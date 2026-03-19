# 源码解析功能设计文档

**日期**: 2026-03-19
**状态**: 设计完成
**功能**: 根据本地路径解析 Java Spring Boot 项目，提取 API 接口并 AI 生成测试用例

---

## 一、功能概述

用户输入服务器本地项目路径，系统自动解析该路径下所有 Java 源码，提取 Spring Boot API 接口信息，并与 AI 服务协作生成测试用例和入参。

### 与现有功能的关系

与 OpenAPI 文档导入功能为**并列关系**：
- OpenAPI 导入：用户上传 OpenAPI YAML/JSON 文档
- 源码解析：用户输入本地源码路径，系统自动识别接口

解析结果存储在 `source_code_projects` 表，接口信息存入 `api_endpoints` 表（复用现有表结构）。

---

## 二、技术方案

### 2.1 依赖

| 依赖 | 用途 |
|------|------|
| Python 3.10+ | 运行时 |
| re (标准库) | 正则表达式匹配注解 |
| walkdir / pathlib | 递归扫描目录 |

**无 JDK 依赖**，MVP 采用纯正则方案。

### 2.2 解析注解范围

| 注解 | 提取信息 |
|------|---------|
| `@RestController` / `@Controller` | 类标记（需同时有 @RequestMapping 才识别） |
| `@RequestMapping` | 类级 path、前缀 |
| `@GetMapping` / `@PostMapping` / `@PutMapping` / `@DeleteMapping` / `@PatchMapping` | 方法级 path、HTTP method |
| `@PathVariable` | 路径参数（{id} 形式） |
| `@RequestParam` | Query 参数 |
| `@RequestBody` | 请求体 |

### 2.3 正则匹配模式

```python
# 类级注解
@RestController> pattern: r'@RestController\s*(?:@RequestMapping\s*\(\s*["\']([^"\']+)["\'])?
@Controller> pattern: r'@Controller\s*(?:@RequestMapping\s*\(\s*["\']([^"\']+)["\'])?

# 方法级注解
@GetMapping> pattern: r'@GetMapping\s*\(\s*["\']([^"\']+)["\']'
@PostMapping> pattern: r'@PostMapping\s*\(\s*["\']([^"\']+)["\']'
# ... 其他方法同理

# 参数注解
@PathVariable> pattern: r'@PathVariable\s*(?:,\s*name\s*=\s*["\'](\w+)["\']|\(\s*["\'](\w+)["\'])?
@RequestParam> pattern: r'@RequestParam\s*(?:required\s*=\s*(?:true|false))?\s*(?:,\s*name\s*=\s*["\'](\w+)["\']|\(\s*["\'](\w+)["\'])?
```

---

## 三、系统架构

```
用户输入本地路径
       │
       ▼
┌──────────────────────────────┐
│     SourceCodeParseService   │
│  - validate_path()           │
│  - scan_java_files()          │
│  - parse_file()              │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│   SpringBootRegexParser      │
│  - parse_controller()        │
│  - parse_method()             │
│  - extract_parameters()      │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│     AiTestCaseGenerator      │
│  (复用现有 AI 服务)           │
│  - generate_test_cases()     │
│  - generate_test_data()      │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│       前端展示                │
│  - 接口列表                   │
│  - 接口详情                   │
│  - AI 测试用例预览            │
└──────────────────────────────┘
```

---

## 四、数据模型

### 4.1 新增表：source_code_projects

```python
class SourceCodeProject:
    id: int                    # 主键
    project_id: int            # 关联项目 (FK)
    name: str                  # 代码项目名称
    source_path: str           # 服务器本地路径
    language: str              # "spring-boot"
    status: str                # "pending" / "parsing" / "completed" / "failed"
    error_message: str         # 错误信息 (可选)
    endpoints_count: int       # 解析出的接口数量
    created_at: datetime
    parsed_at: datetime        # 解析完成时间
```

### 4.2 复用的现有表

- `api_endpoints` - 存储解析出的接口信息（复用现有表结构）
- `test_cases` - 存储 AI 生成的测试用例（复用现有表结构）

---

## 五、API 设计

### 5.1 后端接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/source-code/parse` | 开始解析本地源码 |
| GET | `/api/v1/source-code/projects` | 获取源码解析项目列表 |
| GET | `/api/v1/source-code/projects/{id}` | 获取单个项目详情 |
| GET | `/api/v1/source-code/projects/{id}/endpoints` | 获取项目下的接口列表 |
| DELETE | `/api/v1/source-code/projects/{id}` | 删除源码项目 |

#### POST /api/v1/source-code/parse

**请求体**:
```json
{
  "project_id": 1,
  "name": "my-spring-app",
  "source_path": "/home/user/projects/spring-boot-app"
}
```

**响应**:
```json
{
  "id": 1,
  "name": "my-spring-app",
  "source_path": "/home/user/projects/spring-boot-app",
  "status": "parsing",
  "endpoints_count": 0
}
```

#### GET /api/v1/source-code/projects/{id}

**响应**:
```json
{
  "id": 1,
  "name": "my-spring-app",
  "source_path": "/home/user/projects/spring-boot-app",
  "status": "completed",
  "endpoints_count": 25,
  "parsed_at": "2026-03-19T10:30:00Z"
}
```

### 5.2 AI 生成测试用例接口

复用现有的 `POST /api/v1/test-cases/generate` 接口：

**请求体**:
```json
{
  "endpoint_id": 1,
  "generate_normal": true,
  "generate_boundary": true,
  "generate_error": true
}
```

---

## 六、前端交互

### 6.1 页面入口

独立的"源码解析"页面或Tab，与"API 文档"页面并列。

### 6.2 用户流程

1. **输入页面**
   - 输入项目名称
   - 输入服务器本地路径
   - 点击"开始解析"

2. **解析中**
   - 显示解析进度（文件数量）
   - 支持取消操作

3. **解析完成**
   - 显示接口列表
   - 显示解析统计（接口数量、控制器数量）

4. **接口详情**
   - 点击接口展开详情
   - 显示：路径、HTTP方法、参数列表、请求体结构

5. **AI 生成测试用例**
   - 点击"生成测试用例"按钮
   - 显示生成的测试用例列表
   - 可编辑、删除、新增
   - 点击"保存"存入测试用例库

---

## 七、错误处理

| 场景 | HTTP 状态码 | 错误信息 |
|------|------------|---------|
| 路径不存在 | 400 | "源码路径不存在，请确认路径是否正确" |
| 路径无权限访问 | 403 | "无权限访问该路径" |
| 目录下无 .java 文件 | 400 | "未找到任何 Java 文件，请确认路径是否指向 Spring Boot 项目" |
| 解析过程异常 | 500 | "解析过程出现异常: {具体错误}" |

---

## 八、安全考虑

### 8.1 路径安全（基础校验）

- 禁止路径中出现 `..` 穿越
- 验证路径为绝对路径
- 限制扫描深度（最多 20 层目录）

### 8.2 注意

当前设计**不做白名单目录限制**，假设部署环境可信。生产环境使用 Docker 部署时，需确保容器内路径隔离。

---

## 九、实现计划

### Phase 1 - MVP
- [ ] `SourceCodeParseService` 服务实现
- [ ] `SpringBootRegexParser` 正则解析器
- [ ] `SourceCodeProject` 数据模型与 CRUD
- [ ] 后端 API 端点
- [ ] 前端源码解析页面（基础版）
- [ ] 解析结果展示

### Phase 2 - AI 集成
- [ ] 复用现有 AI 服务生成测试用例
- [ ] 前端测试用例预览与编辑
- [ ] 测试用例保存到库

---

## 十、验收标准

1. ✅ 用户输入本地路径后，系统能递归扫描所有 `.java` 文件
2. ✅ 正则能正确匹配 `@RestController` + `@RequestMapping` 类
3. ✅ 正则能正确匹配 `@GetMapping` / `@PostMapping` 等方法注解
4. ✅ 能提取 path variable、query param、request body 信息
5. ✅ 解析结果存入数据库，可在前端展示
6. ✅ AI 能根据接口信息生成测试用例（含正常值、边界值、异常值）
7. ✅ 前端能展示接口列表、详情、测试用例预览
