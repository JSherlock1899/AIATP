"""
Tests for test executor service.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from app.core.database import Base, get_db
from app.main import app
from app.models.test_case import TestCase, TestCaseStatus
from app.models.test_result import TestResult, TestResultStatus
from app.services.test_executor import TestExecutor
from app.schemas.test_case import RequestConfig, AssertionConfig, AssertionType


# Use in-memory database for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class TestRequestConfig:
    """Tests for RequestConfig validation."""

    def test_valid_methods(self):
        """Test all valid HTTP methods are accepted."""
        valid_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        for method in valid_methods:
            config = RequestConfig(method=method, url="http://example.com")
            assert config.method == method.upper()

    def test_lowercase_method_conversion(self):
        """Test lowercase methods are converted to uppercase."""
        config = RequestConfig(method="get", url="http://example.com")
        assert config.method == "GET"

    def test_invalid_method_rejected(self):
        """Test invalid HTTP methods are rejected."""
        with pytest.raises(ValueError):
            RequestConfig(method="INVALID", url="http://example.com")

    def test_default_timeout(self):
        """Test default timeout is 30 seconds."""
        config = RequestConfig(method="GET", url="http://example.com")
        assert config.timeout == 30

    def test_custom_timeout(self):
        """Test custom timeout is accepted."""
        config = RequestConfig(method="GET", url="http://example.com", timeout=60)
        assert config.timeout == 60


class TestAssertionConfig:
    """Tests for AssertionConfig."""

    def test_status_assertion(self):
        """Test status assertion creation."""
        assertion = AssertionConfig(
            type=AssertionType.STATUS,
            field="status_code",
            expected=200
        )
        assert assertion.type == AssertionType.STATUS
        assert assertion.expected == 200

    def test_jsonpath_assertion(self):
        """Test JSONPath assertion creation."""
        assertion = AssertionConfig(
            type=AssertionType.JSONPATH,
            field="$.data.name",
            expected="test"
        )
        assert assertion.type == AssertionType.JSONPATH
        assert assertion.field == "$.data.name"

    def test_header_assertion(self):
        """Test header assertion creation."""
        assertion = AssertionConfig(
            type=AssertionType.HEADER,
            field="Content-Type",
            expected="application/json"
        )
        assert assertion.type == AssertionType.HEADER

    def test_regex_assertion(self):
        """Test regex assertion creation."""
        assertion = AssertionConfig(
            type=AssertionType.REGEX,
            field=r"id:\d+",
            expected="id:123"
        )
        assert assertion.type == AssertionType.REGEX


class TestTestExecutorBuildUrl:
    """Tests for URL building."""

    def test_absolute_url_unchanged(self):
        """Test absolute URLs are not modified."""
        executor = TestExecutor(MagicMock(), base_url="http://custom.com")
        config = RequestConfig(method="GET", url="http://example.com/api")
        assert executor._build_url(config) == "http://example.com/api"

    def test_relative_url_with_base(self):
        """Test relative URLs get base_url prepended."""
        executor = TestExecutor(MagicMock(), base_url="http://custom.com")
        config = RequestConfig(method="GET", url="/api/users")
        assert executor._build_url(config) == "http://custom.com/api/users"

    def test_relative_url_no_trailing_slash_base(self):
        """Test base_url without trailing slash works correctly."""
        executor = TestExecutor(MagicMock(), base_url="http://custom.com")
        config = RequestConfig(method="GET", url="api/users")
        assert executor._build_url(config) == "http://custom.com/api/users"

    def test_relative_url_no_base(self):
        """Test relative URLs without base_url are unchanged."""
        executor = TestExecutor(MagicMock(), base_url=None)
        config = RequestConfig(method="GET", url="api/users")
        assert executor._build_url(config) == "api/users"


class TestTestExecutorApplyTestData:
    """Tests for test data variable substitution."""

    def test_apply_test_data_url(self):
        """Test test data replaces variables in URL."""
        executor = TestExecutor(MagicMock())
        config = RequestConfig(method="GET", url="http://example.com/users/{id}")
        test_data = {"id": "123"}

        result = executor._apply_test_data(config, test_data)
        assert result.url == "http://example.com/users/123"

    def test_apply_test_data_headers(self):
        """Test test data replaces variables in headers."""
        executor = TestExecutor(MagicMock())
        config = RequestConfig(
            method="GET",
            url="http://example.com",
            headers={"Authorization": "Bearer {token}"}
        )
        test_data = {"token": "abc123"}

        result = executor._apply_test_data(config, test_data)
        assert result.headers["Authorization"] == "Bearer abc123"

    def test_apply_test_data_no_test_data(self):
        """Test config unchanged when no test data provided."""
        executor = TestExecutor(MagicMock())
        config = RequestConfig(method="GET", url="http://example.com/users")

        result = executor._apply_test_data(config, None)
        assert result.url == "http://example.com/users"

    def test_apply_test_data_empty_test_data(self):
        """Test config unchanged when empty test data provided."""
        executor = TestExecutor(MagicMock())
        config = RequestConfig(method="GET", url="http://example.com/users")

        result = executor._apply_test_data(config, {})
        assert result.url == "http://example.com/users"


class TestTestExecutorEvaluateAssertions:
    """Tests for assertion evaluation."""

    def test_evaluate_status_assertion_pass(self):
        """Test status assertion passes when status matches."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.STATUS,
            field="status_code",
            expected=200
        )
        response_data = {"status_code": 200, "body": {}}

        result = executor._evaluate_status_assertion(assertion, response_data)
        assert result.passed is True
        assert result.actual == 200

    def test_evaluate_status_assertion_fail(self):
        """Test status assertion fails when status doesn't match."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.STATUS,
            field="status_code",
            expected=200
        )
        response_data = {"status_code": 404, "body": {}}

        result = executor._evaluate_status_assertion(assertion, response_data)
        assert result.passed is False
        assert result.actual == 404

    def test_evaluate_status_assertion_wildcard(self):
        """Test status assertion with wildcard passes for 2xx."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.STATUS,
            field="status_code",
            expected="*"
        )
        response_data = {"status_code": 201, "body": {}}

        result = executor._evaluate_status_assertion(assertion, response_data)
        assert result.passed is True

    def test_evaluate_header_assertion_pass(self):
        """Test header assertion passes when header matches."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.HEADER,
            field="Content-Type",
            expected="application/json"
        )
        response_data = {
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "body": {}
        }

        result = executor._evaluate_header_assertion(assertion, response_data)
        assert result.passed is True

    def test_evaluate_header_assertion_fail(self):
        """Test header assertion fails when header doesn't match."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.HEADER,
            field="Content-Type",
            expected="application/json"
        )
        response_data = {
            "status_code": 200,
            "headers": {"Content-Type": "text/html"},
            "body": {}
        }

        result = executor._evaluate_header_assertion(assertion, response_data)
        assert result.passed is False

    def test_evaluate_header_assertion_not_found(self):
        """Test header assertion fails when header not found."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.HEADER,
            field="X-Custom-Header",
            expected="value"
        )
        response_data = {
            "status_code": 200,
            "headers": {},
            "body": {}
        }

        result = executor._evaluate_header_assertion(assertion, response_data)
        assert result.passed is False
        assert "not found" in result.error_message.lower()

    def test_evaluate_regex_assertion_pass(self):
        """Test regex assertion passes when pattern matches."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.REGEX,
            field=r"user_\d+",
            expected="user_123"
        )
        response_data = {
            "status_code": 200,
            "body": {"message": "Hello user_123!"}
        }

        result = executor._evaluate_regex_assertion(assertion, response_data)
        assert result.passed is True

    def test_evaluate_regex_assertion_fail(self):
        """Test regex assertion fails when pattern doesn't match."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.REGEX,
            field=r"user_\d+",
            expected="user_123"
        )
        response_data = {
            "status_code": 200,
            "body": {"message": "Hello admin!"}
        }

        result = executor._evaluate_regex_assertion(assertion, response_data)
        assert result.passed is False

    def test_evaluate_regex_assertion_no_match(self):
        """Test regex assertion fails when no match found."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.REGEX,
            field=r"not_found_pattern",
            expected=None
        )
        response_data = {
            "status_code": 200,
            "body": {"message": "Hello world!"}
        }

        result = executor._evaluate_regex_assertion(assertion, response_data)
        assert result.passed is False
        assert "did not match" in result.error_message.lower()

    def test_evaluate_jsonpath_assertion_pass(self):
        """Test JSONPath assertion passes when path matches."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.JSONPATH,
            field="$.name",
            expected="John"
        )
        response_data = {
            "status_code": 200,
            "body": {"name": "John", "age": 30}
        }

        result = executor._evaluate_jsonpath_assertion(assertion, response_data)
        assert result.passed is True
        assert result.actual == "John"

    def test_evaluate_jsonpath_assertion_fail(self):
        """Test JSONPath assertion fails when path doesn't match expected."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.JSONPATH,
            field="$.name",
            expected="John"
        )
        response_data = {
            "status_code": 200,
            "body": {"name": "Jane", "age": 25}
        }

        result = executor._evaluate_jsonpath_assertion(assertion, response_data)
        assert result.passed is False
        assert result.actual == "Jane"

    def test_evaluate_jsonpath_assertion_no_match(self):
        """Test JSONPath assertion fails when path not found."""
        executor = TestExecutor(MagicMock())
        assertion = AssertionConfig(
            type=AssertionType.JSONPATH,
            field="$.nonexistent",
            expected="value"
        )
        response_data = {
            "status_code": 200,
            "body": {"name": "John"}
        }

        result = executor._evaluate_jsonpath_assertion(assertion, response_data)
        assert result.passed is False
        assert "no matches" in result.error_message.lower()


class TestTestExecutorIntegration:
    """Integration tests for TestExecutor with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_execute_single_test_success(self, db_session: AsyncSession):
        """Test executing a test case with mocked successful response."""
        # Create a test case
        test_case = TestCase(
            endpoint_id=1,
            name="Test GET users",
            status=TestCaseStatus.ACTIVE,
            request_config={"method": "GET", "url": "http://example.com/api/users"},
            test_data=None,
            expected_response={
                "assertions": [
                    {"type": "status", "field": "status_code", "expected": 200}
                ]
            },
            is_enabled=True
        )
        db_session.add(test_case)
        await db_session.commit()
        await db_session.refresh(test_case)

        # Create executor with mocked response
        executor = TestExecutor(db_session)

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"users": []}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            result = await executor.execute_single_test(test_case)

        assert result.status == TestResultStatus.PASSED
        assert result.response_data["status_code"] == 200
        assert len(result.assertion_results) == 1
        assert result.assertion_results[0]["passed"] is True

    @pytest.mark.asyncio
    async def test_execute_single_test_failure(self, db_session: AsyncSession):
        """Test executing a test case with assertion failure."""
        test_case = TestCase(
            endpoint_id=1,
            name="Test GET users",
            status=TestCaseStatus.ACTIVE,
            request_config={"method": "GET", "url": "http://example.com/api/users"},
            test_data=None,
            expected_response={
                "assertions": [
                    {"type": "status", "field": "status_code", "expected": 201}
                ]
            },
            is_enabled=True
        )
        db_session.add(test_case)
        await db_session.commit()
        await db_session.refresh(test_case)

        executor = TestExecutor(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"users": []}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            result = await executor.execute_single_test(test_case)

        assert result.status == TestResultStatus.FAILED
        assert result.assertion_results[0]["passed"] is False

    @pytest.mark.asyncio
    async def test_execute_batch_multiple_tests(self, db_session: AsyncSession):
        """Test batch execution of multiple test cases."""
        # Create multiple test cases
        test_cases = []
        for i in range(3):
            test_case = TestCase(
                endpoint_id=1,
                name=f"Test {i}",
                status=TestCaseStatus.ACTIVE,
                request_config={"method": "GET", "url": f"http://example.com/api/{i}"},
                test_data=None,
                expected_response={
                    "assertions": [
                        {"type": "status", "field": "status_code", "expected": 200}
                    ]
                },
                is_enabled=True
            )
            db_session.add(test_case)
            test_cases.append(test_case)

        await db_session.commit()
        for tc in test_cases:
            await db_session.refresh(tc)

        executor = TestExecutor(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": "ok"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            result = await executor.execute_batch([tc.id for tc in test_cases])

        assert result.total == 3
        assert result.passed == 3
        assert result.failed == 0
        assert result.error == 0

    @pytest.mark.asyncio
    async def test_execute_with_timeout_error(self, db_session: AsyncSession):
        """Test handling of timeout errors."""
        test_case = TestCase(
            endpoint_id=1,
            name="Test timeout",
            status=TestCaseStatus.ACTIVE,
            request_config={"method": "GET", "url": "http://example.com/api/slow", "timeout": 1},
            test_data=None,
            expected_response={"assertions": []},
            is_enabled=True
        )
        db_session.add(test_case)
        await db_session.commit()
        await db_session.refresh(test_case)

        executor = TestExecutor(db_session)

        import httpx
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )

            result = await executor.execute_single_test(test_case)

        assert result.status == TestResultStatus.ERROR
        assert "timeout" in result.error_message.lower()


class TestBatchExecutionWithSkipped:
    """Tests for batch execution with skipped tests."""

    @pytest.mark.asyncio
    async def test_execute_batch_skips_disabled(self, db_session: AsyncSession):
        """Test that disabled test cases are skipped in batch execution."""
        # Create one enabled and one disabled test case
        enabled_case = TestCase(
            endpoint_id=1,
            name="Enabled test",
            status=TestCaseStatus.ACTIVE,
            request_config={"method": "GET", "url": "http://example.com/api/enabled"},
            test_data=None,
            expected_response={
                "assertions": [
                    {"type": "status", "field": "status_code", "expected": 200}
                ]
            },
            is_enabled=True
        )
        disabled_case = TestCase(
            endpoint_id=1,
            name="Disabled test",
            status=TestCaseStatus.ACTIVE,
            request_config={"method": "GET", "url": "http://example.com/api/disabled"},
            test_data=None,
            expected_response={
                "assertions": [
                    {"type": "status", "field": "status_code", "expected": 200}
                ]
            },
            is_enabled=False
        )

        db_session.add(enabled_case)
        db_session.add(disabled_case)
        await db_session.commit()
        await db_session.refresh(enabled_case)
        await db_session.refresh(disabled_case)

        executor = TestExecutor(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": "ok"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            result = await executor.execute_batch([enabled_case.id, disabled_case.id])

        assert result.total == 2
        assert result.passed == 1
        assert result.skipped == 1

    @pytest.mark.asyncio
    async def test_execute_batch_nonexistent_id(self, db_session: AsyncSession):
        """Test that nonexistent test case IDs are skipped."""
        executor = TestExecutor(db_session)

        result = await executor.execute_batch([9999])

        assert result.total == 1
        assert result.skipped == 1
