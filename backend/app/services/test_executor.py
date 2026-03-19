"""
HTTP test execution service.
"""
import json
import re
import time
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


class TestExecutor:
    """Service for executing HTTP tests."""

    def __init__(self, db, base_url: Optional[str] = None):
        self.db = db
        self.base_url = base_url

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
            async with httpx.AsyncClient(timeout=request_config.timeout) as client:
                method = request_config.method
                url = self._build_url(request_config)
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

        except httpx.TimeoutException as e:
            response_time = (time.time() - start_time) * 1000
            return {}, response_time, f"Request timeout: {str(e)}"
        except httpx.RequestError as e:
            response_time = (time.time() - start_time) * 1000
            return {}, response_time, f"Request error: {str(e)}"
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {}, response_time, f"Unexpected error: {str(e)}"

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

    def _evaluate_regex_assertion(self, assertion: AssertionConfig, response_data: Dict[str, Any]) -> TestResultDetail:
        """Evaluate regex assertion on response body."""
        try:
            pattern = re.compile(str(assertion.field))
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
                error_message=f"Invalid regex pattern '{assertion.field}': {str(e)}"
            )
        except Exception as e:
            return TestResultDetail(
                assertion_type=assertion.type.value,
                field=assertion.field,
                expected=assertion.expected,
                actual=None,
                passed=False,
                description=assertion.description,
                error_message=f"Regex evaluation error: {str(e)}"
            )

    def _evaluate_assertion(self, assertion: AssertionConfig, response_data: Dict[str, Any]) -> TestResultDetail:
        """Evaluate a single assertion based on its type."""
        if assertion.type == AssertionType.STATUS:
            return self._evaluate_status_assertion(assertion, response_data)
        elif assertion.type == AssertionType.JSONPATH:
            return self._evaluate_jsonpath_assertion(assertion, response_data)
        elif assertion.type == AssertionType.HEADER:
            return self._evaluate_header_assertion(assertion, response_data)
        elif assertion.type == AssertionType.REGEX:
            return self._evaluate_regex_assertion(assertion, response_data)
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
                    result = self._evaluate_assertion(assertion, response_data)
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
