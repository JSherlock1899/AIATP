import yaml
import json
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fastapi import HTTPException, status
import logging

from app.models.api_doc import ApiDoc
from app.models.api_endpoint import ApiEndpoint, HttpMethod
from app.schemas.api_doc import (
    ApiDocCreate, ApiDocImport, OpenAPIParsedInfo,
    EndpointParameter, EndpointRequestBody, EndpointResponse
)

log = logging.getLogger(__name__)


def _safe_yaml_load(content: str) -> Dict[str, Any]:
    """
    Parse YAML content safely using SafeLoader.
    SafeLoader prevents code execution and alias expansion (billion laughs attack).
    """
    return yaml.load(content, Loader=yaml.SafeLoader)


class OpenAPIParser:
    """Service for parsing OpenAPI 3.0 / Swagger YAML/JSON documents."""

    SUPPORTED_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}

    def __init__(self, db: AsyncSession):
        self.db = db

    def parse_content(self, content: str) -> Dict[str, Any]:
        """
        Parse YAML or JSON content into a dictionary.
        Raises ValueError if content is invalid.
        """
        content = content.strip()

        # Try JSON first
        if content.startswith("{"):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON: malformed or unparseable")

        # Try YAML with SafeLoader to prevent billion laughs attack
        try:
            return _safe_yaml_load(content)
        except yaml.YAMLError:
            raise ValueError("Invalid YAML: malformed or unparseable")

    def detect_format(self, content: str) -> str:
        """Detect whether content is YAML or JSON."""
        content = content.strip()
        if content.startswith("{"):
            return "json"
        return "yaml"

    def validate_openapi(self, data: Dict[str, Any]) -> Tuple[str, str]:
        """
        Validate that the data is a valid OpenAPI document.
        Returns (openapi_version, info_version).
        Raises ValueError if not valid.
        """
        openapi_version = data.get("openapi", data.get("swagger"))
        if not openapi_version:
            raise ValueError("Missing 'openapi' or 'swagger' field")

        # Check if it's a supported version
        if openapi_version.startswith("3."):
            spec_version = "3.0"
        elif openapi_version.startswith("2."):
            spec_version = "2.0"
        else:
            raise ValueError(f"Unsupported OpenAPI version: {openapi_version}")

        info = data.get("info", {})
        if not info:
            raise ValueError("Missing 'info' field")

        title = info.get("title", "Untitled")
        version = info.get("version", "1.0.0")

        return openapi_version, f"{title} v{version}"

    def extract_endpoints(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract all endpoints from an OpenAPI 3.0 document.
        Returns a list of endpoint dictionaries.
        """
        endpoints = []
        paths = data.get("paths", {})

        for path, path_item in paths.items():
            for method in self.SUPPORTED_METHODS:
                operation = path_item.get(method)
                if not operation:
                    continue

                endpoint = self._parse_operation(path, method.upper(), operation, data)
                endpoints.append(endpoint)

        return endpoints

    def _parse_operation(
        self, path: str, method: str, operation: Dict[str, Any], spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse a single operation into an endpoint dictionary."""
        # Get parameters from path item level
        path_params = {p["name"]: p for p in path_item_params(path, spec)}

        # Get operation-level parameters
        operation_params = operation.get("parameters", [])

        # Merge parameters (operation level overrides path level)
        all_params = {**path_params}
        for param in operation_params:
            all_params[param["name"]] = param

        parameters = []
        for param_name, param in all_params.items():
            parameters.append(EndpointParameter(
                name=param_name,
                location=param.get("in", "query"),
                required=param.get("required", False),
                description=param.get("description"),
                param_schema=param.get("schema")
            ))

        # Parse request body (OpenAPI 3.0)
        request_body = None
        request_body_obj = operation.get("requestBody")
        if request_body_obj:
            content = request_body_obj.get("content", {})
            json_content = content.get("application/json", {})
            request_body = EndpointRequestBody(
                description=request_body_obj.get("description"),
                required=request_body_obj.get("required", False),
                content_type="application/json",
                body_schema=json_content.get("schema")
            )

        # Parse responses
        responses = []
        for status_code, response_obj in operation.get("responses", {}).items():
            content = response_obj.get("content", {})
            json_content = content.get("application/json", {})
            responses.append(EndpointResponse(
                status_code=int(status_code.replace("x", "0").split(".")[0]) if status_code != "default" else 500,
                description=response_obj.get("description"),
                response_schema=json_content.get("schema")
            ))

        return {
            "path": path,
            "method": method,
            "summary": operation.get("summary"),
            "description": operation.get("description"),
            "operation_id": operation.get("operationId"),
            "parameters": parameters,
            "request_body": request_body,
            "responses": responses
        }


def path_item_params(path: str, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract path-level parameters for a given path."""
    path_item = spec.get("paths", {}).get(path, {})
    params = path_item.get("parameters", [])

    # Filter to only return path-level parameters
    return [param for param in params if param.get("in") == "path"]


class ApiDocService:
    """Service for managing API documents."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.parser = OpenAPIParser(db)

    async def import_openapi(
        self, project_id: int, import_data: ApiDocImport
    ) -> ApiDoc:
        """
        Import an OpenAPI document from YAML/JSON content.
        Parses the content, validates it, extracts endpoints, and saves to database.
        """
        if not import_data.content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OpenAPI document content is required"
            )

        # Parse content
        try:
            parsed_data = self.parser.parse_content(import_data.content)
        except ValueError as e:
            log.warning(f"Failed to parse OpenAPI document for project {project_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to parse document: malformed or unsupported format"
            )

        # Validate OpenAPI format
        try:
            openapi_version, version_info = self.parser.validate_openapi(parsed_data)
        except ValueError as e:
            log.warning(f"Invalid OpenAPI document for project {project_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OpenAPI document: missing or unsupported version"
            )

        # Create API document
        api_doc = ApiDoc(
            project_id=project_id,
            name=import_data.name,
            version=import_data.version,
            description=import_data.description or parsed_data.get("info", {}).get("description"),
            content=import_data.content,
            parsed_data=parsed_data
        )
        self.db.add(api_doc)
        await self.db.flush()

        # Extract and save endpoints
        endpoints_data = self.parser.extract_endpoints(parsed_data)
        for endpoint_data in endpoints_data:
            request_body_dict = None
            if endpoint_data["request_body"]:
                request_body_dict = endpoint_data["request_body"].model_dump()

            endpoint = ApiEndpoint(
                api_doc_id=api_doc.id,
                path=endpoint_data["path"],
                method=HttpMethod[endpoint_data["method"]],
                summary=endpoint_data["summary"],
                description=endpoint_data["description"],
                operation_id=endpoint_data["operation_id"],
                request_body=request_body_dict,
                request_params=[p.model_dump() for p in endpoint_data["parameters"]],
                responses=[r.model_dump() for r in endpoint_data["responses"]]
            )
            self.db.add(endpoint)

        await self.db.commit()
        await self.db.refresh(api_doc)

        log.info(
            f"Imported OpenAPI document '{import_data.name}' v{import_data.version} "
            f"for project {project_id} with {len(endpoints_data)} endpoints"
        )

        return api_doc

    async def get_doc_by_id(self, doc_id: int, project_id: int) -> Optional[ApiDoc]:
        """Get an API document by ID, verifying project ownership."""
        result = await self.db.execute(
            select(ApiDoc).where(ApiDoc.id == doc_id, ApiDoc.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def list_docs(self, project_id: int, skip: int = 0, limit: int = 100) -> List[ApiDoc]:
        """List all API documents for a project."""
        result = await self.db.execute(
            select(ApiDoc)
            .where(ApiDoc.project_id == project_id)
            .offset(skip)
            .limit(limit)
            .order_by(ApiDoc.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_doc_endpoints(
        self, doc_id: int, project_id: int, skip: int = 0, limit: int = 100
    ) -> List[ApiEndpoint]:
        """Get all endpoints for an API document."""
        # First verify the doc belongs to the project
        doc = await self.get_doc_by_id(doc_id, project_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API document not found"
            )

        result = await self.db.execute(
            select(ApiEndpoint)
            .where(ApiEndpoint.api_doc_id == doc_id)
            .offset(skip)
            .limit(limit)
            .order_by(ApiEndpoint.path, ApiEndpoint.method)
        )
        return list(result.scalars().all())

    async def delete_doc(self, doc_id: int, project_id: int) -> None:
        """Delete an API document and its endpoints."""
        doc = await self.get_doc_by_id(doc_id, project_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API document not found"
            )

        # Delete endpoints first
        await self.db.execute(
            delete(ApiEndpoint).where(ApiEndpoint.api_doc_id == doc_id)
        )

        # Delete the document
        await self.db.delete(doc)
        await self.db.commit()

    async def get_parsed_info(self, doc_id: int, project_id: int) -> OpenAPIParsedInfo:
        """Get parsed information about an OpenAPI document."""
        doc = await self.get_doc_by_id(doc_id, project_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API document not found"
            )

        parsed_data = doc.parsed_data
        if not parsed_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document has no parsed data"
            )

        info = parsed_data.get("info", {})
        paths = list(parsed_data.get("paths", {}).keys())

        # Count endpoints
        endpoints = await self.get_doc_endpoints(doc_id, project_id, limit=10000)

        return OpenAPIParsedInfo(
            title=info.get("title", "Untitled"),
            version=info.get("version", "1.0.0"),
            description=info.get("description"),
            openapi_version=parsed_data.get("openapi", parsed_data.get("swagger", "unknown")),
            endpoints_count=len(endpoints),
            paths=paths
        )
