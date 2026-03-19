from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.schemas.source_code_project import (
    SourceCodeParseRequest, SourceCodeParseResponse, SourceCodeProjectResponse
)
from app.services.source_code_parser import SourceCodeParseService
from app.services.project_service import ProjectService
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/source-code", tags=["source-code"])


async def verify_project_access(project_id: int, user_id: int, db: AsyncSession) -> None:
    """Verify user has access to the project."""
    project_service = ProjectService(db)
    await project_service._verify_project_access(project_id, user_id)


@router.post("/parse", response_model=SourceCodeParseResponse, status_code=status.HTTP_201_CREATED)
async def parse_source_code(
    project_id: int,
    request: SourceCodeParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start parsing a local source code project.

    Validates the path and starts the async parsing process.
    """
    await verify_project_access(project_id, current_user.id, db)

    if request.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id in body must match path parameter"
        )

    service = SourceCodeParseService(db)

    try:
        # Create project record
        project = await service.create_project(
            project_id=project_id,
            name=request.name,
            source_path=request.source_path
        )

        # Start parsing synchronously for MVP (can be made async later)
        project = await service.parse_project(project.id)

        return SourceCodeParseResponse(
            id=project.id,
            name=project.name,
            source_path=project.source_path,
            status=project.status.value,
            endpoints_count=project.endpoints_count,
            message=project.error_message
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("", response_model=List[SourceCodeProjectResponse])
async def list_source_code_projects(
    project_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all source code projects for a project.
    """
    await verify_project_access(project_id, current_user.id, db)

    service = SourceCodeParseService(db)
    projects = await service.list_projects(project_id, skip, limit)
    return projects


@router.get("/{source_project_id}", response_model=SourceCodeProjectResponse)
async def get_source_code_project(
    project_id: int,
    source_project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get details of a specific source code project.
    """
    await verify_project_access(project_id, current_user.id, db)

    service = SourceCodeParseService(db)
    project = await service.get_project(source_project_id)

    if not project or project.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source code project not found"
        )

    return project


@router.get("/{source_project_id}/endpoints")
async def list_source_code_endpoints(
    project_id: int,
    source_project_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all endpoints for a source code project.
    """
    await verify_project_access(project_id, current_user.id, db)

    service = SourceCodeParseService(db)
    project = await service.get_project(source_project_id)

    if not project or project.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source code project not found"
        )

    endpoints = await service.get_project_endpoints(source_project_id, skip, limit)
    return endpoints


@router.delete("/{source_project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source_code_project(
    project_id: int,
    source_project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a source code project and its endpoints.
    """
    await verify_project_access(project_id, current_user.id, db)

    service = SourceCodeParseService(db)
    project = await service.get_project(source_project_id)

    if not project or project.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source code project not found"
        )

    await service.delete_project(source_project_id)
