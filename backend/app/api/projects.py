from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectWithMembers, ProjectMemberResponse
from app.services.project_service import ProjectService
from app.api.auth import get_guest_user
from app.models.user import User
from app.models.project import ProjectRole

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_guest_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new project. The current user becomes the owner.
    """
    service = ProjectService(db)
    project = await service.create_project(project_data, current_user.id)
    return project


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_guest_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all projects the current user has access to.
    """
    service = ProjectService(db)
    projects = await service.get_user_projects(current_user.id)
    return projects


@router.get("/{project_id}", response_model=ProjectWithMembers)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_guest_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a project by ID with its members. User must be a member.
    """
    service = ProjectService(db)
    project = await service._verify_project_access(project_id, current_user.id)
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_guest_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a project. Only owner or admin can update.
    """
    service = ProjectService(db)
    project = await service.update_project(project_id, project_data, current_user.id)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_guest_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a project. Only owner can delete.
    """
    service = ProjectService(db)
    await service.delete_project(project_id, current_user.id)


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: int,
    user_id: int,
    role: ProjectRole = ProjectRole.VIEWER,
    current_user: User = Depends(get_guest_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a member to a project. Only owner or admin can add members.
    """
    service = ProjectService(db)
    member = await service.add_member(project_id, user_id, role, current_user.id)
    return member


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: int,
    user_id: int,
    current_user: User = Depends(get_guest_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a member from a project. Only owner or admin can remove members.
    """
    service = ProjectService(db)
    await service.remove_member(project_id, user_id, current_user.id)
