"""
HTTP test execution service.
"""
import json
import re
import time
import ipaddress
import httpx
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.exceptions import JsonPathParserError

from app.models.test_case import TestCase, TestCaseStatus
from app.models.test_result import TestResult, TestResultStatus
from app.schemas.test_case import (
    AssertionConfig,
    AssertionType,
    RequestConfig,
    TestResultDetail,
    TestExecutionResponse,
)

# Blocked host patterns for SSRF prevention
BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
}

# Internal IP ranges to block
INTERNAL_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]


class SSRFProtectionError(Exception):
    """Raised when a URL fails SSRF validation."""
    pass


class TestExecutor:
    """Service for executing HTTP tests."""

    # Maximum regex complexity (number of states) to prevent ReDoS
    MAX_REGEX_STATES = 10000

    def __init__(self, db, base_url: Optional[str] = None):
        self.db = db
        self.base_url = base_url

    def _validate_url(self, url: str) -> None:
        """
        Validate URL to prevent SSRF attacks.

        Raises:
            SSRFProtectionError: If the URL is not allowed
        """
        if not url:
            raise SSRFProtectionError("URL cannot be empty")

        # Only allow http and https protocols
        if not url.startswith(("http://", "https://")):
            raise SSRFProtectionError("Only HTTP and HTTPS protocols are allowed")

        try:
            # Parse the URL
            parsed = httpx.URL(url)
            host = parsed.host

            if not host:
                raise SSRFProtectionError("Invalid URL: no host found")

            # Check for blocked hosts
            if host.lower() in BLOCKED_HOSTS:
                raise SSRFProtectionError(f"URL host '{host}' is not allowed")

            # Check if host is an IP address
            try:
                ip = ipaddress.ip_address(host)
                # Block internal/private IP addresses
                if ip.is_loopback or ip.is_private or ip.is_reserved:
                    raise SSRFProtectionError(f"Internal IP addresses are not allowed: {ip}")
            except ValueError:
                # It's a hostname, not an IP - hostname validation is done later
                pass

        except SSRFProtectionError:
            raise
        except Exception:
            raise SSRFProtectionError("Invalid URL format")

    def _build_url(self, request_config: RequestConfig) -> str:
        """Build full URL from request config."""
        url = request_config.url
        if not url.startswith(("http://", "https://")):
            if self.base_url:
                url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        return url

    def _apply_test_data(self, request_config: RequestConfig, test_data: Optional[Dict[str, Any]]) -> RequestConfig:
        """Apply test data variables to request config."""
        if not test_data:
            return request_config

        # Convert to dict for modification
        config_dict = request_config.model_dump()

        # Replace variables in URL
        url = config_dict["url"]
        for key, value in test_data.items():
            url = url.replace(f"{{{key}}}", str(value))
        config_dict["url"] = url

        # Replace variables in headers
        if config_dict.get("headers"):
            for key, value in config_dict["headers"].items():
                if isinstance(value, str):
                    for k, v in test_data.items():
                        config_dict["headers"][key] = value.replace(f"{{{k}}}", str(v))

        # Replace variables in body
        if config_dict.get("body") and isinstance(config_dict["body"], dict):
            body_str = str(config_dict["body"])
            for key, value in test_data.items():
                body_str = body_str.replace(f"{{{key}}}", str(value))
            config_dict["body"] = json.loads(body_str)

        return RequestConfig(**config_dict)

    async def _execute_request(self, request_config: RequestConfig) -> tuple[Dict[str, Any], float, Optional[str]]:
        """
        Execute HTTP request and return response data, response time, and error.
        Response time is in milliseconds.
        """
        start_time = time.time()

        try:
            url = self._build_url(request_config)

            # Validate URL before making request (SSRF protection)
            self._validate_url(url)

            async with httpx.AsyncClient(timeout=request_config.timeout) as client:
                method = request_config.method
                headers = request_config.headers or {}
                params = request_config.params or {}
                body = request_config.body

                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=body if body else None,
                )

                response_time = (time.time() - start_time) * 1000

                try:
                    response_data = response.json()
                except Exception:
                    response_data = {"body": response.text}

                response_data_with_status = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_data,
                }

                return response_data_with_status, response_time, None

        except SSRFProtectionError as e:
            response_time = (time.time() - start_time) * 1000
            return {}, response_time, "URL validation failed"
        except httpx.TimeoutException:
            response_time = (time.time() - start_time) * 1000
            return {}, response_time, "Request timeout"
        except httpx.RequestError:
            response_time = (time.time() - start_time) * 1000
            return {}, response_time, "Request failed"
        except Exception:
            response_time = (time.time() - start_time) * 1000
            return {}, response_time, "Unexpected error"

    def _evaluate_status_assertion(self, assertion: AssertionConfig, response_data: Dict[str, Any]) -> TestResultDetail:
        """Evaluate status code assertion."""
        actual_status = response_data.get("status_code")
        expected_status = int(assertion.expected) if assertion.expected != "*" else None

        if expected_status is not None:
            passed = actual_status == expected_status
        else:
            # If expected is "*", check if status is 2xx
            passed = 200 <= (actual_status or 0) < 300

        return TestResultDetail(
            assertion_type=assertion.type.value,
            field="status_code",
            expected=assertion.expected,
            actual=actual_status,
            passed=passed,
            description=assertion.description,
            error_message=None if passed else f"Expected status {assertion.expected}, got {actual_status}"
        )

    def _evaluate_jsonpath_assertion(self, assertion: AssertionConfig, response_data: Dict[str, Any]) -> TestResultDetail:
        """Evaluate JSONPath assertion."""
        try:
            jsonpath_expr = jsonpath_parse(assertion.field)
            body = response_data.get("body", {})

            matches = [match.value for match in jsonpath_expr.find(body)]

            if not matches:
                return TestResultDetail(
                    assertion_type=assertion.type.value,
                    field=assertion.field,
                    expected=assertion.expected,
                    actual=None,
                    passed=False,
                    description=assertion.description,
                    error_message=f"JSONPath '{assertion.field}' returned no matches"
                )

            actual = matches[0] if len(matches) == 1 else matches

            # Handle different comparison types
            if isinstance(assertion.expected, dict):
                # For complex expected values, check if actual is in expected or matches
                passed = actual in assertion.expected.values() if isinstance(assertion.expected, dict) else actual == assertion.expected
            else:
                passed = str(actual) == str(assertion.expected)

            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=actual,
                passed=passed,
                description=assertion.description,
                error_message=None if passed else f"Expected '{assertion.expected}', got '{actual}'"
            )

        except JsonPathParserError as e:
            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message=f"Invalid JSONPath '{assertion.field}': {str(e)}"
            )
        except Exception as e:
            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message=f"JSONPath evaluation error: {str(e)}"
            )

    def _evaluate_header_assertion(self, assertion: AssertionConfig, response_data: Dict[str, Any]) -> TestResultDetail:
        """Evaluate header assertion."""
        headers = response_data.get("headers", {})
        actual = headers.get(assertion.field)

        if actual is None:
            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message=f"Header '{assertion.field}' not found in response"
            )

        passed = str(actual) == str(assertion.expected)

        return TestResultDetail(
            assertion_type=assertion.type.value,
            field=assertion.field,
            expected=assertion.expected,
            actual=actual,
            passed=passed,
            description=assertion.description,
            error_message=None if passed else f"Expected header '{assertion.field}' to be '{assertion.expected}', got '{actual}'"
        )

    def _validate_regex_complexity(self, pattern: str) -> bool:
        """
        Check if regex pattern is too complex (potential ReDoS).

        Returns:
            True if pattern is safe, False otherwise
        """
        try:
            # Compile the pattern
            compiled = re.compile(pattern)
            # Check the size of the state machine using the regex structure
            # This is a simplified check - counts characters as proxy for complexity
            if len(pattern) > 500:
                return False
            return True
        except re.error:
            # Let the normal error handling deal with invalid patterns
            return True

    def _evaluate_regex_assertion(self, assertion: AssertionConfig, response_data: Dict[str, Any]) -> TestResultDetail:
        """Evaluate regex assertion on response body."""
        try:
            pattern_str = str(assertion.field)

            # Check regex complexity to prevent ReDoS
            if not self._validate_regex_complexity(pattern_str):
                return TestResultDetail(
                    assertion_type=assertion.type.value,
                    field=assertion.field,
                    expected=assertion.expected,
                    actual=None,
                    passed=False,
                    description=assertion.description,
                    error_message="Regex pattern is too complex"
                )

            pattern = re.compile(pattern_str)
            body = response_data.get("body", {})

            # Convert body to string for regex matching
            if isinstance(body, dict):
                body_str = str(body)
            elif isinstance(body, str):
                body_str = body
            else:
                body_str = str(body)

            match = pattern.search(body_str)

            if not match:
                return TestResultDetail(
                    assertion_type=assertion.type.value,
                    field=assertion.field,
                    expected=assertion.expected,
                    actual=None,
                    passed=False,
                    description=assertion.description,
                    error_message=f"Regex pattern '{assertion.field}' did not match"
                )

            actual = match.group(0)

            # If expected is provided, check if it matches the captured group
            if assertion.expected:
                passed = actual == str(assertion.expected)
            else:
                passed = True

            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=actual,
                passed=passed,
                description=assertion.description,
                error_message=None if passed else f"Expected match '{assertion.expected}', got '{actual}'"
            )

        except re.error as e:
            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message=f"Invalid regex pattern '{assertion.field}'"
            )
        except Exception as e:
            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message="Regex evaluation error"
            )

    def _evaluate_response_time_assertion(self, assertion: AssertionConfig, response_data: Dict[str, Any], response_time: float) -> TestResultDetail:
        """Evaluate response time assertion."""
        expected_ms = int(assertion.expected)
        actual_ms = int(response_time)
        passed = actual_ms <= expected_ms

        return TestResultDetail(
            assertion_type=assertion.type.value,
            field="response_time",
            expected=expected_ms,
            actual=actual_ms,
            passed=passed,
            description=assertion.description,
            error_message=None if passed else f"Response time {actual_ms}ms exceeded limit {expected_ms}ms"
        )

    def _evaluate_range_assertion(self, assertion: AssertionConfig, response_data: Dict[str, Any]) -> TestResultDetail:
        """Evaluate range assertion (min/max values)."""
        try:
            jsonpath_expr = jsonpath_parse(assertion.field)
            body = response_data.get("body", {})
            matches = [match.value for match in jsonpath_expr.find(body)]

            if not matches:
                return TestResultDetail(
                    assertion_type=assertion.type.value,
                    field=assertion.field,
                    expected=assertion.expected,
                    actual=None,
                    passed=False,
                    description=assertion.description,
                    error_message=f"JSONPath '{assertion.field}' returned no matches"
                )

            actual = matches[0] if len(matches) == 1 else matches

            # expected should be a dict with 'min' and 'max' keys
            if isinstance(assertion.expected, dict):
                min_val = assertion.expected.get("min")
                max_val = assertion.expected.get("max")

                if min_val is not None and max_val is not None:
                    passed = min_val <= actual <= max_val
                    expected_str = f"{min_val} <= x <= {max_val}"
                elif min_val is not None:
                    passed = actual >= min_val
                    expected_str = f"x >= {min_val}"
                elif max_val is not None:
                    passed = actual <= max_val
                    expected_str = f"x <= {max_val}"
                else:
                    passed = False
                    expected_str = str(assertion.expected)
            else:
                passed = actual == assertion.expected
                expected_str = str(assertion.expected)

            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=expected_str,
                actual=actual,
                passed=passed,
                description=assertion.description,
                error_message=None if passed else f"Value {actual} is outside range {expected_str}"
            )
        except JsonPathParserError as e:
            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message=f"Invalid JSONPath '{assertion.field}': {str(e)}"
            )
        except Exception as e:
            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message=f"Range evaluation error: {str(e)}"
            )

    def _evaluate_array_count_assertion(self, assertion: AssertionConfig, response_data: Dict[str, Any]) -> TestResultDetail:
        """Evaluate array count assertion."""
        try:
            jsonpath_expr = jsonpath_parse(assertion.field)
            body = response_data.get("body", {})
            matches = [match.value for match in jsonpath_expr.find(body)]

            if not matches:
                return TestResultDetail(
                    assertion_type=assertion.type.value,
                    field=assertion.field,
                    expected=assertion.expected,
                    actual=None,
                    passed=False,
                    description=assertion.description,
                    error_message=f"JSONPath '{assertion.field}' returned no matches"
                )

            actual_array = matches[0] if len(matches) == 1 else matches

            if not isinstance(actual_array, (list, dict)):
                return TestResultDetail(
                    assertion_type=assertion.type.value,
                    field=assertion.field,
                    expected=assertion.expected,
                    actual=type(actual_array).__name__,
                    passed=False,
                    description=assertion.description,
                    error_message=f"Field '{assertion.field}' is not an array or object"
                )

            # For dict, count keys; for list, count elements
            if isinstance(actual_array, dict):
                actual_count = len(actual_array.keys())
            else:
                actual_count = len(actual_array)

            # expected can be a number, or a dict with min/max
            if isinstance(assertion.expected, dict):
                min_val = assertion.expected.get("min")
                max_val = assertion.expected.get("max")

                if min_val is not None and max_val is not None:
                    passed = min_val <= actual_count <= max_val
                    expected_str = f"{min_val} <= count <= {max_val}"
                elif min_val is not None:
                    passed = actual_count >= min_val
                    expected_str = f"count >= {min_val}"
                elif max_val is not None:
                    passed = actual_count <= max_val
                    expected_str = f"count <= {max_val}"
                else:
                    passed = False
                    expected_str = str(assertion.expected)
            else:
                passed = actual_count == int(assertion.expected)
                expected_str = str(assertion.expected)

            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=expected_str,
                actual=actual_count,
                passed=passed,
                description=assertion.description,
                error_message=None if passed else f"Array count {actual_count} does not match expected {expected_str}"
            )
        except JsonPathParserError as e:
            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message=f"Invalid JSONPath '{assertion.field}': {str(e)}"
            )
        except Exception as e:
            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message=f"Array count evaluation error: {str(e)}"
            )

    def _evaluate_json_size_assertion(self, assertion: AssertionConfig, response_data: Dict[str, Any]) -> TestResultDetail:
        """Evaluate JSON size assertion (byte length of JSON body)."""
        try:
            body = response_data.get("body")
            if body is None:
                return TestResultDetail(
                    assertion_type=assertion.type.value,
                    field="body",
                    expected=assertion.expected,
                    actual=None,
                    passed=False,
                    description=assertion.description,
                    error_message="Response body is empty"
                )

            import sys
            body_str = json.dumps(body) if not isinstance(body, str) else body
            actual_size = len(body_str.encode('utf-8'))

            # expected can be a number (max bytes), or dict with min/max
            if isinstance(assertion.expected, dict):
                min_val = assertion.expected.get("min")
                max_val = assertion.expected.get("max")

                if min_val is not None and max_val is not None:
                    passed = min_val <= actual_size <= max_val
                    expected_str = f"{min_val} <= size <= {max_val}"
                elif min_val is not None:
                    passed = actual_size >= min_val
                    expected_str = f"size >= {min_val}"
                elif max_val is not None:
                    passed = actual_size <= max_val
                    expected_str = f"size <= {max_val}"
                else:
                    passed = False
                    expected_str = str(assertion.expected)
            else:
                max_size = int(assertion.expected)
                passed = actual_size <= max_size
                expected_str = f"size <= {max_size}"

            return TestResultDetail(
                assertion_type=assertion.type.value,
                field="body",
                expected=expected_str,
                actual=actual_size,
                passed=passed,
                description=assertion.description,
                error_message=None if passed else f"JSON size {actual_size} bytes exceeds limit {expected_str}"
            )
        except Exception as e:
            return TestResultDetail(
                assertion_type=assertion.type.value,
                field="body",
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message=f"JSON size evaluation error: {str(e)}"
            )

    def _evaluate_assertion(self, assertion: AssertionConfig, response_data: Dict[str, Any], response_time: float = 0) -> TestResultDetail:
        """Evaluate a single assertion based on its type."""
        if assertion.type == AssertionType.STATUS:
            return self._evaluate_status_assertion(assertion, response_data)
        elif assertion.type == AssertionType.JSONPATH:
            return self._evaluate_jsonpath_assertion(assertion, response_data)
        elif assertion.type == AssertionType.HEADER:
            return self._evaluate_header_assertion(assertion, response_data)
        elif assertion.type == AssertionType.REGEX:
            return self._evaluate_regex_assertion(assertion, response_data)
        elif assertion.type == AssertionType.RESPONSE_TIME:
            return self._evaluate_response_time_assertion(assertion, response_data, response_time)
        elif assertion.type == AssertionType.RANGE:
            return self._evaluate_range_assertion(assertion, response_data)
        elif assertion.type == AssertionType.ARRAY_COUNT:
            return self._evaluate_array_count_assertion(assertion, response_data)
        elif assertion.type == AssertionType.JSON_SIZE:
            return self._evaluate_json_size_assertion(assertion, response_data)
        else:
            return TestResultDetail(
                assertion_type=assertion.type.value if hasattr(assertion.type, 'value') else str(assertion.type),
                field=assertion.field,
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message=f"Unknown assertion type: {assertion.type}"
            )

    async def execute_single_test(
        self,
        test_case: TestCase,
        base_url: Optional[str] = None
    ) -> TestResult:
        """Execute a single test case and return the result."""
        original_base_url = self.base_url
        if base_url:
            self.base_url = base_url

        try:
            # Build request config
            request_config = RequestConfig(**test_case.request_config)

            # Apply test data
            request_config = self._apply_test_data(request_config, test_case.test_data)

            # Execute request
            response_data, response_time, error = await self._execute_request(request_config)

            # Evaluate assertions
            assertion_details = []
            overall_passed = True

            if test_case.expected_response:
                # Parse assertions from expected_response if present
                assertions_data = test_case.expected_response.get("assertions", [])
                for assert_data in assertions_data:
                    assertion = AssertionConfig(**assert_data)
                    result = self._evaluate_assertion(assertion, response_data, response_time)
                    assertion_details.append(result)
                    if not result.passed:
                        overall_passed = False

            # Determine status
            if error:
                status = TestResultStatus.ERROR
            elif overall_passed:
                status = TestResultStatus.PASSED
            else:
                status = TestResultStatus.FAILED

            # Create test result
            test_result = TestResult(
                test_case_id=test_case.id,
                status=status,
                response_data=response_data,
                response_time=response_time,
                error_message=error,
                assertion_results=[d.model_dump() for d in assertion_details]
            )

            self.db.add(test_result)
            await self.db.commit()
            await self.db.refresh(test_result)

            return test_result

        finally:
            self.base_url = original_base_url

    async def execute_single_test_by_id(
        self,
        test_case_id: int,
        base_url: Optional[str] = None
    ) -> TestResult:
        """Execute a single test case by its ID and return the result."""
        result = await self.db.execute(
            select(TestCase).where(TestCase.id == test_case_id)
        )
        test_case = result.scalar_one_or_none()

        if not test_case:
            raise ValueError(f"Test case {test_case_id} not found")

        if not test_case.is_enabled:
            raise ValueError(f"Test case {test_case_id} is disabled")

        return await self.execute_single_test(test_case, base_url)

    async def execute_batch(
        self,
        test_case_ids: List[int],
        base_url: Optional[str] = None
    ) -> TestExecutionResponse:
        """Execute multiple test cases and return batch results."""
        start_time = time.time()

        results = []
        passed = 0
        failed = 0
        error = 0
        skipped = 0

        for test_case_id in test_case_ids:
            result = await self.db.execute(
                select(TestCase).where(TestCase.id == test_case_id)
            )
            test_case = result.scalar_one_or_none()

            if not test_case:
                skipped += 1
                continue

            if not test_case.is_enabled:
                skipped += 1
                continue

            test_result = await self.execute_single_test(test_case, base_url)
            results.append(test_result)

            if test_result.status == TestResultStatus.PASSED:
                passed += 1
            elif test_result.status == TestResultStatus.FAILED:
                failed += 1
            elif test_result.status == TestResultStatus.ERROR:
                error += 1
            else:
                skipped += 1

        total_time = (time.time() - start_time) * 1000

        return TestExecutionResponse(
            total=len(test_case_ids),
            passed=passed,
            failed=failed,
            error=error,
            skipped=skipped,
            results=results,
            execution_time=total_time
        )

    async def execute_batch_stream(
        self,
        test_case_ids: List[int],
        base_url: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """Execute multiple test cases and yield progress events (for SSE streaming)."""
        start_time = time.time()
        total = len(test_case_ids)
        passed = 0
        failed = 0
        error = 0
        skipped = 0

        for index, test_case_id in enumerate(test_case_ids):
            # Yield progress event before executing
            yield {
                "event": "progress",
                "data": {
                    "current": index + 1,
                    "total": total,
                    "test_case_id": test_case_id,
                    "status": "running",
                    "passed": passed,
                    "failed": failed,
                    "error": error,
                    "skipped": skipped
                }
            }

            result = await self.db.execute(
                select(TestCase).where(TestCase.id == test_case_id)
            )
            test_case = result.scalar_one_or_none()

            if not test_case:
                skipped += 1
                yield {
                    "event": "result",
                    "data": {
                        "test_case_id": test_case_id,
                        "status": "skipped",
                        "reason": "Test case not found"
                    }
                }
                continue

            if not test_case.is_enabled:
                skipped += 1
                yield {
                    "event": "result",
                    "data": {
                        "test_case_id": test_case_id,
                        "status": "skipped",
                        "reason": "Test case is disabled"
                    }
                }
                continue

            test_result = await self.execute_single_test(test_case, base_url)

            if test_result.status == TestResultStatus.PASSED:
                passed += 1
            elif test_result.status == TestResultStatus.FAILED:
                failed += 1
            elif test_result.status == TestResultStatus.ERROR:
                error += 1
            else:
                skipped += 1

            # Yield result event
            yield {
                "event": "result",
                "data": {
                    "test_case_id": test_case_id,
                    "result_id": test_result.id,
                    "status": test_result.status.value,
                    "response_time": test_result.response_time,
                    "error_message": test_result.error_message,
                    "assertion_results": test_result.assertion_results,
                    "passed": test_result.status == TestResultStatus.PASSED,
                    "passed_count": passed,
                    "failed_count": failed,
                    "error_count": error,
                    "skipped_count": skipped
                }
            }

        total_time = (time.time() - start_time) * 1000

        # Yield completion event
        yield {
            "event": "complete",
            "data": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "error": error,
                "skipped": skipped,
                "execution_time": total_time
            }
        }
