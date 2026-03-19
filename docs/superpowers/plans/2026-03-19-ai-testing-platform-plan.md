# AIATP 实施计划（第一阶段 - MVP）

> **给 agent 工作者：** 必需的子技能：使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 来实施此计划。步骤使用复选框（`- [ ]`）语法进行跟踪。

**目标：** 构建 AI 驱动 API 测试平台的 MVP，包含用户认证、项目管理、OpenAPI 导入和 API 测试执行。

**架构：** FastAPI 后端（Python）+ Vue 3 前端的模块化单体架构。PostgreSQL 持久化。第二阶段加入 AI 功能。

**技术栈：** FastAPI + SQLAlchemy 2.0 + Pydantic v2 | Vue 3 + Element Plus + Pinia | PostgreSQL 15+ | Docker Compose

---

## 文件结构

```
ai-testing-platform/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 应用入口
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py        # 环境配置
│   │   │   ├── database.py      # SQLAlchemy 引擎/会话
│   │   │   └── security.py      # JWT 处理
│   │   ├── models/              # SQLAlchemy 模型
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── api_doc.py
│   │   │   ├── api_endpoint.py
│   │   │   ├── test_case.py
│   │   │   └── test_result.py
│   │   ├── schemas/              # Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── api_doc.py
│   │   │   └── test_case.py
│   │   ├── api/                  # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── auth.py           # /auth 端点
│   │   │   ├── projects.py       # /projects 端点
│   │   │   ├── api_docs.py       # /api-docs 端点
│   │   │   └── test_cases.py     # /test-cases 和 /execute 端点
│   │   └── services/              # 业务逻辑
│   │       ├── __init__.py
│   │       ├── auth_service.py
│   │       ├── project_service.py
│   │       ├── openapi_parser.py  # OpenAPI 解析
│   │       └── test_executor.py   # HTTP 测试执行
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_projects.py
│   │   ├── test_openapi_parser.py
│   │   └── test_executor.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                  # Axios API 客户端
│   │   │   ├── index.ts
│   │   │   ├── projects.ts
│   │   │   └── testCases.ts
│   │   ├── stores/              # Pinia 状态管理
│   │   │   └── auth.ts
│   │   ├── views/               # 页面组件
│   │   │   ├── Login.vue
│   │   │   ├── Projects.vue
│   │   │   └── ProjectDetail.vue
│   │   ├── router/
│   │   │   └── index.ts
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json
│   ├── nginx.conf
│   └── Dockerfile
└── docker-compose.yml
```

---

## 任务 1：项目脚手架

**文件：**
- 创建：`backend/requirements.txt`
- 创建：`backend/Dockerfile`
- 创建：`backend/app/__init__.py`
- 创建：`backend/app/main.py`
- 创建：`frontend/package.json`
- 创建：`frontend/Dockerfile`
- 创建：`docker-compose.yml`

- [ ] **步骤 1：创建 backend/requirements.txt**

```txt
fastapi==0.111.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.30
asyncpg==0.29.0
pydantic==2.7.0
pydantic-settings==2.2.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
httpx==0.27.0
PyYAML==6.0.1
alembic==1.13.1
jsonpath-ng==1.6.1
pytest==8.2.0
pytest-asyncio==0.23.6
aiosqlite==0.20.0
```

- [ ] **步骤 2：创建 backend/app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.models import user, project, api_doc, api_endpoint, test_case, test_result

app = FastAPI(title="AIATP", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **步骤 3：创建 docker-compose.yml**

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://aitp:aitp123@db:5432/aitp
      - SECRET_KEY=your-secret-key-change-in-production
    depends_on:
      - db
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=aitp
      - POSTGRES_USER=aitp
      - POSTGRES_PASSWORD=aitp123
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

- [ ] **步骤 4：提交**

```bash
git add -A && git commit -m "chore: 使用 FastAPI + Vue 3 搭建项目结构"
```

---

## 任务 2：核心配置与数据库模型

**文件：**
- 创建：`backend/app/core/config.py`
- 创建：`backend/app/core/database.py`
- 创建：`backend/app/core/security.py`
- 修改：`backend/app/main.py`
- 创建：`backend/app/models/__init__.py`

- [ ] **步骤 1：创建 app/core/config.py**

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"

@lru_cache
def get_settings():
    return Settings()
```

- [ ] **步骤 2：创建 app/core/database.py**

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=True)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session_maker() as session:
        yield session
```

- [ ] **步骤 3：创建 app/core/security.py**

```python
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
```

- [ ] **步骤 4：创建 app/models/__init__.py**

```python
from app.models.user import User
from app.models.project import Project, ProjectMember
from app.models.api_doc import ApiDoc
from app.models.api_endpoint import ApiEndpoint
from app.models.test_case import TestCase
from app.models.test_result import TestResult

__all__ = ["User", "Project", "ProjectMember", "ApiDoc", "ApiEndpoint", "TestCase", "TestResult"]
```

- [ ] **步骤 5-10：创建所有模型文件（user.py, project.py, api_doc.py, api_endpoint.py, test_case.py, test_result.py）**

- [ ] **步骤 11：提交**

```bash
git add -A && git commit -m "feat: 添加核心配置、数据库和所有 SQLAlchemy 模型"
```

---

## 任务 3-6：后端 API 开发

详见计划文档中的详细步骤...

## 任务 7：前端脚手架

**文件：**
- 创建：`frontend/package.json`
- 创建：`frontend/vite.config.ts`
- 创建：`frontend/index.html`
- 创建：`frontend/src/main.ts`
- 创建：`frontend/src/App.vue`
- 创建：`frontend/src/api/index.ts`
- 创建：`frontend/src/api/projects.ts`
- 创建：`frontend/src/api/testCases.ts`
- 创建：`frontend/src/stores/auth.ts`
- 创建：`frontend/src/router/index.ts`
- 创建：`frontend/src/views/Login.vue`
- 创建：`frontend/src/views/Projects.vue`
- 创建：`frontend/src/views/ProjectDetail.vue`
- 创建：`frontend/nginx.conf`
- 创建：`frontend/Dockerfile`

详见计划文档中的详细代码...

## 任务 8：最终集成与验证

- [ ] **步骤 1：更新 app/main.py 添加所有路由**
- [ ] **步骤 2：创建 .env.example**
- [ ] **步骤 3：验证后端运行**
- [ ] **步骤 4：验证 docker-compose 构建**
- [ ] **步骤 5：提交**

---

## 总结

| 任务 | 描述 | 状态 |
|------|------|------|
| 1 | 项目脚手架 | 待处理 |
| 2 | 核心配置与数据库模型 | 待处理 |
| 3 | 用户认证 API | 待处理 |
| 4 | 项目管理 API | 待处理 |
| 5 | OpenAPI 导入与解析 | 待处理 |
| 6 | 测试用例管理与执行 | 待处理 |
| 7 | 前端脚手架 | 待处理 |
| 8 | 最终集成与验证 | 待处理 |
