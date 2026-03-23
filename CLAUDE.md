# AIATP 项目规范

> AI-Driven API Testing Platform - AI 驱动的 API 测试平台

## 项目概述

- **后端**: FastAPI + SQLAlchemy 2.0 + Pydantic v2 + PostgreSQL/SQLite
- **前端**: Vue 3 + Element Plus + TypeScript + Pinia
- **测试**: pytest + pytest-asyncio (90+ tests)
- **AI**: OpenAI GPT-4o / Anthropic Claude

## 目录结构

```
AI-test/
├── backend/
│   ├── app/
│   │   ├── api/          # API 路由 (ai, auth, projects, test_cases, source_code)
│   │   ├── core/         # 核心模块 (config, database, security)
│   │   ├── models/       # SQLAlchemy 模型
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # 业务逻辑 (ai_provider, test_executor, openapi_parser)
│   │   └── main.py       # FastAPI 应用入口
│   ├── tests/            # pytest 测试
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/          # API 调用
│   │   ├── router/       # Vue Router
│   │   ├── stores/       # Pinia stores
│   │   ├── views/        # 页面组件
│   │   └── App.vue
│   ├── tests/            # E2E 测试 (Playwright)
│   ├── package.json
│   └── vite.config.ts
├── docs/                 # 文档
├── docker-compose.yml
└── CLAUDE.md
```

## 常用命令

### 后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 运行测试
pytest -v
pytest tests/ -v --tb=short

# 生成迁移
alembic revision --autogenerate -m "描述"
```

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

### Docker

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## 开发规范

### 后端 (Python)

1. **命名规范**
   - Controller: `XxxController` (实际用 `APIRouter`)
   - Service: `XxxService`
   - Model: `XxxModel` / `XxxEntity`
   - Schema: `XxxSchema` / `XxxDTO`

2. **异常处理**
   - 使用 `raise ResultException` (fly 框架)
   - 错误码前缀: `common-xxxx` (通用), `workorder-xxxx`, `member-xxxx`

3. **日志规范**
   - 使用占位符 `log.info("用户[{}]登录成功", userId)`
   - 异常日志: `log.error("...", e)`

4. **输入校验**
   - API 参数使用 `@Valid` 校验
   - 使用 Pydantic schema 验证请求体

### 前端 (TypeScript/Vue)

1. **组件组织**
   - `views/`: 页面级组件
   - `components/`: 通用组件
   - `api/`: API 调用封装
   - `stores/`: Pinia 状态管理

2. **API 响应处理**
   - 使用统一响应格式 `{ code, message, data }`
   - 使用 `axios` 封装，配置拦截器

## 测试要求

- **覆盖率目标**: ≥80%
- **测试类型**:
  - 单元测试: 独立函数、工具类
  - 集成测试: API 端点、数据库操作
  - E2E 测试: 关键用户流程 (Playwright)

## 安全检查

- [ ] 无硬编码凭证 (使用环境变量)
- [ ] 用户输入验证
- [ ] SQL 注入防护 (参数化查询)
- [ ] XSS 防护
- [ ] SSRF 防护 (URL 验证阻止内网 IP)
- [ ] ReDoS 防护 (正则限制 500 字符)
- [ ] YAML 解析使用 SafeLoader

## Git 提交规范

```
<type>: <description>

Types: feat, fix, refactor, docs, test, chore, perf, ci
```

## AI 功能配置

编辑 `backend/.env`:

```bash
# AI Provider 选择
AI_PROVIDER=anthropic  # 或 openai

# OpenAI
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4o

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxx
ANTHROPIC_MODEL=MiniMax-M2.7
```
