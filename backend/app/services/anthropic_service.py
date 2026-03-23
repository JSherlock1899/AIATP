"""
Anthropic AI Provider Implementation
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


class AnthropicProvider(AIProvider):
    """Anthropic Claude AI Provider"""

    def __init__(self):
        from app.core.config import settings
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model = settings.ANTHROPIC_MODEL
        self.base_url = settings.ANTHROPIC_BASE_URL
        self._client = None

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _get_client(self):
        """获取 Anthropic 客户端"""
        if self._client is None and self.api_key:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                pass
        return self._client

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用 Claude LLM"""
        client = self._get_client()
        if not client:
            raise ValueError("Anthropic API key not configured or client not available")

        response = await client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.content[0].text

    async def generate_test_cases(
        self,
        api_info: Dict[str, Any],
        count: int = 3
    ) -> List[TestCaseSuggestion]:
        """根据 API 信息生成测试用例建议"""

        if not self.api_key:
            return self._rule_based_test_cases(api_info, count)

        system_prompt = """你是一个专业的 API 测试工程师。根据提供的 API 信息，生成全面的测试用例建议。
每个测试用例应该包含：
- name: 用例名称
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
2. **根据字段名推断合理值**：
   - email → "user@example.com"
   - phone/mobile → "13800138000"
   - name/username → "张三" 或 "john_doe"
   - password → "SecurePass123"
   - id → 生成一个合理的数字如 1
3. **不要生成空对象 {} 或空数组 []**
4. **包含所有必填字段**

请以 JSON 数组格式返回。"""

        user_prompt = f"""API 信息：
{json.dumps(api_info, ensure_ascii=False, indent=2)}

请生成 {count} 个测试用例建议，覆盖正常路径、边界条件和异常情况。
**必须根据 DTO 字段信息生成真实合理的请求体数据！**"""

        try:
            response_text = await self._call_llm(system_prompt, user_prompt)
            # 尝试解析 JSON
            data = json.loads(response_text)
            return [TestCaseSuggestion(**item) for item in data]
        except Exception as e:
            return self._rule_based_test_cases(api_info, count)

    def _rule_based_test_cases(
        self,
        api_info: Dict[str, Any],
        count: int = 3
    ) -> List[TestCaseSuggestion]:
        """基于规则生成测试用例"""
        suggestions = []
        path = api_info.get("path", "/")
        method = api_info.get("method", "GET").upper()
        summary = api_info.get("summary", "")
        parameters = api_info.get("parameters") or []
        request_body_schema = api_info.get("request_body")

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
- type: 断言类型 (status, jsonpath, header, regex)
- field: 字段路径 (如 status_code, data.user.id, headers.content-type)
- expected: 期望值
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
        """基于规则生成断言"""
        suggestions = []
        status_code = api_response.get("status_code", 200)

        suggestions.append(AssertionSuggestion(
            type="status",
            field="status_code",
            expected=status_code,
            description=f"验证状态码为 {status_code}"
        ))

        body = api_response.get("body")
        if body and isinstance(body, dict):
            if "data" in body:
                suggestions.append(AssertionSuggestion(
                    type="jsonpath",
                    field="$.data",
                    expected={"exists": True},
                    description="验证 data 字段存在"
                ))

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
        """基于规则分析异常"""
        error_message = test_result.get("error_message", "")
        status_code = test_result.get("response_data", {}).get("status_code")

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
                confidence=0.9
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
        total = len(recent_results)
        if total == 0:
            return ["暂无历史数据"]

        failed = sum(1 for r in recent_results if r.get("status") == "failed")
        failure_rate = failed / total

        if failure_rate > 0.5:
            suggestions.append(f"失败率较高 ({failure_rate:.0%})，建议检查测试用例的合理性")

        passed = sum(1 for r in recent_results if r.get("status") == "passed")
        if passed == total and total > 5:
            suggestions.append("所有测试都通过了，考虑添加更严格的断言")

        if not suggestions:
            suggestions.append("测试用例表现良好，继续保持")

        return suggestions
