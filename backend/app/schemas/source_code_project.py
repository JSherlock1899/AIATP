from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional


class SourceCodeProjectCreate(BaseModel):
    """Schema for creating a source code project."""
    project_id: int
    name: str
    source_path: str

    @field_validator("source_path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("Path traversal not allowed")
        if len(v) < 2 or (not v.startswith("/") and v[1] != ":"):
            raise ValueError("Absolute path required")
        return v


class SourceCodeProjectResponse(BaseModel):
    """Schema for source code project response."""
    id: int
    project_id: int
    name: str
    source_path: str
    language: str
    status: str
    error_message: Optional[str] = None
    endpoints_count: int = 0
    created_at: datetime
    parsed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SourceCodeParseRequest(BaseModel):
    """Schema for parse request."""
    project_id: int
    name: str
    source_path: str


class SourceCodeParseResponse(BaseModel):
    """Schema for parse response."""
    id: int
    name: str
    source_path: str
    status: str
    endpoints_count: int
    message: Optional[str] = None
