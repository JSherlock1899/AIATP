from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class ParseStatus(enum.Enum):
    PENDING = "pending"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceCodeProject(Base):
    __tablename__ = "source_code_projects"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    api_doc_id = Column(Integer, ForeignKey("api_docs.id"), nullable=True)
    name = Column(String(200), nullable=False)
    source_path = Column(String(500), nullable=False)
    language = Column(String(50), default="spring-boot")
    status = Column(SQLEnum(ParseStatus), default=ParseStatus.PENDING)
    error_message = Column(Text, nullable=True)
    endpoints_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    parsed_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project")
    api_doc = relationship("ApiDoc", back_populates="source_code_project", uselist=False)
    endpoints = relationship("ApiEndpoint")
