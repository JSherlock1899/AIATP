from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class HttpMethod(enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ApiEndpoint(Base):
    __tablename__ = "api_endpoints"

    id = Column(Integer, primary_key=True, index=True)
    api_doc_id = Column(Integer, ForeignKey("api_docs.id"), nullable=True)
    source_code_project_id = Column(Integer, ForeignKey("source_code_projects.id"), nullable=True)
    path = Column(String(500), nullable=False, index=True)
    method = Column(SQLEnum(HttpMethod), nullable=False)
    summary = Column(String(500))
    description = Column(Text)
    operation_id = Column(String(100))
    request_body = Column(JSON)
    request_headers = Column(JSON)
    request_params = Column(JSON)
    responses = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    api_doc = relationship("ApiDoc", back_populates="endpoints")
    source_code_project = relationship("SourceCodeProject", back_populates="endpoints")
    test_cases = relationship("TestCase", back_populates="endpoint")
