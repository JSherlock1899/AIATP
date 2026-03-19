from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class TestResultStatus(enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False)
    status = Column(SQLEnum(TestResultStatus), nullable=False)
    response_data = Column(JSON)
    response_time = Column(Float)
    """Response time in milliseconds"""
    error_message = Column(Text)
    assertion_results = Column(JSON)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())

    test_case = relationship("TestCase", back_populates="results")
