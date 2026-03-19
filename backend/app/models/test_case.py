from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class TestCaseStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    endpoint_id = Column(Integer, ForeignKey("api_endpoints.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(SQLEnum(TestCaseStatus), default=TestCaseStatus.DRAFT)
    request_config = Column(JSON)
    test_data = Column(JSON)
    expected_response = Column(JSON)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    endpoint = relationship("ApiEndpoint", back_populates="test_cases")
    results = relationship("TestResult", back_populates="test_case")
