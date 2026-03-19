# AI-Driven API Testing Platform (AIATP) 设计文档

**日期**: 2026-03-19
**状态**: 设计阶段

---

## 一、项目背景

AI-Driven API Testing Platform (AIATP) 是一个私有化部署的 AI 增强型 API 测试平台，帮助开发者和测试工程师：

- 导入 API 文档自动生成测试用例
- AI 智能生成断言和验证逻辑
- 异常检测 + 预测性诊断
- 可视化报告 + 趋势分析
- 团队协作 + 项目隔离

**目标用户**: 开发人员 + 测试工程师（混合团队）

---

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────┐
│              Vue 3 Frontend                  │
│  (Element Plus, Pinia, Vue Router, Vite)    │
└─────────────────────┬───────────────────────┘
                      │ HTTP/REST
                      ▼
┌─────────────────────────────────────────────┐
│               FastAPI Backend                │
│  ┌────────┬────────┬────────┬────────┐   │
│  │API管理  │ AI引擎  │ 测试执行 │ 报告中心 │   │
│  └────────┴────────┴────────┴────────┘   │
│  ┌────────┬────────┬────────┐             │
│  │知识库   │定时任务  │用户/权限 │              │
│  └────────┴────────┴────────┘             │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│              PostgreSQL                      │
└─────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术选型 |
|------|----------|
| 后端框架 | FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| 前端框架 | Vue 3 + Element Plus + Pinia + Axios |
| 数据库 | PostgreSQL 15+ |
| AI 引擎 | LangChain + 多模型抽象层（OpenAI/Claude/Ollama）|
| 部署方式 | Docker Compose |

---

## 三、核心功能模块

| 模块 | 功能描述 |
|------|----------|
| **API 管理** | 导入 OpenAPI/Swagger/Postman 文档，管理项目下的 API 列表 |
| **用例生成** | AI 分析 API 文档，自动生成测试用例和断言 |
| **测试执行** | 支持单接口/批量/定时执行，记录详细执行日志 |
| **AI 引擎** | 多模型抽象层，统一调度 OpenAI/Claude/开源模型 |
| **断言引擎** | AI 生成智能断言，支持 JSONPath/XPath/正则 |
| **报告中心** | 可视化报告、趋势图、失败分析、导出 PDF/HTML |
| **知识库** | 测试经验积累、常见问题库、AI 建议库 |
| **定时任务** | Cron 表达式配置，支持 CI/CD Hook |
| **用户/权限** | 多用户、项目隔离、基础角色权限 |

---

## 四、数据模型

### 4.1 核心实体关系

```
User
  └── Team ──── ProjectMember
                    └── Project
                          ├── ApiDoc (API 文档)
                          ├── TestCase (测试用例)
                          ├── TestSuite (测试套件)
                          ├── TestResult (执行结果)
                          ├── KnowledgeBase (知识库)
                          └── Schedule (定时任务)
```

### 4.2 主要数据表

| 表名 | 说明 |
|------|------|
| users | 用户表 |
| teams | 团队表 |
| projects | 项目表 |
| project_members | 项目成员关联表 |
| api_docs | API 文档表（存储 OpenAPI/Postman 导入内容）|
| apis | API 端点表 |
| test_cases | 测试用例表 |
| test_suites | 测试套件表 |
| test_results | 执行结果表 |
| knowledge_base | 知识库表 |
| schedules | 定时任务表 |

---

## 五、AI 能力设计

### 5.1 多模型抽象层

```python
# AI Provider 抽象接口
class AIProvider(ABC):
    def generate_test_cases(self, api_spec: dict) -> List[TestCase]
    def generate_assertions(self, response: dict, context: dict) -> List[Assertion]
    def analyze_anomaly(self, test_result: TestResult) -> AnomalyReport
    def suggest_fix(self, failed_test: TestCase) -> str
```

支持的模型：
- OpenAI (GPT-4o)
- Anthropic (Claude)
- 本地模型 (Ollama/Llama/Qwen)

### 5.2 AI 功能流程

1. **用例生成**: API 文档 → AI 分析 → 测试用例 + 断言
2. **智能断言**: 响应数据 + 历史数据 → AI 生成验证规则
3. **异常检测**: 测试结果 → AI 分析 → 问题分类 + 建议修复
4. **知识建议**: 失败场景 → AI 匹配知识库 → 推荐解决方案

---

## 六、部署架构

### 6.1 Docker Compose 配置

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/aitp
      - AI_PROVIDER=openai
    depends_on:
      - db

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=aitp
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass

volumes:
  postgres_data:
```

---

## 七、项目结构

```
ai-testing-platform/
├── backend/
│   ├── app/
│   │   ├── api/              # API 路由
│   │   │   ├── projects/
│   │   │   ├── apis/
│   │   │   ├── test_cases/
│   │   │   ├── test_results/
│   │   │   ├── ai/
│   │   │   ├── knowledge/
│   │   │   └── auth/
│   │   ├── core/             # 核心配置
│   │   ├── models/           # SQLAlchemy 模型
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # 业务逻辑
│   │   ├── ai/               # AI 引擎
│   │   └── main.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/            # 页面
│   │   ├── components/       # 组件
│   │   ├── stores/          # Pinia stores
│   │   ├── router/
│   │   ├── api/             # API 调用
│   │   └── main.ts
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── README.md
```

---

## 八、优先级规划

### Phase 1 - MVP
- [ ] 用户认证（注册/登录/JWT）
- [ ] 项目管理（创建/加入项目）
- [ ] API 文档导入（OpenAPI/Swagger）
- [ ] API 列表展示
- [ ] 单接口测试执行
- [ ] 测试结果展示

### Phase 2 - AI 增强
- [ ] AI 测试用例生成
- [ ] AI 智能断言
- [ ] AI 异常分析
- [ ] 多 AI 模型切换

### Phase 3 - 高级功能
- [ ] 测试套件管理
- [ ] 定时任务
- [ ] CI/CD 集成
- [ ] 报告导出
- [ ] 知识库
- [ ] 团队权限管理

---

## 九、验收标准

1. 可以导入 OpenAPI 3.0 文档并解析
2. 可以手动创建测试用例并执行
3. AI 可以生成测试用例和断言
4. 测试结果可持久化存储
5. 支持多用户、多项目隔离
6. 可通过 Docker Compose 一键部署
