"""
AI Provider Abstract Interface
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class AssertionSuggestion(BaseModel):
    """AI 生成的断言建议"""
    type: str  # status, jsonpath, header, regex
    field: str
    expected: Any
    description: Optional[str] = None
    confidence: float = 0.8  # 置信度 0-1


class TestCaseSuggestion(BaseModel):
    """AI 生成的测试用例建议"""
    name: str
    description: Optional[str] = None
    method: str
    url: str
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None
    assertions: List[AssertionSuggestion] = []
    test_data: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None  # AI 生成理由


class AnomalyAnalysis(BaseModel):
    """AI 异常分析结果"""
    error_type: str  # network, timeout, assertion, server_error, etc.
    severity: str  # critical, high, medium, low
    root_cause: str  # 可能的原因
    suggestion: str  # 修复建议
    related_tests: Optional[List[int]] = None  # 相关测试用例 ID
    confidence: float = 0.8


class AIProvider(ABC):
    """AI Provider 抽象接口"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 名称"""
        pass

    @abstractmethod
    async def generate_test_cases(
        self,
        api_info: Dict[str, Any],
        count: int = 3
    ) -> List[TestCaseSuggestion]:
        """
        根据 API 信息生成测试用例建议

        Args:
            api_info: API 信息，包含 path, method, summary, parameters, request_body, responses 等
            count: 生成数量

        Returns:
            List[TestCaseSuggestion]: 测试用例建议列表
        """
        pass

    @abstractmethod
    async def generate_assertions(
        self,
        api_response: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[AssertionSuggestion]:
        """
        根据 API 响应生成断言建议

        Args:
            api_response: API 响应数据
            context: 额外上下文信息（如 API 路径、期望的状态码等）

        Returns:
            List[AssertionSuggestion]: 断言建议列表
        """
        pass

    @abstractmethod
    async def analyze_anomaly(
        self,
        test_result: Dict[str, Any],
        related_context: Optional[Dict[str, Any]] = None
    ) -> AnomalyAnalysis:
        """
        分析测试异常

        Args:
            test_result: 测试结果
            related_context: 相关上下文

        Returns:
            AnomalyAnalysis: 异常分析结果
        """
        pass

    @abstractmethod
    async def suggest_improvements(
        self,
        test_case: Dict[str, Any],
        recent_results: List[Dict[str, Any]]
    ) -> List[str]:
        """
        根据测试用例和历史结果提供改进建议

        Args:
            test_case: 测试用例
            recent_results: 最近的执行结果

        Returns:
            List[str]: 改进建议列表
        """
        pass

    async def health_check(self) -> bool:
        """检查 AI 服务是否可用"""
        try:
            return await self._ping()
        except Exception:
            return False

    async def _ping(self) -> bool:
        """实际的健康检查"""
        return True
