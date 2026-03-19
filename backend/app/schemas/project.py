from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    project_key: str

    @field_validator("project_key")
    @classmethod
    def validate_project_key(cls, v: str) -> str:
        if len(v) < 2 or len(v) > 20:
            raise ValueError("project_key must be 2-20 characters")
        if not v.isalnum():
            raise ValueError("project_key must be alphanumeric")
        return v.upper()


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    project_key: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectMemberResponse(BaseModel):
    id: int
    user_id: int
    project_id: int
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectWithMembers(ProjectResponse):
    members: List[ProjectMemberResponse] = []
