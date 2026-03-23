import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ParsedEndpoint:
    """Represents a parsed API endpoint."""
    path: str
    method: str
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: List[Dict] = None
    request_body: Optional[Dict] = None
    responses: List[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "method": self.method,
            "summary": self.summary,
            "description": self.description,
            "parameters": self.parameters or [],
            "request_body": self.request_body,
            "responses": self.responses or []
        }

    def __getitem__(self, key: str) -> Any:
        """Allow dict-style access for backward compatibility."""
        return getattr(self, key)

    def keys(self):
        return ["path", "method", "summary", "description", "parameters", "request_body", "responses"]


class SpringBootRegexParser:
    """Parser for Spring Boot Java source code using regex."""

    # HTTP Method mapping
    METHOD_ANNOTATIONS = {
        "GetMapping": "GET",
        "PostMapping": "POST",
        "PutMapping": "PUT",
        "DeleteMapping": "DELETE",
        "PatchMapping": "PATCH",
        "HeadMapping": "HEAD",
        "OptionsMapping": "OPTIONS",
        "RequestMapping": "GET"  # Default, may be overridden by method attribute
    }

    # Regex patterns
    CLASS_CONTROLLER_PATTERN = re.compile(
        r'@(?:Rest)?Controller\s*(?:\s*@\s*RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\'])',
        re.MULTILINE
    )

    # Pattern for method annotations: @GetMapping("/path") or @GetMapping(value="/path") or @GetMapping
    METHOD_PATTERN = re.compile(
        r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|HeadMapping|OptionsMapping|RequestMapping)'
        r'(?:\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']\s*\))?',
        re.MULTILINE
    )

    # Pattern to remove single-line comments to avoid matching annotations in comments
    COMMENT_LINE_PATTERN = re.compile(r'^\s*//.*$', re.MULTILINE)

    REQUEST_BODY_PATTERN = re.compile(r'@RequestBody')

    # DTO class name patterns - match class/record declarations
    DTO_NAME_PATTERNS = [
        re.compile(r'(?:public\s+)?class\s+(\w*(?:Request|Response|DTO|Vo|VO|Entity|Model)\w*)\s*(?:extends|implements)?'),
        re.compile(r'(?:public\s+)?record\s+(\w*(?:Request|Response|DTO|Vo|VO)\w*)\s*\('),
    ]

    def __init__(self):
        """Initialize parser with DTO index."""
        self.dto_index: Dict[str, str] = {}  # DTO name -> file path
        self.java_files: List[str] = []
        self.source_path: str = ""

    @staticmethod
    def validate_path(path: str) -> str:
        """Validate path doesn't contain traversal."""
        if ".." in path:
            raise ValueError("Path traversal not allowed")
        if not os.path.isabs(path):
            raise ValueError("Absolute path required")
        return path

    @staticmethod
    def scan_java_files(source_path: str, max_depth: int = 20) -> List[str]:
        """Recursively scan for .java files."""
        java_files = []
        source = Path(source_path)

        if not source.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")

        for root, dirs, files in os.walk(source):
            # Check depth
            depth = root[len(source_path):].count(os.sep)
            if depth >= max_depth:
                dirs.clear()
                continue

            for file in files:
                if file.endswith(".java"):
                    java_files.append(os.path.join(root, file))

        return java_files

    def build_dto_index(self, java_files: List[str]) -> None:
        """Build an index of DTO class names to their file paths."""
        self.dto_index = {}
        self.java_files = java_files

        for java_file in java_files:
            try:
                file_size = os.path.getsize(java_file)
                if file_size > MAX_FILE_SIZE:
                    continue

                with open(java_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Remove comments
                content = self.COMMENT_LINE_PATTERN.sub('', content)

                # Look for DTO class definitions
                for pattern in self.DTO_NAME_PATTERNS:
                    for match in pattern.finditer(content):
                        dto_name = match.group(1)
                        # Store lowercase for case-insensitive lookup
                        self.dto_index[dto_name] = java_file
                        self.dto_index[dto_name.lower()] = java_file
            except Exception:
                continue

    def _get_dto_file_path(self, dto_name: str) -> Optional[str]:
        """Get the file path for a DTO class by name."""
        # Try exact match first
        if dto_name in self.dto_index:
            return self.dto_index[dto_name]
        # Try lowercase match
        if dto_name.lower() in self.dto_index:
            return self.dto_index[dto_name.lower()]
        return None

    def _read_dto_content(self, dto_name: str) -> Optional[str]:
        """Read the content of a DTO file."""
        file_path = self._get_dto_file_path(dto_name)
        if not file_path:
            return None

        try:
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    def parse_content(self, content: str) -> List[ParsedEndpoint]:
        """Parse Java source code content and extract endpoints."""
        endpoints = []

        # Remove single-line comments to avoid matching annotations in comments
        # This fixes Critical 1: regex matches annotations inside comments
        content_without_comments = self.COMMENT_LINE_PATTERN.sub('', content)

        # Find class-level @RequestMapping prefix
        class_match = self.CLASS_CONTROLLER_PATTERN.search(content_without_comments)
        class_path = class_match.group(1) if class_match else ""

        # If no @RestController or @Controller with @RequestMapping, skip
        if (not class_path and "@RestController" in content_without_comments) or "@Controller" in content_without_comments:
            # Check if there's a standalone @RequestMapping at class level
            class_request_mapping = re.search(
                r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
                content_without_comments
            )
            if class_request_mapping:
                class_path = class_request_mapping.group(1)

        # If still no class path, try to find package as fallback
        if not class_path:
            package_match = re.search(r'package\s+([\w.]+);', content_without_comments)
            if package_match:
                class_path = "/" + package_match.group(1).replace(".", "/")

        # Find all method-level annotations
        # First pass: collect all raw matches
        raw_matches = []
        for match in self.METHOD_PATTERN.finditer(content_without_comments):
            annotation_name = match.group(1)
            method_path = match.group(2) if match.group(2) else ""
            http_method = self.METHOD_ANNOTATIONS.get(annotation_name, "GET")

            # Skip @RequestMapping at class level (before any method definitions)
            if annotation_name == "RequestMapping":
                # Check if this @RequestMapping is at class level by seeing if it appears
                # before any public/private/protected method
                before_content = content_without_comments[:match.start()]
                last_modifier = re.search(r'\b(public|private|protected)\s+', before_content)
                if last_modifier is None:
                    # Class-level @RequestMapping, skip
                    continue

                # It's a method-level @RequestMapping, check for method attribute
                method_match = re.search(
                    r'method\s*=\s*HttpMethod\.(\w+)',
                    content_without_comments[match.start():match.start() + 200]
                )
                if method_match:
                    http_method = method_match.group(1)

            # Get method boundaries for deduplication
            method_start = match.start()
            method_end = self._find_method_end(content_without_comments, method_start)

            raw_matches.append({
                'annotation_name': annotation_name,
                'method_path': method_path,
                'http_method': http_method,
                'method_start': method_start,
                'method_end': method_end,
                'match': match
            })

        # Deduplicate: for each method block, if there are multiple annotations for the same
        # HTTP method (e.g., both @GetMapping and @GetMapping("/path")), only keep the one with path
        deduplicated = []
        for i, current in enumerate(raw_matches):
            has_long_form = any(
                other['http_method'] == current['http_method'] and
                other['method_path'] and  # has a path
                abs(other['method_start'] - current['method_start']) < 200  # same method block
                for other in raw_matches if other is not current
            )
            # Skip short form if there's also a long form for the same HTTP method
            if not current['method_path'] and has_long_form:
                continue
            deduplicated.append(current)

        # Second pass: create endpoints from deduplicated matches
        for match_data in deduplicated:
            annotation_name = match_data['annotation_name']
            method_path = match_data['method_path']
            http_method = match_data['http_method']
            method_start = match_data['method_start']
            method_end = match_data['method_end']
            match = match_data['match']

            # Combine class path and method path
            full_path = self._combine_paths(class_path, method_path)

            # Extract parameters
            method_content = content_without_comments[method_start:method_end]

            parameters = self._extract_parameters(method_content)
            # Pass full file content to extract DTO fields from class definitions at file level
            request_body_info = self._extract_request_body_info(content_without_comments, method_content)

            endpoint = ParsedEndpoint(
                path=full_path,
                method=http_method,
                parameters=parameters,
                request_body=request_body_info
            )
            endpoints.append(endpoint)

        return endpoints

    def _combine_paths(self, class_path: str, method_path: str) -> str:
        """Combine class and method paths."""
        if not class_path:
            return method_path
        if not method_path:
            return class_path

        # Ensure single slash between paths
        class_path = class_path.rstrip("/")
        if method_path.startswith("/"):
            return class_path + method_path
        return f"{class_path}/{method_path}"

    def _extract_request_body_info(self, full_content: str, method_content: str) -> Optional[Dict]:
        """Extract @RequestBody parameter information including DTO class and fields."""
        # Pattern: @RequestBody optionally followed by annotations (like @Valid), then type and name
        # Matches: @RequestBody UserRequest request
        # Matches: @RequestBody @Valid UserRequest request
        request_body_pattern = re.compile(
            r'@RequestBody(?:\s+(?:@?\w+))*?\s+(\w+)\s+(\w+)',
            re.MULTILINE
        )
        match = request_body_pattern.search(method_content)
        if match:
            dto_type = match.group(1)  # e.g., CreateWorkOrderRequest
            param_name = match.group(2)  # e.g., dto

            # Try to find the DTO class definition in the full file content to extract fields
            fields = self._extract_dto_fields(full_content, dto_type)

            return {
                "type": dto_type,
                "name": param_name,
                "required": True,
                "fields": fields
            }
        return None

    def _extract_dto_fields(self, content: str, dto_name: str) -> List[Dict]:
        """Try to extract fields from a DTO class definition.

        First searches in the current file content, then falls back to
        cross-file search using the DTO index.
        """
        fields = []

        # First try: find DTO in current file content
        fields = self._extract_dto_fields_from_content(content, dto_name)
        if fields:
            return fields

        # Second try: look up DTO in indexed files
        dto_content = self._read_dto_content(dto_name)
        if dto_content:
            # Remove comments from DTO content
            dto_content = self.COMMENT_LINE_PATTERN.sub('', dto_content)
            return self._extract_dto_fields_from_content(dto_content, dto_name)

        return fields

    def _extract_dto_fields_from_content(self, content: str, dto_name: str) -> List[Dict]:
        """Extract fields from DTO class definition in given content."""
        fields = []

        # Find DTO class definition (class or record)
        # Pattern handles: class UserRequest { }, class UserRequest extends Base { }, record UserRequest(...)
        dto_pattern = re.compile(
            rf'(?:class|record)\s+{re.escape(dto_name)}\s*(?:extends\s+\w+)?\s*(?:implements\s+\w+)?\s*\{{?([^}}]*)\}}?',
            re.MULTILINE | re.DOTALL
        )
        dto_match = dto_pattern.search(content)
        if not dto_match:
            return fields

        dto_body = dto_match.group(1)

        # Pattern for field declarations: private Type fieldName;
        field_pattern = re.compile(
            r'private\s+(\w+(?:<[^>]+>)?)\s+(\w+)\s*;',
            re.MULTILINE
        )

        for match in field_pattern.finditer(dto_body):
            field_type = match.group(1)
            field_name = match.group(2)
            fields.append({
                "name": field_name,
                "type": field_type
            })

        return fields

    def _extract_parameters(self, method_content: str) -> List[Dict]:
        """Extract @PathVariable and @RequestParam parameters."""
        parameters = []

        # Find all @PathVariable annotations and extract parameter names
        # Pattern: @PathVariable or @PathVariable(...) followed by type and name
        path_var_pattern = re.compile(
            r'@PathVariable'
            r'(?:\s*\([^)]*\))?'  # Optional arguments like (value="id") or (required=false)
            r'\s+(\w+)\s+(\w+)',   # Type and name: Long id
            re.MULTILINE
        )
        for match in path_var_pattern.finditer(method_content):
            param_name = match.group(2)  # Second group is the parameter name
            parameters.append({
                "name": param_name,
                "location": "path",
                "required": True
            })

        # Also check for @PathVariable with explicit name only: @PathVariable("id")
        path_var_explicit = re.compile(
            r'@PathVariable\s*\(\s*(?:value\s*=\s*)?["\'](\w+)["\']',
            re.MULTILINE
        )
        for match in path_var_explicit.finditer(method_content):
            param_name = match.group(1)
            # Check if this param is already added
            if not any(p["name"] == param_name for p in parameters):
                parameters.append({
                    "name": param_name,
                    "location": "path",
                    "required": True
                })

        # Find all @RequestParam annotations and extract parameter names
        # Pattern: @RequestParam or @RequestParam(...) followed by type and name
        request_param_pattern = re.compile(
            r'@RequestParam'
            r'(?:\s*\([^)]*\))?'  # Optional arguments like (required=false)
            r'\s+(\w+)\s+(\w+)',  # Type and name: String name
            re.MULTILINE
        )
        for match in request_param_pattern.finditer(method_content):
            param_name = match.group(2)  # Second group is the parameter name
            # Check if required
            full_match = match.group(0)
            required = "required" not in full_match or "required=false" not in full_match
            parameters.append({
                "name": param_name,
                "location": "query",
                "required": required
            })

        # Also check for @RequestParam with explicit name only: @RequestParam("name") or @RequestParam(name="name")
        request_param_explicit = re.compile(
            r'@RequestParam\s*\(\s*(?:name\s*=\s*)?["\'](\w+)["\']',
            re.MULTILINE
        )
        for match in request_param_explicit.finditer(method_content):
            param_name = match.group(1)
            # Check if this param is already added
            if not any(p["name"] == param_name for p in parameters):
                # Check if required
                start = max(0, match.start() - 50)
                end = min(len(method_content), match.end() + 50)
                context = method_content[start:end]
                required = "required" not in context or "required=false" not in context
                parameters.append({
                    "name": param_name,
                    "location": "query",
                    "required": required
                })

        return parameters

    def _find_method_end(self, content: str, start: int) -> int:
        """Find the approximate end of a method containing the annotation."""
        # Find next method or class definition
        next_method = re.search(r'^\s*(?:public|private|protected|\w)\s+\w+\s+\w+\s*\(', content[start+100:], re.MULTILINE)
        next_class = re.search(r'^\s*class\s+\w+', content[start+100:], re.MULTILINE)

        end = len(content)
        if next_method:
            end = min(end, start + 100 + next_method.start())
        if next_class:
            end = min(end, start + 100 + next_class.start())

        return end

    def parse_file(self, file_path: str) -> List[ParsedEndpoint]:
        """Parse a Java file using the pre-built DTO index."""
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large ({file_size} bytes): {file_path}. Max size is {MAX_FILE_SIZE} bytes")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.parse_content(content)


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit per file


def parse_java_file(file_path: str) -> List[ParsedEndpoint]:
    """Convenience function to parse a single Java file."""
    # Check file size before reading
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"File too large ({file_size} bytes): {file_path}. Max size is {MAX_FILE_SIZE} bytes")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    parser = SpringBootRegexParser()
    return parser.parse_content(content)


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime
import logging

from app.models.source_code_project import SourceCodeProject, ParseStatus
from app.models.api_endpoint import ApiEndpoint, HttpMethod

log = logging.getLogger(__name__)


class SourceCodeParseService:
    """Service for parsing local source code projects."""

    MAX_DEPTH = 20

    def __init__(self, db: AsyncSession):
        self.db = db

    def validate_source_path(self, path: str) -> str:
        """Validate and sanitize source path."""
        path = path.strip()

        # Check for null bytes (path traversal attempt)
        if "\0" in path:
            raise ValueError("Null bytes not allowed in path")

        # Check for URL-encoded path traversal
        if "%2e%2e" in path.lower() or "%252e" in path.lower():
            raise ValueError("URL-encoded path traversal not allowed")

        # Check for path traversal
        if ".." in path:
            raise ValueError("Path traversal not allowed")

        # Check for Windows-style path traversal
        if "..\\" in path:
            raise ValueError("Windows-style path traversal not allowed")

        # Check absolute path
        if not os.path.isabs(path):
            raise ValueError("Absolute path required")

        # Check exists
        if not os.path.exists(path):
            raise FileNotFoundError(f"Source path does not exist: {path}")

        return path

    async def create_project(
        self, project_id: int, name: str, source_path: str
    ) -> SourceCodeProject:
        """Create a new source code project."""
        # Validate path
        validated_path = self.validate_source_path(source_path)

        # Check for existing project with same name
        result = await self.db.execute(
            select(SourceCodeProject).where(
                SourceCodeProject.project_id == project_id,
                SourceCodeProject.name == name
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError(f"Project with name '{name}' already exists")

        project = SourceCodeProject(
            project_id=project_id,
            name=name,
            source_path=validated_path,
            language="spring-boot",
            status=ParseStatus.PENDING
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)

        log.info(f"Created source code project '{name}' at {validated_path}")
        return project

    async def parse_project(self, project_id: int) -> SourceCodeProject:
        """Parse a source code project and extract endpoints."""
        result = await self.db.execute(
            select(SourceCodeProject).where(SourceCodeProject.id == project_id)
        )
        project = result.scalar_one_or_none()

        if not project:
            raise ValueError(f"Source code project not found: {project_id}")

        try:
            # Update status inside try block to avoid orphaned PARSING state
            project.status = ParseStatus.PARSING
            await self.db.commit()

            # Scan for Java files
            parser = SpringBootRegexParser()
            java_files = parser.scan_java_files(project.source_path, self.MAX_DEPTH)

            if not java_files:
                project.status = ParseStatus.FAILED
                project.error_message = "No Java files found in source path"
                await self.db.commit()
                return project

            # Build DTO index for cross-file field extraction
            parser.source_path = project.source_path
            parser.build_dto_index(java_files)
            log.info(f"Built DTO index with {len(parser.dto_index)} entries from {len(java_files)} files")

            # Parse each file using the same parser instance (has DTO index)
            all_endpoints = []
            failed_files = []
            for java_file in java_files:
                try:
                    endpoints = parser.parse_file(java_file)
                    all_endpoints.extend(endpoints)
                except Exception as e:
                    failed_files.append((java_file, str(e)))
                    log.warning(f"Failed to parse {java_file}: {e}")
                    continue

            # Log summary of failed files if any
            if failed_files:
                log.warning(f"Failed to parse {len(failed_files)}/{len(java_files)} files: {[f[0] for f in failed_files]}")

            # Create ApiDoc entry for this source project
            from app.models.api_doc import ApiDoc
            api_doc = ApiDoc(
                project_id=project.project_id,
                name=f"{project.name} (Source)",
                version="1.0.0",
                description=f"Auto-parsed from {project.source_path}",
                content="",  # No raw content for source code
                parsed_data={"source_files": len(java_files)}
            )
            self.db.add(api_doc)
            await self.db.flush()

            # Create endpoints
            for endpoint_data in all_endpoints:
                endpoint = ApiEndpoint(
                    api_doc_id=api_doc.id,
                    source_code_project_id=project.id,
                    path=endpoint_data.path,
                    method=HttpMethod[endpoint_data.method],
                    summary=endpoint_data.summary,
                    description=endpoint_data.description,
                    request_body=endpoint_data.request_body,
                    request_params=endpoint_data.parameters,
                    responses=endpoint_data.responses
                )
                self.db.add(endpoint)

            # Update project status
            project.status = ParseStatus.COMPLETED
            project.endpoints_count = len(all_endpoints)
            project.parsed_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(project)

            log.info(
                f"Parsed source code project '{project.name}': "
                f"{len(java_files)} files, {len(all_endpoints)} endpoints"
            )

        except Exception as e:
            project.status = ParseStatus.FAILED
            project.error_message = str(e)
            await self.db.commit()
            log.error(f"Failed to parse source code project {project_id}: {e}")

        return project

    async def get_project(self, project_id: int) -> Optional[SourceCodeProject]:
        """Get a source code project by ID."""
        result = await self.db.execute(
            select(SourceCodeProject).where(SourceCodeProject.id == project_id)
        )
        return result.scalar_one_or_none()

    async def list_projects(self, project_id: int, skip: int = 0, limit: int = 100) -> List[SourceCodeProject]:
        """List source code projects for a given project."""
        result = await self.db.execute(
            select(SourceCodeProject)
            .where(SourceCodeProject.project_id == project_id)
            .offset(skip)
            .limit(limit)
            .order_by(SourceCodeProject.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_project_endpoints(
        self, source_project_id: int, skip: int = 0, limit: int = 100
    ) -> List[ApiEndpoint]:
        """Get all endpoints for a source code project."""
        result = await self.db.execute(
            select(ApiEndpoint)
            .where(ApiEndpoint.source_code_project_id == source_project_id)
            .offset(skip)
            .limit(limit)
            .order_by(ApiEndpoint.path, ApiEndpoint.method)
        )
        return list(result.scalars().all())

    async def delete_project(self, project_id: int) -> None:
        """Delete a source code project and its endpoints."""
        result = await self.db.execute(
            select(SourceCodeProject).where(SourceCodeProject.id == project_id)
        )
        project = result.scalar_one_or_none()

        if not project:
            raise ValueError(f"Source code project not found: {project_id}")

        # Delete associated endpoints
        await self.db.execute(
            delete(ApiEndpoint).where(ApiEndpoint.source_code_project_id == project_id)
        )

        # Delete associated api_doc (one-to-one via source_code_project relationship)
        if project.api_doc:
            await self.db.delete(project.api_doc)

        await self.db.delete(project)
        await self.db.commit()

        log.info(f"Deleted source code project: {project_id}")
