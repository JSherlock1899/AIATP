from pydantic import BaseModel, field_validator, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any


class EndpointParameter(BaseModel):
    """API endpoint parameter schema."""
    name: str
    location: str  # query, path, header, cookie
    required: bool = False
    description: Optional[str] = None
    param_schema: Optional[Dict[str, Any]] = None


class EndpointRequestBody(BaseModel):
    """API endpoint request body schema."""
    description: Optional[str] = None
    required: bool = False
    content_type: Optional[str] = None
    body_schema: Optional[Dict[str, Any]] = None


class EndpointResponse(BaseModel):
    """API endpoint response schema."""
    status_code: int
    description: Optional[str] = None
    response_schema: Optional[Dict[str, Any]] = None


class ApiEndpointBase(BaseModel):
    """Base API endpoint schema."""
    path: str
    method: str
    summary: Optional[str] = None
    description: Optional[str] = None
    operation_id: Optional[str] = None
    parameters: List[EndpointParameter] = []
    request_body: Optional[EndpointRequestBody] = None
    responses: List[EndpointResponse] = []


class ApiEndpointCreate(ApiEndpointBase):
    """Schema for creating an API endpoint."""
    api_doc_id: int


class ApiEndpointResponse(ApiEndpointBase):
    """Schema for API endpoint response."""
    id: int
    api_doc_id: int
    is_active: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiDocBase(BaseModel):
    """Base API document schema."""
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None


class ApiDocCreate(ApiDocBase):
    """Schema for creating an API document."""
    project_id: int


class ApiDocImport(BaseModel):
    """Schema for importing an OpenAPI document."""
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    content: Optional[str] = None  # Raw YAML/JSON content

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) == 0:
            return None
        return v


class ApiDocResponse(ApiDocBase):
    """Schema for API document response."""
    id: int
    project_id: int
    file_path: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ApiDocDetailResponse(ApiDocResponse):
    """Schema for detailed API document response with endpoints count."""
    endpoints_count: int = 0


class ApiDocWithEndpoints(ApiDocResponse):
    """Schema for API document with its endpoints."""
    endpoints: List[ApiEndpointResponse] = []


class OpenAPIParsedInfo(BaseModel):
    """Schema for parsed OpenAPI document info."""
    title: str
    version: str
    description: Optional[str] = None
    openapi_version: str
    endpoints_count: int
    paths: List[str]
