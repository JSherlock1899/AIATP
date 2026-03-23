"""
OpenAI AI Provider Implementation
"""
import os
import json
from typing import List, Dict, Any, Optional

from app.services.ai_provider import (
    AIProvider,
    TestCaseSuggestion,
    AssertionSuggestion,
    AnomalyAnalysis
)


class OpenAIProvider(AIProvider):
    """OpenAI GPT-4o AI Provider"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self._client = None

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_client(self):
        """获取 OpenAI 客户端"""
        if self._client is None and self.api_key:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                pass
        return self._client

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM"""
        client = self._get_client()
        if not client:
            raise ValueError("OpenAI API key not configured or client not available")

        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content

    async def generate_test_cases(
        self,
        api_info: Dict[str, Any],
        count: int = 3
    ) -> List[TestCaseSuggestion]:
        """根据 API 信息生成测试用例建议"""

        # 如果没有 API key，使用规则生成
        if not self.api_key:
            return self._rule_based_test_cases(api_info, count)

        path = api_info.get("path", "")
        method = api_info.get("method", "GET").upper()
        summary = api_info.get("summary", "")
        parameters = api_info.get("parameters") or []
        request_body_schema = api_info.get("request_body")

        # 构建详细的请求体说明
        body_info = ""
        if request_body_schema:
            body_info = f"\n请求体 Schema: {json.dumps(request_body_schema, ensure_ascii=False, indent=2)}"
        elif parameters:
            body_params = [p for p in parameters if p.get("location") in ("body", "request", None)]
            if body_params:
                body_info = f"\n参数信息: {json.dumps(body_params, ensure_ascii=False, indent=2)}"

        system_prompt = """你是一个专业的 API 测试工程师。根据提供的 API 信息，生成全面的测试用例建议。
每个测试用例应该包含：
- name: 用例名称（简洁明了）
- description: 用例描述
- method: HTTP 方法
- url: 请求 URL（可以是相对路径）
- headers: 请求头（如需要）
- body: 请求体（根据 API 性质生成合理的 JSON 数据）
- assertions: 断言列表，每个断言包含 type, field, expected, description

**重要：请根据 request_body_schema 中的字段信息生成合理的请求体！**

对于 POST/PUT/PATCH 接口，body 应该生成符合业务逻辑的示例数据：
1. **严格根据 DTO 字段名和类型生成**：
   - String/text 类型字段：生成真实感的数据，如 "title": "工单标题"
   - Integer/Long 类型字段：生成数字，如 "priority": 1
   - Boolean 类型字段：生成 true/false
   - Array 类型字段：根据元素类型生成数组
2. **根据字段名推断合理值**：
   - email → "user@example.com"
   - phone/mobile → "13800138000"
   - url/link → "https://example.com"
   - name/username → "张三" 或 "john_doe"
   - password → "SecurePass123"
   - id → 生成一个合理的数字如 1
   - status/type → 生成业务相关的枚举值
3. **不要生成空对象 {} 或空数组 []**
4. **包含所有必填字段**

请以 JSON 数组格式返回。"""

        user_prompt = f"""API 信息：
- 路径: {path}
- 方法: {method}
- 描述: {summary}
{body_info}

请生成 {count} 个测试用例建议，覆盖正常路径、边界条件和异常情况。
**必须根据 DTO 字段信息生成真实合理的请求体数据！**"""

        try:
            response_text = await self._call_llm(system_prompt, user_prompt)
            # 解析 JSON 响应
            data = json.loads(response_text)
            return [TestCaseSuggestion(**item) for item in data]
        except Exception as e:
            # 如果 LLM 调用失败，回退到规则生成
            return self._rule_based_test_cases(api_info, count)

    def _rule_based_test_cases(
        self,
        api_info: Dict[str, Any],
        count: int = 3
    ) -> List[TestCaseSuggestion]:
        """基于规则生成测试用例（无 AI 时使用）"""
        suggestions = []
        path = api_info.get("path", "/")
        method = api_info.get("method", "GET").upper()
        summary = api_info.get("summary", "")
        parameters = api_info.get("parameters") or []
        request_body_schema = api_info.get("request_body")

        # 基础测试用例
        suggestions.append(TestCaseSuggestion(
            name=f"{method} {path} - 基本请求",
            description=f"测试 {summary} 的基本调用",
            method=method,
            url=path,
            assertions=[
                AssertionSuggestion(
                    type="status",
                    field="status_code",
                    expected=200,
                    description="验证返回 200 状态码"
                )
            ],
            reasoning="基础测试用例"
        ))

        # 如果是 POST/PUT，添加请求体测试
        if method in ["POST", "PUT", "PATCH"]:
            # 根据 request_body schema 或 parameters 生成合理的请求体
            sample_body = self._generate_sample_body(request_body_schema, parameters)
            suggestions.append(TestCaseSuggestion(
                name=f"{method} {path} - 完整参数",
                description="测试带完整参数的请求",
                method=method,
                url=path,
                body=sample_body,
                assertions=[
                    AssertionSuggestion(
                        type="status",
                        field="status_code",
                        expected=200,
                        description="验证返回 200 状态码"
                    )
                ],
                reasoning="验证完整参数"
            ))

            # 空请求体测试
            suggestions.append(TestCaseSuggestion(
                name=f"{method} {path} - 空请求体",
                description="测试空请求体或无效数据",
                method=method,
                url=path,
                body={},
                assertions=[
                    AssertionSuggestion(
                        type="status",
                        field="status_code",
                        expected=400,
                        description="验证返回 400 错误"
                    )
                ],
                reasoning="验证输入验证"
            ))

        # 添加参数测试
        if parameters:
            suggestions.append(TestCaseSuggestion(
                name=f"{method} {path} - 缺少必填参数",
                description="测试缺少必填参数的情况",
                method=method,
                url=path,
                assertions=[
                    AssertionSuggestion(
                        type="status",
                        field="status_code",
                        expected=400,
                        description="验证返回参数错误"
                    )
                ],
                reasoning="验证参数验证"
            ))

        return suggestions[:count]

    def _generate_sample_body(self, request_body: Any, parameters: List[Dict]) -> Dict[str, Any]:
        """根据 request_body schema 或 parameters 生成示例请求体"""
        if request_body and isinstance(request_body, dict):
            # 尝试从 request_body schema 生成
            fields = request_body.get("fields") or []
            if fields:
                result = {}
                for field_info in fields:
                    field_name = field_info.get("name", "")
                    field_type = field_info.get("type", "string").lower()
                    result[field_name] = self._generate_field_value(field_name, field_type)
                if result:
                    return result

        # 根据 parameters 生成（path/query 参数）
        body_params = [p for p in parameters if p.get("location") in ("body", "request")]
        if body_params:
            result = {}
            for p in body_params:
                name = p.get("name", "")
                result[name] = "test_value"
            if result:
                return result

        # 默认返回空对象
        return {}

    def _generate_field_value(self, field_name: str, field_type: str) -> Any:
        """根据字段名和类型生成合理的示例值"""
        name_lower = field_name.lower()

        # 根据字段名推断合理值
        if "email" in name_lower:
            return "user@example.com"
        elif "phone" in name_lower or "mobile" in name_lower or "tel" in name_lower:
            return "13800138000"
        elif "url" in name_lower or "link" in name_lower:
            return "https://example.com"
        elif "password" in name_lower or "pwd" in name_lower:
            return "SecurePass123"
        elif "name" in name_lower or "username" in name_lower or "nickname" in name_lower:
            return "张三"
        elif "title" in name_lower or "subject" in name_lower:
            return "测试标题"
        elif "content" in name_lower or "description" in name_lower or "detail" in name_lower:
            return "这是测试内容"
        elif "id" in name_lower:
            return 1
        elif "status" in name_lower or "state" in name_lower:
            return "active"
        elif "type" in name_lower or "category" in name_lower:
            return "normal"
        elif "priority" in name_lower or "level" in name_lower:
            return 1
        elif "count" in name_lower or "num" in name_lower or "total" in name_lower:
            return 0
        elif "price" in name_lower or "amount" in name_lower or "money" in name_lower:
            return 99.99
        elif "enable" in name_lower or "active" in name_lower or "disabled" in name_lower:
            return True
        elif "flag" in name_lower:
            return False
        elif "date" in name_lower or "time" in name_lower or "created" in name_lower or "updated" in name_lower:
            return "2024-01-01 10:00:00"
        elif "address" in name_lower or "location" in name_lower:
            return "北京市朝阳区"
        elif "avatar" in name_lower or "image" in name_lower or "photo" in name_lower or "logo" in name_lower:
            return "https://example.com/image.jpg"

        # 根据 Java 类型生成
        if field_type in ("string", "text", "str"):
            return "test_value"
        elif field_type in ("integer", "int", "long", "biginteger", "double", "float", "decimal", "number"):
            return 1
        elif field_type in ("boolean", "bool"):
            return True
        elif field_type == "array":
            return []
        elif field_type == "object":
            return {}

        # 默认返回字符串
        return "test_value"

    async def generate_assertions(
        self,
        api_response: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[AssertionSuggestion]:
        """根据 API 响应生成断言建议"""

        if not self.api_key:
            return self._rule_based_assertions(api_response, context)

        system_prompt = """你是一个专业的 API 测试工程师。根据提供的 API 响应和上下文，生成合适的断言建议。
每个断言应该包含：
- type: 断言类型
  * status: HTTP 状态码 (如 200, 201, 400, 404, 500)
  * jsonpath: JSON 响应字段验证，使用 JSONPath 语法 (如 $.data.id, $.items[0].name)
  * header: 响应头验证 (如 content-type, x-request-id)
  * regex: 正则表达式匹配响应体
  * response_time: 响应时间断言，expected 为最大毫秒数
  * json_size: JSON 响应体大小（字节），expected 为最大字节数或 {min, max} 范围
  * array_count: 数组/对象字段元素数量，expected 为数量或 {min, max} 范围
  * range: 数值字段范围验证，expected 为 {min, max} 范围或具体值
- field: 字段路径 (如 status_code, $.data.user.id, content-type, $.items)
- expected: 期望值
  * status: 具体状态码数字或 "*" (匹配 2xx)
  * jsonpath: 具体值或 {"exists": true} 或 {"min": X, "max": Y}
  * header: 具体字符串值
  * regex: 要匹配的字符串
  * response_time: 最大毫秒数
  * json_size: 最大字节数或 {min, max}
  * array_count: 数量或 {min, max}
  * range: 具体值或 {min, max}
- description: 描述
- confidence: 置信度 0-1

请以 JSON 数组格式返回。"""

        context_str = json.dumps(context or {}, ensure_ascii=False, indent=2)
        user_prompt = f"""API 响应：
{json.dumps(api_response, ensure_ascii=False, indent=2)}

上下文：
{context_str}

请生成合适的断言建议。"""

        try:
            response_text = await self._call_llm(system_prompt, user_prompt)
            data = json.loads(response_text)
            return [AssertionSuggestion(**item) for item in data]
        except Exception:
            return self._rule_based_assertions(api_response, context)

    def _rule_based_assertions(
        self,
        api_response: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[AssertionSuggestion]:
        """基于规则生成断言（无 AI 时使用）"""
        suggestions = []

        # 状态码断言
        status_code = api_response.get("status_code", 200)
        suggestions.append(AssertionSuggestion(
            type="status",
            field="status_code",
            expected=status_code,
            description=f"验证状态码为 {status_code}"
        ))

        # 如果是 JSON 响应，添加 JSONPath 断言
        body = api_response.get("body")
        if body and isinstance(body, dict):
            suggestions.append(AssertionSuggestion(
                type="jsonpath",
                field="$",
                expected={"exists": True},
                description="验证响应体存在"
            ))

            # 检查常见字段
            if "data" in body:
                suggestions.append(AssertionSuggestion(
                    type="jsonpath",
                    field="$.data",
                    expected={"exists": True},
                    description="验证 data 字段存在"
                ))

            if "id" in body or (isinstance(body.get("data"), dict) and "id" in body["data"]):
                id_path = "$.data.id" if "data" in body else "$.id"
                suggestions.append(AssertionSuggestion(
                    type="jsonpath",
                    field=id_path,
                    expected={"exists": True},
                    description="验证 ID 字段存在"
                ))

        # 响应时间断言
        response_time = api_response.get("response_time", 0)
        if response_time > 0:
            suggestions.append(AssertionSuggestion(
                type="response_time",
                field="response_time",
                expected=3000,
                description="验证响应时间小于 3000ms"
            ))

        # JSON 响应体大小断言
        if body:
            import sys
            body_str = json.dumps(body) if not isinstance(body, str) else body
            body_size = len(body_str.encode('utf-8'))
            suggestions.append(AssertionSuggestion(
                type="json_size",
                field="body",
                expected={"min": 0, "max": body_size * 2},
                description=f"验证响应体大小在合理范围内"
            ))

        # 数组字段数量断言
        if body and isinstance(body, dict):
            for key, value in body.items():
                if isinstance(value, list):
                    count = len(value)
                    if count > 0:
                        suggestions.append(AssertionSuggestion(
                            type="array_count",
                            field=f"$.{key}",
                            expected={"min": max(0, count - 5), "max": count + 5},
                            description=f"验证 {key} 数组长度在合理范围"
                        ))
                        break  # 只添加一个数组断言作为示例

        return suggestions

    async def analyze_anomaly(
        self,
        test_result: Dict[str, Any],
        related_context: Optional[Dict[str, Any]] = None
    ) -> AnomalyAnalysis:
        """分析测试异常"""

        if not self.api_key:
            return self._rule_based_analysis(test_result, related_context)

        system_prompt = """你是一个专业的 API 测试工程师和诊断专家。根据测试失败结果，分析可能的原因并提供修复建议。

分析应该包含：
- error_type: 错误类型 (network, timeout, assertion, server_error, validation, unknown)
- severity: 严重程度 (critical, high, medium, low)
- root_cause: 可能的原因分析
- suggestion: 具体的修复建议
- confidence: 置信度 0-1

请以 JSON 格式返回。"""

        result_str = json.dumps(test_result, ensure_ascii=False, indent=2)
        context_str = json.dumps(related_context or {}, ensure_ascii=False, indent=2)
        user_prompt = f"""测试失败结果：
{result_str}

相关上下文：
{context_str}

请分析失败原因并提供修复建议。"""

        try:
            response_text = await self._call_llm(system_prompt, user_prompt)
            data = json.loads(response_text)
            return AnomalyAnalysis(**data)
        except Exception:
            return self._rule_based_analysis(test_result, related_context)

    def _rule_based_analysis(
        self,
        test_result: Dict[str, Any],
        related_context: Optional[Dict[str, Any]] = None
    ) -> AnomalyAnalysis:
        """基于规则分析异常（无 AI 时使用）"""
        error_message = test_result.get("error_message", "")
        status_code = test_result.get("response_data", {}).get("status_code")

        # 根据错误信息判断错误类型
        if "timeout" in error_message.lower():
            return AnomalyAnalysis(
                error_type="timeout",
                severity="high",
                root_cause="请求超时，可能是网络问题或服务端响应过慢",
                suggestion="1. 检查网络连接\n2. 增加超时时间\n3. 检查服务端性能",
                confidence=0.9
            )
        elif "connection" in error_message.lower():
            return AnomalyAnalysis(
                error_type="network",
                severity="critical",
                root_cause="无法连接到服务器",
                suggestion="1. 检查服务器地址是否正确\n2. 检查服务器是否运行\n3. 检查防火墙设置",
                confidence=0.95
            )
        elif status_code and status_code >= 500:
            return AnomalyAnalysis(
                error_type="server_error",
                severity="high",
                root_cause="服务端返回 5xx 错误，可能是服务端内部问题",
                suggestion="1. 检查服务端日志\n2. 联系后端开发人员\n3. 稍后重试",
                related_tests=related_context.get("related_test_ids") if related_context else None,
                confidence=0.9
            )
        elif status_code and status_code == 400:
            return AnomalyAnalysis(
                error_type="validation",
                severity="medium",
                root_cause="请求参数验证失败",
                suggestion="1. 检查请求参数格式\n2. 验证必填字段\n3. 检查参数类型是否正确",
                confidence=0.9
            )
        elif status_code and status_code == 401:
            return AnomalyAnalysis(
                error_type="authentication",
                severity="high",
                root_cause="未授权访问，需要认证",
                suggestion="1. 检查是否需要登录\n2. 验证 Token 是否有效\n3. 检查权限设置",
                confidence=0.95
            )
        elif test_result.get("assertion_results"):
            failed_assertions = [a for a in test_result["assertion_results"] if not a.get("passed")]
            if failed_assertions:
                return AnomalyAnalysis(
                    error_type="assertion",
                    severity="medium",
                    root_cause=f"断言失败: {failed_assertions[0].get('field', 'unknown')}",
                    suggestion=f"1. 检查期望值是否正确\n2. 验证实际响应数据\n3. 更新断言条件",
                    confidence=0.85
                )

        return AnomalyAnalysis(
            error_type="unknown",
            severity="medium",
            root_cause="未知错误",
            suggestion="1. 查看详细错误信息\n2. 检查测试用例配置\n3. 联系开发人员",
            confidence=0.5
        )

    async def suggest_improvements(
        self,
        test_case: Dict[str, Any],
        recent_results: List[Dict[str, Any]]
    ) -> List[str]:
        """提供测试用例改进建议"""
        suggestions = []

        # 统计失败率
        total = len(recent_results)
        if total == 0:
            return ["暂无历史数据"]

        failed = sum(1 for r in recent_results if r.get("status") == "failed")
        failure_rate = failed / total

        if failure_rate > 0.5:
            suggestions.append(f"失败率较高 ({failure_rate:.0%})，建议检查测试用例的合理性")

        # 检查是否总是成功（可能断言太宽松）
        passed = sum(1 for r in recent_results if r.get("status") == "passed")
        if passed == total and total > 5:
            suggestions.append("所有测试都通过了，考虑添加更严格的断言")

        # 检查响应时间趋势
        response_times = [r.get("response_time", 0) for r in recent_results]
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            if avg_time > 2000:
                suggestions.append(f"平均响应时间较长 ({avg_time:.0f}ms)，建议添加超时断言")

        # 检查是否有偶发失败
        recent_statuses = [r.get("status") for r in recent_results[-5:]]
        if "failed" in recent_statuses and "passed" in recent_statuses:
            suggestions.append("存在偶发失败，可能是网络不稳定或服务端并发问题")

        if not suggestions:
            suggestions.append("测试用例表现良好，继续保持")

        return suggestions


# 全局 provider 实例
_ai_providers: Dict[str, AIProvider] = {}


def get_ai_provider(provider_name: str = None) -> AIProvider:
    """获取 AI Provider 实例，从配置读取"""
    from app.core.config import settings
    from app.services.anthropic_service import AnthropicProvider

    # 如果没有指定，使用配置文件中的 provider
    if provider_name is None:
        provider_name = settings.AI_PROVIDER

    if provider_name not in _ai_providers:
        if provider_name == "openai":
            _ai_providers[provider_name] = OpenAIProvider()
        elif provider_name == "anthropic":
            _ai_providers[provider_name] = AnthropicProvider()
        else:
            raise ValueError(f"Unknown AI provider: {provider_name}")
    return _ai_providers[provider_name]


def register_provider(name: str, provider: AIProvider):
    """注册新的 AI Provider"""
    _ai_providers[name] = provider


def get_default_provider_name() -> str:
    """获取默认 provider 名称"""
    from app.core.config import settings
    return settings.AI_PROVIDER
