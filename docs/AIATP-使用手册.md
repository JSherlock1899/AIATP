# AIATP 使用手册

> AI-Driven API Testing Platform - AI 驱动的 API 测试平台
>
> 版本：1.0.0
> 更新日期：2026-03-20

---

## 目录

1. [项目概述](#1-项目概述)
2. [快速开始](#2-快速开始)
3. [项目管理](#3-项目管理)
4. [API 文档导入](#4-api-文档导入)
5. [源代码解析](#5-源代码解析)
6. [测试用例管理](#6-测试用例管理)
7. [断言配置](#7-断言配置)
8. [测试执行](#8-测试执行)
9. [测试结果分析](#9-测试结果分析)
10. [AI 功能详解](#10-ai-功能详解)
11. [常见问题](#11-常见问题)

---

## 1. 项目概述

### 1.1 功能架构

```
┌─────────────────────────────────────────────────────────────┐
│                        AIATP                                 │
├─────────────────────────────────────────────────────────────┤
│  数据导入                    │  测试执行                      │
│  ├─ OpenAPI 文档导入        │  ├─ 单用例执行                 │
│  └─ Java 源代码解析         │  ├─ 批量执行 (SSE 流式)        │
│                            │  └─ 重试机制                   │
│  用例生成                  │  结果分析                      │
│  ├─ AI 自动生成            │  ├─ 断言详情展示              │
│  └─ 手动创建               │  ├─ 响应数据查看               │
│                            │  └─ AI 失败分析               │
│  断言类型                                                    │
│  ├─ 状态码                │                               │
│  ├─ JSONPath              │                               │
│  ├─ 响应头                │                               │
│  ├─ 正则表达式            │                               │
│  ├─ 响应时间              │                               │
│  ├─ JSON 大小             │                               │
│  ├─ 数组长度              │                               │
│  └─ 数值范围              │                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Element Plus + TypeScript + Pinia |
| 后端 | FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |
| AI | OpenAI GPT-4o / Anthropic Claude |
| 测试 | pytest + pytest-asyncio |

### 1.3 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:5173 | Web UI |
| 后端 API | http://localhost:8000 | REST API |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| 健康检查 | http://localhost:8000/health | 服务状态 |

---

## 2. 快速开始

### 2.1 环境要求

- Python 3.10+
- Node.js 16+
- npm 或 yarn
- (可选) OpenAI API Key 或 Anthropic API Key

### 2.2 安装与启动

#### 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入必要的 API Key

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

#### Docker 启动（推荐）

```bash
# 在项目根目录
docker-compose up -d
```

### 2.3 首次使用流程

```
1. 打开浏览器访问 http://localhost:5173
2. 注册账号或登录（默认支持游客模式）
3. 创建项目
4. 导入 API 文档或解析源代码
5. 生成测试用例
6. 执行测试
7. 查看结果
```

---

## 3. 项目管理

### 3.1 创建项目

1. 在项目列表页面，点击 **"新建项目"** 按钮
2. 填写项目信息：

| 字段 | 必填 | 说明 |
|------|------|------|
| 项目名称 | 是 | 1-100 个字符 |
| 描述 | 否 | 项目详细说明 |
| Base URL | 否 | 统一替换测试用例的请求地址 |

3. 点击 **"确定"** 创建项目

### 3.2 项目设置

进入项目详情后，可以：

- 修改项目名称和描述
- 设置全局 Base URL（影响所有未单独配置 Base URL 的用例）
- 查看项目统计信息

### 3.3 项目成员（高级功能）

| 角色 | 权限 |
|------|------|
| 所有者 | 完全控制 |
| 管理员 | 管理用例、执行测试 |
| 测试员 | 执行测试、查看结果 |
| 访客 | 只读 |

---

## 4. API 文档导入

### 4.1 支持格式

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| OpenAPI 3.0 | .json, .yaml, .yml | 推荐 |
| Swagger 2.0 | .json, .yaml, .yml | 兼容支持 |

### 4.2 导入步骤

#### 方式一：在线导入

1. 进入项目详情
2. 切换到 **"API 文档"** 标签页
3. 点击 **"导入文档"**
4. 选择 **"在线导入"**
5. 输入 OpenAPI 文档的 URL 或粘贴 JSON/YAML 内容
6. 点击 **"导入"**

#### 方式二：文件导入

1. 进入项目详情 → **"API 文档"**
2. 点击 **"导入文档"** → **"文件导入"**
3. 选择本地 OpenAPI/Swagger 文件（.json/.yaml/.yml）
4. 点击 **"导入"**

#### 方式三：粘贴导入

1. 进入项目详情 → **"API 文档"**
2. 点击 **"导入文档"** → **"粘贴导入"**
3. 在文本框中粘贴 OpenAPI JSON 内容
4. 点击 **"导入"**

### 4.3 导入结果

成功导入后显示：

```
✅ 解析成功
├── 端点数量：25
├── GET：15
├── POST：6
├── PUT：2
├── DELETE：2
└── 文档版本：OpenAPI 3.0
```

### 4.4 查看已导入的端点

1. 在 **"API 端点"** 标签页查看所有端点
2. 点击端点可查看详细信息：

| 信息 | 说明 |
|------|------|
| 路径 | API 路由路径 |
| 方法 | GET/POST/PUT/DELETE 等 |
| 描述 | API 功能说明 |
| 参数 | 路径参数、查询参数 |
| 请求体 | JSON Schema 定义 |
| 响应 | 响应状态码和格式 |

---

## 5. 源代码解析

### 5.1 功能说明

自动解析 Java Spring Boot 项目的源代码，提取：

- Controller 映射的 API 端点
- 请求参数（@PathVariable、@RequestParam、@RequestBody）
- DTO/Entity 类定义（字段名和类型）

### 5.2 支持的注解

| 注解 | 提取内容 |
|------|----------|
| `@RestController` | Controller 类 |
| `@RequestMapping` | 类级别路径 |
| `@GetMapping` | GET 方法 + 路径 |
| `@PostMapping` | POST 方法 + 路径 |
| `@PutMapping` | PUT 方法 + 路径 |
| `@DeleteMapping` | DELETE 方法 + 路径 |
| `@PatchMapping` | PATCH 方法 + 路径 |
| `@PathVariable` | 路径参数 |
| `@RequestParam` | 查询参数 |
| `@RequestBody` | 请求体 + DTO 字段 |

### 5.3 解析步骤

1. 进入项目详情
2. 点击左侧菜单 **"源代码解析"**
3. 点击 **"新建解析任务"**
4. 填写配置：

| 字段 | 必填 | 说明 |
|------|------|------|
| 项目名称 | 是 | 解析任务的显示名称 |
| 源代码路径 | 是 | Java 源码根目录，如 `/home/user/project/src/main/java` |

5. 点击 **"开始解析"**
6. 等待解析完成（显示进度条）

### 5.4 DTO 字段提取

> ⚠️ **重要限制**

DTO 类必须在 Controller 源文件内部定义，且位置在 `@RestController` 注解之后、方法定义之前。

**正确示例：**

```java
@RestController
@RequestMapping("/api/users")
public class UserController {

    // DTO 定义在类内部、方法之前 ✅
    public static class CreateUserRequest {
        private String username;
        private String email;
        private String password;
        // getters and setters...
    }

    @PostMapping
    public User create(@RequestBody CreateUserRequest request) {
        return userService.create(request);
    }
}
```

**错误示例：**

```java
@RestController
@RequestMapping("/api/users")
public class UserController {

    @PostMapping
    public User create(@RequestBody CreateUserRequest request) {
        return userService.create(request);
    }
}

// CreateUserRequest 定义在另一个文件 ❌
```

### 5.5 解析结果

解析完成后显示：

```
✅ 解析完成
├── Controller 数量：5
├── 端点数量：23
├── DTO 数量：12
└── 提取字段：45
```

---

## 6. 测试用例管理

### 6.1 创建测试用例

#### 方式一：从端点创建

1. 切换到 **"API 端点"** 标签页
2. 找到目标端点
3. 点击端点行右侧的 **"创建用例"** 按钮
4. 自动填充端点信息，填写用例名称
5. 配置请求参数和断言
6. 点击 **"保存"**

#### 方式二：手动创建

1. 切换到 **"测试用例"** 标签页
2. 点击 **"添加测试用例"**
3. 手动填写所有字段
4. 点击 **"保存"**

### 6.2 用例基本信息

| 字段 | 必填 | 说明 |
|------|------|------|
| 用例名称 | 是 | 标识用例的名称 |
| 选择端点 | 否 | 关联的 API 端点 |
| 请求方法 | 是 | GET/POST/PUT/DELETE/PATCH |
| 请求 URL | 是 | 完整 URL 或相对路径 |
| 请求头 | 否 | JSON 格式，如 `{"Content-Type": "application/json"}` |
| 请求体 | 否 | JSON 格式的请求数据 |
| 超时时间 | 否 | 请求超时时间，默认 30 秒 |

### 6.3 请求体格式

**JSON 格式示例：**

```json
{
  "username": "张三",
  "email": "zhangsan@example.com",
  "password": "SecurePass123",
  "age": 25
}
```

**支持变量替换：**

```
请求体中使用 {{variable}} 引用测试数据
```

### 6.4 测试数据

测试数据用于在执行时动态替换请求中的变量：

| 变量 | 替换位置 | 示例 |
|------|----------|------|
| `{{userId}}` | URL、请求头、请求体 | `GET /api/users/{{userId}}` |

### 6.5 批量操作

- **全选**：勾选列表顶部复选框
- **批量执行**：选择多个用例后点击 **"批量执行"**
- **批量删除**：选择用例后点击删除按钮

---

## 7. 断言配置

### 7.1 断言类型说明

断言用于验证 API 响应是否符合预期。

| 类型 | 说明 | 示例 |
|------|------|------|
| `status` | HTTP 状态码 | expected: `200` 或 `201` |
| `jsonpath` | JSON 响应字段值 | field: `$.data.id`, expected: `123` |
| `header` | 响应头内容 | field: `Content-Type`, expected: `application/json` |
| `regex` | 正则表达式匹配 | field: `$.message`, expected: `success` |
| `response_time` | 响应时间（毫秒） | expected: `3000` (最大 3000ms) |
| `json_size` | JSON 响应体大小（字节） | expected: `{"max": 10240}` |
| `array_count` | 数组/对象元素数量 | field: `$.items`, expected: `{"min": 1, "max": 100}` |
| `range` | 数值字段范围 | field: `$.price`, expected: `{"min": 0, "max": 1000}` |

### 7.2 添加断言

1. 在用例编辑弹窗中，找到 **"断言"** 区域
2. 点击 **"AI 智能添加断言"**（推荐）或手动添加
3. 选择断言类型、填写字段路径和期望值
4. 可添加多条断言

### 7.3 断言配置示例

**状态码断言：**

```
类型：status
字段：status_code
期望值：200
描述：验证返回成功状态码
```

**JSONPath 断言：**

```
类型：jsonpath
字段：$.data.user.id
期望值：12345
描述：验证用户 ID 正确
```

**数值范围断言：**

```
类型：range
字段：$.price
期望值：{"min": 100, "max": 1000}
描述：验证价格在合理范围内
```

**数组长度断言：**

```
类型：array_count
字段：$.items
期望值：{"min": 1, "max": 50}
描述：验证返回商品数量在合理范围
```

### 7.4 AI 智能断言

点击 **"AI 智能添加断言"** 后：

1. 系统自动执行该测试用例
2. 获取真实响应数据
3. AI 分析响应内容
4. 生成推荐断言（包括响应时间、JSON 大小等）

---

## 8. 测试执行

### 8.1 单用例执行

1. 在 **"测试用例"** 标签页
2. 找到目标用例
3. 点击行右侧的 **"执行"** 按钮
4. 等待执行完成
5. 自动切换到 **"测试结果"** 标签页显示结果

### 8.2 批量执行

1. 在 **"测试用例"** 标签页
2. 勾选要执行的用例（左侧复选框）
3. 点击 **"批量执行"** 按钮
4. 观察进度条：

```
████████████░░░░░░░░░ 67%
正在执行: 获取用户详情
已执行: 8 / 12
```

5. 执行完成后显示汇总结果

### 8.3 批量执行限制

- 每次批量执行最多 100 个用例
- 超过时提示：`Batch size exceeds maximum limit of 100`

### 8.4 执行状态说明

| 状态 | 说明 |
|------|------|
| `passed` | 所有断言通过 |
| `failed` | 至少一个断言失败 |
| `error` | 执行过程出错（如网络超时） |
| `skipped` | 用例被跳过（未启用或不存在） |

---

## 9. 测试结果分析

### 9.1 结果概览

执行完成后显示：

```
总数：12
通过：8  ✅
失败：3  ❌
错误：1  ⚠️
耗时：1,234 ms
```

### 9.2 查看详情

1. 在结果列表中找到目标用例
2. 点击 **"详情"** 按钮
3. 展开显示：

#### 响应数据

```json
{
  "status_code": 200,
  "headers": {
    "Content-Type": "application/json",
    "X-Request-Id": "abc123"
  },
  "body": {
    "code": 0,
    "message": "success",
    "data": {
      "id": 10001,
      "username": "张三",
      "email": "zhangsan@example.com"
    }
  }
}
```

#### 断言结果

| 断言 | 期望值 | 实际值 | 状态 |
|------|--------|--------|------|
| status | 200 | 200 | ✅ 通过 |
| jsonpath: $.data.id | 10001 | 10001 | ✅ 通过 |
| jsonpath: $.data.username | "张三" | "李四" | ❌ 失败 |
| response_time | ≤3000ms | 1234ms | ✅ 通过 |

### 9.3 重试功能

#### 单个重试

1. 在失败用例行点击 **"重试"** 按钮
2. 系统重新执行该用例
3. 结果更新到列表中

#### 批量重试失败

1. 在结果汇总区点击 **"重试所有失败用例"**
2. 系统自动筛选失败用例
3. 批量重新执行
4. 完成后合并结果

### 9.4 AI 失败分析

对于失败的用例，可以点击 **"AI 分析"**：

1. 系统收集失败信息和响应数据
2. 调用 AI 分析可能原因
3. 显示分析报告：

```
错误类型：assertion
严重程度：medium
可能原因：断言期望值与实际响应不匹配
修复建议：
1. 检查测试用例的期望值是否正确
2. 确认 API 响应数据格式
3. 更新断言条件或调整测试数据
置信度：85%
```

---

## 10. AI 功能详解

### 10.1 配置 AI Provider

编辑 `backend/.env` 文件：

```bash
# 选择 AI 提供商
AI_PROVIDER=anthropic  # 或 openai

# OpenAI 配置
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic 配置
ANTHROPIC_API_KEY=sk-ant-xxxxx
ANTHROPIC_MODEL=MiniMax-M2.7
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
```

### 10.2 AI 生成测试用例

点击 **"AI 生成测试用例"**：

1. 系统遍历所有端点
2. 并行调用 AI（每批 5 个端点）
3. 为每个端点生成 2 个测试用例：
   - **基础用例**：验证基本功能
   - **完整参数用例**：带完整请求体

> ⚠️ **注意**：如果未配置 AI Key 或 AI 不可用，系统使用规则回退生成，仅生成简单的基础用例。

### 10.3 AI 智能断言

点击用例行右侧的 **"智能断言"**：

1. 执行该测试用例获取真实响应
2. AI 分析响应内容
3. 推荐合适的断言：
   - 状态码断言
   - 关键字段存在性检查
   - 响应时间断言
   - JSON 大小断言
   - 数组长度断言（如果适用）

### 10.4 AI 批量分析

当有多个失败用例时：

1. 点击 **"分析所有失败"**
2. 系统并发分析每个失败用例
3. 生成综合报告：
   - 高严重性问题数量
   - 各类问题的修复建议

---

## 11. 常见问题

### Q1: 源代码解析提示 "DTO 字段为空"

**原因**：DTO 类定义在单独的 Java 文件中，解析器无法提取。

**解决方案**：
1. 将 DTO 类定义移动到 Controller 源文件内部
2. 确保 DTO 定义在 `@RestController` 注解之后、方法定义之前

### Q2: AI 生成测试用例时请求体为空

**原因**：
1. 源代码解析未提取到 DTO 字段
2. AI Provider 未配置或不可用

**解决方案**：
1. 检查 DTO 是否正确定义
2. 配置有效的 AI API Key
3. 手动填写请求体

### Q3: 批量执行报错 "Batch size exceeds maximum limit"

**原因**：一次性执行超过 100 个用例

**解决方案**：分批执行，每次少于 100 个用例

### Q4: SSE 进度条不更新

**原因**：浏览器 EventSource 对 URL 长度有限制

**解决方案**：已改用 fetch + ReadableStream 实现，无 URL 长度限制

### Q5: 前端页面空白或加载失败

**解决方案**：
1. 检查后端是否正常运行：`curl http://localhost:8000/health`
2. 清除浏览器缓存
3. 重启前端开发服务器

### Q6: 如何导入嵌套 DTO？

**示例**：创建工单接口包含用户信息

```java
public static class CreateWorkOrderRequest {
    private String title;
    private String description;
    // 嵌套 DTO
    private UserInfo user;

    public static class UserInfo {
        private Long userId;
        private String username;
    }
}
```

系统会递归提取嵌套字段：
```json
{
  "title": "工单标题",
  "description": "工单描述",
  "user": {
    "userId": 123,
    "username": "张三"
  }
}
```

---

## 附录

### A. API 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` | 用户注册 |
| POST | `/auth/login` | 用户登录 |
| GET | `/auth/me` | 获取当前用户 |
| GET | `/projects` | 获取项目列表 |
| POST | `/projects` | 创建项目 |
| GET | `/projects/{id}` | 获取项目详情 |
| POST | `/projects/{id}/api-docs/import` | 导入 API 文档 |
| POST | `/projects/{id}/source-code/parse` | 解析源代码 |
| GET | `/test-cases` | 获取测试用例列表 |
| POST | `/test-cases` | 创建测试用例 |
| POST | `/test-cases/execute` | 执行测试用例 |
| POST | `/test-cases/execute/stream` | 流式执行测试用例 |
| POST | `/ai/generate-test-cases` | AI 生成测试用例 |
| POST | `/ai/generate-assertions` | AI 生成断言 |
| POST | `/ai/analyze-anomaly` | AI 分析异常 |

### B. 错误码对照表

| 错误码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### C. 日志级别

| 级别 | 使用场景 |
|------|----------|
| ERROR | 程序异常、需要立即处理 |
| WARN | 可恢复错误、潜在风险 |
| INFO | 重要业务节点 |
| DEBUG | 开发调试信息 |

---

*文档结束*
