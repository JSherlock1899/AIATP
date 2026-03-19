"""
Test case management API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from app.core.database import get_db
from app.schemas.test_case import (
    TestCaseCreate,
    TestCaseUpdate,
    TestCaseResponse,
    TestExecutionRequest,
    TestExecutionResponse,
    TestResultResponse,
)
from app.services.test_executor import TestExecutor
from app.api.auth import get_current_user
from app.models.user import User
from app.models.test_case import TestCase, TestCaseStatus
from app.models.api_endpoint import ApiEndpoint

router = APIRouter(prefix="/test-cases", tags=["test-cases"])


async def get_test_case_or_404(test_case_id: int, db: AsyncSession) -> TestCase:
    """Get test case by ID or raise 404."""
    result = await db.execute(
        select(TestCase)
        .options(selectinload(TestCase.endpoint))
        .where(TestCase.id == test_case_id)
    )
    test_case = result.scalar_one_or_none()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found"
        )
    return test_case


@router.post("", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
async def create_test_case(
    test_case_data: TestCaseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new test case for an API endpoint.
    """
    # Verify endpoint exists
    result = await db.execute(
        select(ApiEndpoint).where(ApiEndpoint.id == test_case_data.endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API endpoint not found"
        )

    # Build expected_response from assertions
    expected_response = {
        "assertions": [a.model_dump() for a in test_case_data.assertions]
    }

    db_test_case = TestCase(
        endpoint_id=test_case_data.endpoint_id,
        name=test_case_data.name,
        description=test_case_data.description,
        status=TestCaseStatus.ACTIVE,
        request_config=test_case_data.request_config.model_dump(),
        test_data=test_case_data.test_data,
        expected_response=expected_response,
        is_enabled=test_case_data.is_enabled
    )

    db.add(db_test_case)
    await db.commit()
    await db.refresh(db_test_case)

    return db_test_case


@router.get("", response_model=List[TestCaseResponse])
async def list_test_cases(
    endpoint_id: int = Query(None, description="Filter by endpoint ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all test cases, optionally filtered by endpoint.
    """
    query = select(TestCase)

    if endpoint_id:
        query = query.where(TestCase.endpoint_id == endpoint_id)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    test_cases = result.scalars().all()

    return test_cases


@router.get("/{test_case_id}", response_model=TestCaseResponse)
async def get_test_case(
    test_case_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a test case by ID.
    """
    test_case = await get_test_case_or_404(test_case_id, db)
    return test_case


@router.put("/{test_case_id}", response_model=TestCaseResponse)
async def update_test_case(
    test_case_id: int,
    test_case_data: TestCaseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a test case.
    """
    test_case = await get_test_case_or_404(test_case_id, db)

    update_data = test_case_data.model_dump(exclude_unset=True)

    # Handle request_config update
    if "request_config" in update_data and update_data["request_config"]:
        update_data["request_config"] = test_case_data.request_config.model_dump()

    # Handle assertions update in expected_response
    if "assertions" in update_data and update_data["assertions"] is not None:
        update_data["expected_response"] = {
            "assertions": [a.model_dump() for a in test_case_data.assertions]
        }

    for key, value in update_data.items():
        if key == "assertions":
            continue  # Already handled above
        setattr(test_case, key, value)

    await db.commit()
    await db.refresh(test_case)

    return test_case


@router.delete("/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_case(
    test_case_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a test case.
    """
    test_case = await get_test_case_or_404(test_case_id, db)

    await db.delete(test_case)
    await db.commit()


@router.post("/execute", response_model=TestExecutionResponse)
async def execute_test_cases(
    execution_request: TestExecutionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute one or more test cases and return results.
    """
    if not execution_request.test_case_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="test_case_ids cannot be empty"
        )

    # Limit batch size to prevent unbounded execution
    MAX_BATCH_SIZE = 100
    if len(execution_request.test_case_ids) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size exceeds maximum limit of {MAX_BATCH_SIZE}"
        )

    executor = TestExecutor(db, base_url=execution_request.base_url)
    result = await executor.execute_batch(execution_request.test_case_ids)

    return result


@router.get("/{test_case_id}/results", response_model=List[TestResultResponse])
async def get_test_case_results(
    test_case_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical test results for a test case.
    """
    test_case = await get_test_case_or_404(test_case_id, db)

    from app.models.test_result import TestResult
    result = await db.execute(
        select(TestResult)
        .where(TestResult.test_case_id == test_case_id)
        .order_by(TestResult.executed_at.desc())
        .offset(skip)
        .limit(limit)
    )
    results = result.scalars().all()

    return results
