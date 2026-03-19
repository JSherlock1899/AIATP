from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import tempfile
import os

from app.core.database import get_db
from app.schemas.api_doc import (
    ApiDocImport, ApiDocResponse, ApiDocDetailResponse, ApiDocWithEndpoints,
    ApiEndpointResponse, OpenAPIParsedInfo
)
from app.services.openapi_parser import ApiDocService
from app.services.project_service import ProjectService
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/api-docs", tags=["api-docs"])


async def verify_project_access(project_id: int, user_id: int, db: AsyncSession) -> None:
    """Verify user has access to the project."""
    project_service = ProjectService(db)
    await project_service._verify_project_access(project_id, user_id)


@router.post("/import", response_model=ApiDocResponse, status_code=status.HTTP_201_CREATED)
async def import_api_doc(
    project_id: int,
    import_data: ApiDocImport,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Import an OpenAPI document (YAML or JSON format).

    The document can be provided as raw YAML/JSON content in the request body.
    Supports OpenAPI 3.0 and Swagger 2.0 formats.
    """
    await verify_project_access(project_id, current_user.id, db)

    service = ApiDocService(db)
    api_doc = await service.import_openapi(project_id, import_data)
    return api_doc


@router.post("/import/file", response_model=ApiDocResponse, status_code=status.HTTP_201_CREATED)
async def import_api_doc_file(
    project_id: int,
    file: UploadFile = File(...),
    name: str = Query(..., description="Name for the API document"),
    version: str = Query("1.0.0", description="Version of the API document"),
    description: str = Query(None, description="Description of the API document"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Import an OpenAPI document from a file upload.

    Supports YAML (.yaml, .yml) and JSON (.json) files.
    """
    await verify_project_access(project_id, current_user.id, db)

    # Read file content
    content = await file.read()

    # Detect and decode content
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded"
        )

    import_data = ApiDocImport(
        name=name,
        version=version,
        description=description,
        content=content_str
    )

    service = ApiDocService(db)
    api_doc = await service.import_openapi(project_id, import_data)
    return api_doc


@router.get("", response_model=List[ApiDocResponse])
async def list_api_docs(
    project_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all API documents for a project.
    """
    await verify_project_access(project_id, current_user.id, db)

    service = ApiDocService(db)
    docs = await service.list_docs(project_id, skip, limit)
    return docs


@router.get("/{doc_id}", response_model=ApiDocDetailResponse)
async def get_api_doc(
    project_id: int,
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get details of a specific API document.
    """
    await verify_project_access(project_id, current_user.id, db)

    service = ApiDocService(db)
    doc = await service.get_doc_by_id(doc_id, project_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API document not found"
        )

    # Get endpoints count
    endpoints = await service.get_doc_endpoints(doc_id, project_id, limit=0)

    return ApiDocDetailResponse(
        id=doc.id,
        project_id=doc.project_id,
        name=doc.name,
        version=doc.version,
        description=doc.description,
        file_path=doc.file_path,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        endpoints_count=len(endpoints)
    )


@router.get("/{doc_id}/info", response_model=OpenAPIParsedInfo)
async def get_doc_parse_info(
    project_id: int,
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get parsed information about an OpenAPI document.
    """
    await verify_project_access(project_id, current_user.id, db)

    service = ApiDocService(db)
    return await service.get_parsed_info(doc_id, project_id)


@router.get("/{doc_id}/endpoints", response_model=List[ApiEndpointResponse])
async def list_doc_endpoints(
    project_id: int,
    doc_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all endpoints for an API document.
    """
    await verify_project_access(project_id, current_user.id, db)

    service = ApiDocService(db)
    endpoints = await service.get_doc_endpoints(doc_id, project_id, skip, limit)
    return endpoints


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_doc(
    project_id: int,
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an API document and all its endpoints.
    """
    await verify_project_access(project_id, current_user.id, db)

    service = ApiDocService(db)
    await service.delete_doc(doc_id, project_id)
