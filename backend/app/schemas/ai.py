"""
AI-related Pydantic schemas.
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class ApiInfo(BaseModel):
    """API 信息"""
    path: str
    method: str
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[List[Dict[str, Any]]] = None
    request_body: Optional[Dict[str, Any]] = None
    responses: Optional[Dict[str, Any]] = None


class AssertionSuggestion(BaseModel):
    """AI 生成的断言建议"""
    type: str
    field: str
    expected: Any
    description: Optional[str] = None
    confidence: float = 0.8


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
    reasoning: Optional[str] = None


class AnomalyAnalysis(BaseModel):
    """AI 异常分析结果"""
    error_type: str
    severity: str
    root_cause: str
    suggestion: str
    related_tests: Optional[List[int]] = None
    confidence: float = 0.8


class GenerateTestCasesRequest(BaseModel):
    """生成测试用例请求"""
    api_info: ApiInfo
    count: int = 3


class GenerateAssertionsRequest(BaseModel):
    """生成断言请求"""
    api_response: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


class AnalyzeAnomalyRequest(BaseModel):
    """分析异常请求"""
    test_result: Dict[str, Any]
    related_context: Optional[Dict[str, Any]] = None


class SuggestImprovementsRequest(BaseModel):
    """建议改进请求"""
    test_case_id: int
    recent_results: List[Dict[str, Any]]


class AIProviderConfig(BaseModel):
    """AI Provider 配置"""
    provider: str = "openai"
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None


class AIStatus(BaseModel):
    """AI 服务状态"""
    provider: str
    available: bool
    model: Optional[str] = None
    error: Optional[str] = None
