"""
Test case related Pydantic schemas.
"""
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class AssertionType(str, Enum):
    """Assertion types for test validation."""
    STATUS = "status"
    JSONPATH = "jsonpath"
    HEADER = "header"
    REGEX = "regex"


class AssertionConfig(BaseModel):
    """Single assertion configuration."""
    type: AssertionType
    field: str  # JSONPath expression, header name, or regex pattern
    expected: Any
    description: Optional[str] = None


class RequestConfig(BaseModel):
    """HTTP request configuration."""
    method: str
    url: str
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, str]] = None
    body: Optional[Any] = None
    timeout: Optional[int] = 30

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        allowed = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        if v.upper() not in allowed:
            raise ValueError(f"method must be one of {allowed}")
        return v.upper()


class TestCaseCreate(BaseModel):
    """Schema for creating a test case."""
    endpoint_id: int
    name: str
    description: Optional[str] = None
    request_config: RequestConfig
    test_data: Optional[Dict[str, Any]] = None
    assertions: List[AssertionConfig] = []
    is_enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) < 1 or len(v) > 200:
            raise ValueError("name must be 1-200 characters")
        return v


class TestCaseUpdate(BaseModel):
    """Schema for updating a test case."""
    name: Optional[str] = None
    description: Optional[str] = None
    request_config: Optional[RequestConfig] = None
    test_data: Optional[Dict[str, Any]] = None
    assertions: Optional[List[AssertionConfig]] = None
    is_enabled: Optional[bool] = None


class TestCaseResponse(BaseModel):
    """Schema for test case response."""
    id: int
    endpoint_id: int
    name: str
    description: Optional[str]
    status: str
    request_config: Dict[str, Any]
    test_data: Optional[Dict[str, Any]]
    expected_response: Optional[Dict[str, Any]]
    is_enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TestExecutionRequest(BaseModel):
    """Schema for test execution request."""
    test_case_ids: List[int]
    base_url: Optional[str] = None  # Override base URL for testing


class TestResultDetail(BaseModel):
    """Detailed result of a single assertion."""
    assertion_type: str
    field: str
    expected: Any
    actual: Any
    passed: bool
    description: Optional[str] = None
    error_message: Optional[str] = None


class TestResultResponse(BaseModel):
    """Schema for test result response."""
    id: int
    test_case_id: int
    status: str
    response_data: Optional[Dict[str, Any]]
    response_time: float
    error_message: Optional[str]
    assertion_results: List[TestResultDetail]
    executed_at: datetime

    model_config = {"from_attributes": True}


class TestExecutionResponse(BaseModel):
    """Schema for batch test execution response."""
    total: int
    passed: int
    failed: int
    error: int
    skipped: int
    results: List[TestResultResponse]
    execution_time: float  # Total time in milliseconds
