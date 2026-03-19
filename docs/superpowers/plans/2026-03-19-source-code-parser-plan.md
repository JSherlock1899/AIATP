# 源码解析功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户输入服务器本地路径，系统自动解析 Java Spring Boot 源码，提取 API 接口并通过 AI 生成测试用例

**Architecture:**
- 后端：新增 `SourceCodeProject` 模型和 `SpringBootRegexParser` 正则解析器，复用现有 `ApiEndpoint` 表存储接口，`ApiDocService` 逻辑被复用
- 前端：新增"源码解析"页面，支持输入路径、解析结果展示、AI 生成测试用例预览
- 无 JDK 依赖，纯 Python 正则实现

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Vue 3, Element Plus

---

## 文件结构

```
backend/app/
├── models/
│   ├── source_code_project.py     # 新增: SourceCodeProject 模型
│   └── api_endpoint.py           # 修改: api_doc_id 改为 nullable
├── schemas/
│   ├── source_code_project.py    # 新增: Pydantic schemas
│   └── api_doc.py                # 修改: 新增 source_code_project_id
├── services/
│   ├── source_code_parser.py     # 新增: SpringBootRegexParser + SourceCodeParseService
│   └── openapi_parser.py         # 修改: 支持 source_code_project_id
├── api/
│   └── source_code.py            # 新增: API 路由
└── main.py                        # 修改: 注册新路由

frontend/src/
├── api/
│   └── sourceCode.ts             # 新增: 前端 API 调用
├── views/
│   └── SourceCodeParse.vue       # 新增: 源码解析页面
└── router/
    └── index.ts                  # 修改: 添加路由
```

---

## Task 1: 修改 ApiEndpoint 模型，支持两种来源

**Files:**
- Modify: `backend/app/models/api_endpoint.py:21-24`
- Modify: `backend/app/models/api_doc.py`

- [ ] **Step 1: 修改 api_endpoint.py，将 api_doc_id 改为 nullable，添加 source_code_project_id**

```python
# api_endpoint.py
# 原: api_doc_id = Column(Integer, ForeignKey("api_docs.id"), nullable=False)
# 改为:
api_doc_id = Column(Integer, ForeignKey("api_docs.id"), nullable=True)
source_code_project_id = Column(Integer, ForeignKey("source_code_projects.id"), nullable=True)
```

- [ ] **Step 2: 在 ApiDoc 模型中添加 source_code_project 反向关系**

```python
# api_doc.py - ApiDoc 类中添加:
source_code_project = relationship(
    "SourceCodeProject",
    back_populates="api_doc",
    uselist=False  # 一对一关系
)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/api_endpoint.py backend/app/models/api_doc.py
git commit -m "refactor: make api_doc_id nullable to support source code projects"
```

---

## Task 2: 创建 SourceCodeProject 模型

**Files:**
- Create: `backend/app/models/source_code_project.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建 source_code_project.py**

```python
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class ParseStatus(enum.Enum):
    PENDING = "pending"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceCodeProject(Base):
    __tablename__ = "source_code_projects"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    source_path = Column(String(500), nullable=False)
    language = Column(String(50), default="spring-boot")
    status = Column(SQLEnum(ParseStatus), default=ParseStatus.PENDING)
    error_message = Column(Text, nullable=True)
    endpoints_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    parsed_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project")
    api_doc = relationship("ApiDoc", back_populates="source_code_project", uselist=False)
    endpoints = relationship("ApiEndpoint")
```

- [ ] **Step 2: 修改 models/__init__.py 导出**

```python
from app.models.source_code_project import SourceCodeProject, ParseStatus
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/source_code_project.py backend/app/models/__init__.py
git commit -m "feat: add SourceCodeProject model for local source code parsing"
```

---

## Task 3: 创建 Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/source_code_project.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: 创建 schemas/source_code_project.py**

```python
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List


class SourceCodeProjectCreate(BaseModel):
    """Schema for creating a source code project."""
    project_id: int
    name: str
    source_path: str

    @field_validator("source_path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("Path traversal not allowed")
        if not v.startswith("/") and not v[1] == ":":
            raise ValueError("Absolute path required")
        return v


class SourceCodeProjectResponse(BaseModel):
    """Schema for source code project response."""
    id: int
    project_id: int
    name: str
    source_path: str
    language: str
    status: str
    error_message: Optional[str] = None
    endpoints_count: int = 0
    created_at: datetime
    parsed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SourceCodeParseRequest(BaseModel):
    """Schema for parse request."""
    project_id: int
    name: str
    source_path: str


class SourceCodeParseResponse(BaseModel):
    """Schema for parse response."""
    id: int
    name: str
    source_path: str
    status: str
    endpoints_count: int
    message: Optional[str] = None
```

- [ ] **Step 2: 修改 schemas/__init__.py**

```python
from app.schemas.source_code_project import (
    SourceCodeProjectCreate,
    SourceCodeProjectResponse,
    SourceCodeParseRequest,
    SourceCodeParseResponse
)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/source_code_project.py backend/app/schemas/__init__.py
git commit -m "feat: add Pydantic schemas for source code projects"
```

---

## Task 4: 创建 SpringBootRegexParser 正则解析器

**Files:**
- Create: `backend/app/services/source_code_parser.py`

- [ ] **Step 1: 编写测试**

创建 `backend/tests/test_source_code_parser.py`:

```python
import pytest
from app.services.source_code_parser import SpringBootRegexParser, parse_java_file


SIMPLE_CONTROLLER = '''
package com.example.controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class UserController {

    @GetMapping("/{id}")
    public User getUser(@PathVariable Long id) {
        return userService.findById(id);
    }

    @PostMapping
    public User createUser(@RequestBody @Valid UserRequest request) {
        return userService.create(request);
    }

    @PutMapping("/{id}")
    public User updateUser(@PathVariable Long id, @RequestBody UserRequest request) {
        return userService.update(id, request);
    }

    @DeleteMapping("/{id}")
    public void deleteUser(@PathVariable Long id) {
        userService.delete(id);
    }

    @GetMapping("/search")
    public List<User> searchUsers(@RequestParam String name, @RequestParam(required=false) Integer age) {
        return userService.search(name, age);
    }
}
'''


def test_parse_simple_controller():
    parser = SpringBootRegexParser()
    endpoints = parser.parse_content(SIMPLE_CONTROLLER)

    assert len(endpoints) == 5

    # Test GET /{id}
    get_by_id = next(e for e in endpoints if e["method"] == "GET" and "/{id}" in e["path"])
    assert get_by_id["path"] == "/api/users/{id}"
    assert get_by_id["summary"] is None

    # Test POST
    post = next(e for e in endpoints if e["method"] == "POST")
    assert post["path"] == "/api/users"
    assert post["request_body"] is not None

    # Test search with query params
    search = next(e for e in endpoints if "search" in e["path"])
    assert search["method"] == "GET"
    params = {p["name"]: p for p in search["parameters"]}
    assert "name" in params
    assert "age" in params


def test_path_traversal_blocked():
    with pytest.raises(ValueError, match="Path traversal"):
        SpringBootRegexParser.validate_path("/projects/../../../etc/passwd")


def test_relative_path_blocked():
    with pytest.raises(ValueError, match="Absolute path"):
        SpringBootRegexParser.validate_path("relative/path")


def test_scan_java_files(tmp_path):
    # Create test structure
    controller_dir = tmp_path / "src" / "main" / "java" / "com" / "example"
    controller_dir.mkdir(parents=True)
    (controller_dir / "UserController.java").write_text(SIMPLE_CONTROLLER)

    files = list(SpringBootRegexParser.scan_java_files(str(tmp_path)))
    assert len(files) == 1
    assert files[0].endswith("UserController.java")
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && pytest tests/test_source_code_parser.py -v
# 预期: ERROR - module not found
```

- [ ] **Step 3: 编写 SpringBootRegexParser 实现**

```python
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
        r'@(?:Rest)?Controller\s*(?:@\RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\'])',
        re.MULTILINE
    )

    METHOD_PATTERN = re.compile(
        r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|HeadMapping|OptionsMapping|RequestMapping)'
        r'\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
        re.MULTILINE
    )

    PATH_VARIABLE_PATTERN = re.compile(
        r'@PathVariable\s*(?:\(\s*(?:value\s*=\s*)?["\'](\w+)["\']\s*\)|(?<!\w)(\w+)(?!\w))',
        re.MULTILINE
    )

    REQUEST_PARAM_PATTERN = re.compile(
        r'@RequestParam\s*(?:\(\s*(?:name\s*=\s*)?["\'](\w+)["\']\s*\)|(?<!\w)(\w+)(?!\w))',
        re.MULTILINE
    )

    REQUEST_BODY_PATTERN = re.compile(r'@RequestBody')

    def validate_path(self, path: str) -> str:
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

    def parse_content(self, content: str) -> List[ParsedEndpoint]:
        """Parse Java source code content and extract endpoints."""
        endpoints = []

        # Find class-level @RequestMapping prefix
        class_match = self.CLASS_CONTROLLER_PATTERN.search(content)
        class_path = class_match.group(1) if class_match else ""

        # If no @RestController or @Controller with @RequestMapping, skip
        if not class_path and "@RestController" in content or "@Controller" in content:
            # Check if there's a standalone @RequestMapping at class level
            class_request_mapping = re.search(
                r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
                content
            )
            if class_request_mapping:
                class_path = class_request_mapping.group(1)

        # If still no class path, try to find package as fallback
        if not class_path:
            package_match = re.search(r'package\s+([\w.]+);', content)
            if package_match:
                class_path = "/" + package_match.group(1).replace(".", "/")

        # Find all method-level annotations
        for match in self.METHOD_PATTERN.finditer(content):
            annotation_name = match.group(1)
            method_path = match.group(2)
            http_method = self.METHOD_ANNOTATIONS.get(annotation_name, "GET")

            # Handle @RequestMapping with method attribute
            if annotation_name == "RequestMapping":
                method_match = re.search(
                    r'method\s*=\s*HttpMethod\.(\w+)',
                    content[match.start():match.start() + 200]
                )
                if method_match:
                    http_method = method_match.group(1)

            # Combine class path and method path
            full_path = self._combine_paths(class_path, method_path)

            # Extract parameters
            method_start = match.start()
            method_end = self._find_method_end(content, method_start)
            method_content = content[method_start:method_end]

            parameters = self._extract_parameters(method_content)
            has_request_body = self.REQUEST_BODY_PATTERN.search(method_content) is not None

            endpoint = ParsedEndpoint(
                path=full_path,
                method=http_method,
                parameters=parameters,
                request_body={"required": False} if has_request_body else None
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

    def _extract_parameters(self, method_content: str) -> List[Dict]:
        """Extract @PathVariable and @RequestParam parameters."""
        parameters = []

        # Extract path variables
        for match in self.PATH_VARIABLE_PATTERN.finditer(method_content):
            param_name = match.group(1) or match.group(2)
            parameters.append({
                "name": param_name,
                "location": "path",
                "required": True
            })

        # Extract request params
        for match in self.REQUEST_PARAM_PATTERN.finditer(method_content):
            param_name = match.group(1) or match.group(2)
            # Check if required
            required = "required" in method_content[max(0, match.start()-20):match.start()+50]
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


def parse_java_file(file_path: str) -> List[ParsedEndpoint]:
    """Convenience function to parse a single Java file."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    parser = SpringBootRegexParser()
    return parser.parse_content(content)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && pytest tests/test_source_code_parser.py -v
# 预期: PASS
```

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_source_code_parser.py backend/app/services/source_code_parser.py
git commit -m "feat: add SpringBootRegexParser for parsing Java source code"
```

---

## Task 5: 创建 SourceCodeParseService 服务

**Files:**
- Modify: `backend/app/services/source_code_parser.py` (添加 Service 类)

- [ ] **Step 1: 添加 SourceCodeParseService 类**

在 `source_code_parser.py` 末尾添加:

```python
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

        # Check for path traversal
        if ".." in path:
            raise ValueError("Path traversal not allowed")

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

        # Update status
        project.status = ParseStatus.PARSING
        await self.db.commit()

        try:
            # Scan for Java files
            parser = SpringBootRegexParser()
            java_files = parser.scan_java_files(project.source_path, self.MAX_DEPTH)

            if not java_files:
                project.status = ParseStatus.FAILED
                project.error_message = "No Java files found in source path"
                await self.db.commit()
                return project

            # Parse each file
            all_endpoints = []
            for java_file in java_files:
                try:
                    endpoints = parse_java_file(java_file)
                    all_endpoints.extend(endpoints)
                except Exception as e:
                    log.warning(f"Failed to parse {java_file}: {e}")
                    continue

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
```

- [ ] **Step 2: 更新测试以覆盖 Service**

```python
# 在 test_source_code_parser.py 添加
@pytest.mark.asyncio
async def test_create_project_invalid_path():
    service = SourceCodeParseService(db)
    with pytest.raises(ValueError, match="Absolute path required"):
        await service.create_project(1, "test", "relative/path")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/source_code_parser.py
git commit -m "feat: add SourceCodeParseService for managing source code projects"
```

---

## Task 6: 创建 API 路由

**Files:**
- Create: `backend/app/api/source_code.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建 api/source_code.py**

```python
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
```

- [ ] **Step 2: 在 main.py 注册路由**

```python
# 在 main.py 添加
from app.api.source_code import router as source_code_router

# 在 include_routers 函数中添加
app.include_router(source_code_router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/source_code.py backend/app/main.py
git commit -m "feat: add source code parsing API endpoints"
```

---

## Task 7: 前端 API 和页面

**Files:**
- Create: `frontend/src/api/sourceCode.ts`
- Create: `frontend/src/views/SourceCodeParse.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 创建 api/sourceCode.ts**

```typescript
import apiClient from './index'

export interface SourceCodeProject {
  id: number
  project_id: number
  name: string
  source_path: string
  language: string
  status: 'pending' | 'parsing' | 'completed' | 'failed'
  error_message?: string
  endpoints_count: number
  created_at: string
  parsed_at?: string
}

export interface ParseRequest {
  project_id: number
  name: string
  source_path: string
}

export interface ParseResponse {
  id: number
  name: string
  source_path: string
  status: string
  endpoints_count: number
  message?: string
}

export interface Endpoint {
  id: number
  path: string
  method: string
  summary?: string
  description?: string
  parameters: Array<{
    name: string
    location: string
    required: boolean
  }>
  request_body?: any
  responses: any[]
}

export const sourceCodeApi = {
  parse: (projectId: number, data: ParseRequest): Promise<ParseResponse> => {
    return apiClient.post(`/projects/${projectId}/source-code/parse`, data)
  },

  list: (projectId: number): Promise<SourceCodeProject[]> => {
    return apiClient.get(`/projects/${projectId}/source-code/projects`)
  },

  get: (projectId: number, sourceProjectId: number): Promise<SourceCodeProject> => {
    return apiClient.get(`/projects/${projectId}/source-code/projects/${sourceProjectId}`)
  },

  getEndpoints: (projectId: number, sourceProjectId: number): Promise<Endpoint[]> => {
    return apiClient.get(`/projects/${projectId}/source-code/projects/${sourceProjectId}/endpoints`)
  },

  delete: (projectId: number, sourceProjectId: number): Promise<void> => {
    return apiClient.delete(`/projects/${projectId}/source-code/projects/${sourceProjectId}`)
  }
}
```

- [ ] **Step 2: 创建 views/SourceCodeParse.vue**

```vue
<template>
  <div class="source-code-parse">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>源码解析</span>
        </div>
      </template>

      <!-- 解析表单 -->
      <el-form v-if="!currentProject" :model="form" label-width="120px">
        <el-form-item label="项目名称">
          <el-input v-model="form.name" placeholder="输入源码项目名称" />
        </el-form-item>
        <el-form-item label="源码路径">
          <el-input
            v-model="form.sourcePath"
            placeholder="/home/user/projects/my-spring-boot-app"
            type="textarea"
            :rows="2"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleParse" :loading="loading">
            开始解析
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 解析状态 -->
      <div v-if="currentProject" class="project-status">
        <el-alert
          :title="statusTitle"
          :type="statusType"
          :description="currentProject.error_message"
          show-icon
        />

        <div class="stats" v-if="currentProject.status === 'completed'">
          <el-statistic title="接口数量" :value="currentProject.endpoints_count" />
          <el-statistic title="源码路径" :value="currentProject.source_path" />
        </div>

        <!-- 接口列表 -->
        <el-table
          v-if="endpoints.length > 0"
          :data="endpoints"
          stripe
          style="width: 100%; margin-top: 20px"
        >
          <el-table-column prop="method" label="方法" width="80">
            <template #default="{ row }">
              <el-tag :type="getMethodType(row.method)">{{ row.method }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="path" label="路径" />
          <el-table-column prop="summary" label="描述" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button link type="primary" @click="showEndpointDetail(row)">
                详情
              </el-button>
              <el-button link type="primary" @click="generateTestCases(row)">
                生成用例
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 操作按钮 -->
        <div class="actions">
          <el-button @click="currentProject = null">返回</el-button>
          <el-button type="danger" @click="handleDelete">删除</el-button>
        </div>
      </div>

      <!-- 项目列表 -->
      <div v-if="!currentProject && projects.length > 0" class="projects-list">
        <el-divider>已解析的项目</el-divider>
        <el-list>
          <el-list-item v-for="project in projects" :key="project.id">
            <el-list-item-meta
              :title="project.name"
              :description="`${project.source_path} - ${project.endpoints_count} 接口`"
            />
            <template #extra>
              <el-button link type="primary" @click="selectProject(project)">
                查看
              </el-button>
            </template>
          </el-list-item>
        </el-list>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { sourceCodeApi, type SourceCodeProject, type Endpoint } from '@/api/sourceCode'

const props = defineProps<{
  projectId: number
}>()

const form = ref({
  name: '',
  sourcePath: ''
})

const loading = ref(false)
const projects = ref<SourceCodeProject[]>([])
const currentProject = ref<SourceCodeProject | null>(null)
const endpoints = ref<Endpoint[]>([])

const statusTitle = computed(() => {
  if (!currentProject.value) return ''
  const statusMap: Record<string, string> = {
    pending: '等待解析',
    parsing: '正在解析...',
    completed: '解析完成',
    failed: '解析失败'
  }
  return statusMap[currentProject.value.status] || currentProject.value.status
})

const statusType = computed(() => {
  if (!currentProject.value) return 'info'
  const typeMap: Record<string, any> = {
    pending: 'info',
    parsing: 'warning',
    completed: 'success',
    failed: 'error'
  }
  return typeMap[currentProject.value.status] || 'info'
})

const getMethodType = (method: string) => {
  const typeMap: Record<string, any> = {
    GET: 'success',
    POST: 'primary',
    PUT: 'warning',
    DELETE: 'danger',
    PATCH: 'info'
  }
  return typeMap[method] || 'info'
}

const handleParse = async () => {
  if (!form.value.name || !form.value.sourcePath) {
    ElMessage.warning('请填写项目名称和源码路径')
    return
  }

  loading.value = true
  try {
    const result = await sourceCodeApi.parse(props.projectId, {
      project_id: props.projectId,
      name: form.value.name,
      source_path: form.value.sourcePath
    })

    ElMessage.success('解析完成')
    await loadProject(result.id)
    await loadProjects()
  } catch (error: any) {
    ElMessage.error(error.detail || '解析失败')
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    projects.value = await sourceCodeApi.list(props.projectId)
  } catch (error) {
    console.error('Failed to load projects:', error)
  }
}

const loadProject = async (id: number) => {
  try {
    currentProject.value = await sourceCodeApi.get(props.projectId, id)
    if (currentProject.value.status === 'completed') {
      endpoints.value = await sourceCodeApi.getEndpoints(props.projectId, id)
    }
  } catch (error) {
    ElMessage.error('加载项目详情失败')
  }
}

const selectProject = async (project: SourceCodeProject) => {
  await loadProject(project.id)
}

const showEndpointDetail = (endpoint: Endpoint) => {
  // TODO: Show endpoint detail dialog
  console.log('Show detail:', endpoint)
}

const generateTestCases = (endpoint: Endpoint) => {
  // TODO: Integrate with AI test case generation
  ElMessage.info('AI 生成测试用例功能开发中')
}

const handleDelete = async () => {
  if (!currentProject.value) return

  try {
    await ElMessageBox.confirm('确定要删除这个源码项目吗?', '警告', {
      type: 'warning'
    })

    await sourceCodeApi.delete(props.projectId, currentProject.value.id)
    ElMessage.success('删除成功')
    currentProject.value = null
    await loadProjects()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.source-code-parse {
  padding: 20px;
}

.card-header {
  font-size: 18px;
  font-weight: bold;
}

.project-status {
  margin-top: 20px;
}

.stats {
  display: flex;
  gap: 40px;
  margin: 20px 0;
}

.actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

.projects-list {
  margin-top: 30px;
}
</style>
```

- [ ] **Step 3: 修改 router/index.ts 添加路由**

```typescript
{
  path: '/projects/:id/source-code',
  name: 'SourceCodeParse',
  component: () => import('@/views/SourceCodeParse.vue'),
  meta: { requiresAuth: true }
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/sourceCode.ts frontend/src/views/SourceCodeParse.vue frontend/src/router/index.ts
git commit -m "feat: add source code parsing frontend page"
```

---

## Task 8: 数据库迁移

**Files:**
- Create: `backend/alembic/versions/xxxx_add_source_code_project.py`

- [ ] **Step 1: 创建 Alembic 迁移**

```bash
cd backend && alembic revision --autogenerate -m "add source_code_projects table"
```

- [ ] **Step 2: 修改迁移文件确保 nullable 正确**

手动编辑生成的迁移文件:

```python
# 修改 api_endpoints 表
op.alter_column('api_endpoints', 'api_doc_id',
    existing_type=sa.Integer(),
    nullable=True)

# 添加 source_code_project_id 列
op.add_column('api_endpoints',
    sa.Column('source_code_project_id', sa.Integer(),
              sa.ForeignKey('source_code_projects.id'),
              nullable=True))

# 创建 source_code_projects 表
op.create_table('source_code_projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('source_path', sa.String(length=500), nullable=False),
    sa.Column('language', sa.String(length=50), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'PARSING', 'COMPLETED', 'FAILED'), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('endpoints_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('parsed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
)
```

- [ ] **Step 3: 运行迁移**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat: add database migration for source_code_projects"
```

---

## 验收清单

- [ ] 源码路径验证（禁止 `..` 穿越、必须是绝对路径）
- [ ] 递归扫描 `.java` 文件
- [ ] 正则匹配 `@RestController` + `@RequestMapping` 类
- [ ] 正则匹配 `@GetMapping` / `@PostMapping` 等方法注解
- [ ] 提取 path variable、query param、request body 信息
- [ ] 解析结果存入数据库
- [ ] 前端展示接口列表
- [ ] 支持查看接口详情
- [ ] 支持删除源码项目
