from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from typing import List

from app.models.project import Project, ProjectMember, ProjectRole
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_project_by_id(self, project_id: int) -> Project | None:
        result = await self.db.execute(
            select(Project)
            .options(selectinload(Project.members))
            .where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def _verify_project_access(self, project_id: int, user_id: int, require_role: str = None) -> Project:
        """Verify user has access to project and optionally has required role."""
        project = await self.get_project_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        member = next((m for m in project.members if m.user_id == user_id), None)
        if not member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
        if require_role:
            if require_role == "owner" and project.owner_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can perform this action")
            if require_role == "admin" and project.owner_id != user_id and member.role != ProjectRole.ADMIN:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or owner required")
        return project

    async def get_project_by_key(self, project_key: str) -> Project | None:
        result = await self.db.execute(
            select(Project)
            .options(selectinload(Project.members))
            .where(Project.project_key == project_key.upper())
        )
        return result.scalar_one_or_none()

    async def list_projects(self, skip: int = 0, limit: int = 100) -> List[Project]:
        result = await self.db.execute(
            select(Project)
            .options(selectinload(Project.members))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_project(self, project_data: ProjectCreate, owner_id: int) -> Project:
        existing = await self.get_project_by_key(project_data.project_key)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project key already exists"
            )

        db_project = Project(
            name=project_data.name,
            description=project_data.description,
            project_key=project_data.project_key.upper(),
            owner_id=owner_id
        )
        self.db.add(db_project)
        await self.db.flush()

        owner_member = ProjectMember(
            project_id=db_project.id,
            user_id=owner_id,
            role=ProjectRole.OWNER
        )
        self.db.add(owner_member)

        await self.db.commit()
        await self.db.refresh(db_project)
        return db_project

    async def update_project(self, project_id: int, project_data: ProjectUpdate, user_id: int) -> Project:
        project = await self._verify_project_access(project_id, user_id, require_role="admin")

        if project_data.name is not None:
            project.name = project_data.name
        if project_data.description is not None:
            project.description = project_data.description

        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def delete_project(self, project_id: int, user_id: int) -> None:
        project = await self._verify_project_access(project_id, user_id, require_role="owner")

        # Delete all members first
        for member in project.members:
            await self.db.delete(member)

        await self.db.delete(project)
        await self.db.commit()

    async def add_member(self, project_id: int, user_id: int, role: ProjectRole, requester_id: int) -> ProjectMember:
        project = await self._verify_project_access(project_id, requester_id, require_role="admin")

        result = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this project"
            )

        member = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role=role
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def remove_member(self, project_id: int, user_id: int, requester_id: int) -> None:
        await self._verify_project_access(project_id, requester_id, require_role="admin")

        result = await self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )

        if member.role == ProjectRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the owner from the project"
            )

        await self.db.delete(member)
        await self.db.commit()

    async def get_user_projects(self, user_id: int) -> List[Project]:
        result = await self.db.execute(
            select(Project)
            .join(ProjectMember)
            .where(ProjectMember.user_id == user_id)
            .options(selectinload(Project.members))
        )
        return list(result.scalars().all())
