from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ApiDoc(Base):
    __tablename__ = "api_docs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    version = Column(String(20), default="1.0.0")
    description = Column(Text)
    content = Column(Text)
    file_path = Column(String(500))
    parsed_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project")
    endpoints = relationship("ApiEndpoint", back_populates="api_doc")
