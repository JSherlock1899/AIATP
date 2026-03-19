"""
AI API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.schemas.ai import (
    GenerateTestCasesRequest,
    GenerateAssertionsRequest,
    AnalyzeAnomalyRequest,
    SuggestImprovementsRequest,
    TestCaseSuggestion,
    AssertionSuggestion,
    AnomalyAnalysis,
    AIStatus,
    AIProviderConfig
)
from app.services.openai_service import get_ai_provider, get_default_provider_name
from app.core.config import settings
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["ai"])


def get_ai_config() -> dict:
    """获取 AI 配置"""
    return {
        "provider": settings.AI_PROVIDER,
        "model": settings.OPENAI_MODEL if settings.AI_PROVIDER == "openai" else settings.ANTHROPIC_MODEL,
        "available": True
    }


@router.get("/status", response_model=AIStatus)
async def get_ai_status():
    """
    获取 AI 服务状态
    """
    config = get_ai_config()
    provider = get_ai_provider(config["provider"])

    try:
        available = await provider.health_check()
        return AIStatus(
            provider=provider.provider_name,
            available=available,
            model=config["model"] if available else None,
            error=None if available else "Health check failed"
        )
    except Exception as e:
        return AIStatus(
            provider=config["provider"],
            available=False,
            error=str(e)
        )


@router.get("/config", response_model=dict)
async def get_ai_config_info():
    """
    获取 AI 配置信息
    """
    return {
        "provider": settings.AI_PROVIDER,
        "openai_model": settings.OPENAI_MODEL,
        "anthropic_model": settings.ANTHROPIC_MODEL,
        "openai_key_set": bool(settings.OPENAI_API_KEY),
        "anthropic_key_set": bool(settings.ANTHROPIC_API_KEY),
    }


@router.post("/generate-test-cases", response_model=List[TestCaseSuggestion])
async def generate_test_cases(
    request: GenerateTestCasesRequest,
    current_user: User = Depends(get_current_user)
):
    """
    AI 生成测试用例建议

    根据 API 信息（路径、方法、参数、响应等）生成测试用例建议。
    """
    provider = get_ai_provider()

    try:
        suggestions = await provider.generate_test_cases(
            api_info=request.api_info.model_dump(),
            count=request.count
        )
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/generate-assertions", response_model=List[AssertionSuggestion])
async def generate_assertions(
    request: GenerateAssertionsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    AI 生成断言建议

    根据 API 响应生成合适的断言建议。
    """
    provider = get_ai_provider()

    try:
        suggestions = await provider.generate_assertions(
            api_response=request.api_response,
            context=request.context
        )
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/analyze-anomaly", response_model=AnomalyAnalysis)
async def analyze_anomaly(
    request: AnalyzeAnomalyRequest,
    current_user: User = Depends(get_current_user)
):
    """
    AI 异常分析

    分析测试失败的原因并提供修复建议。
    """
    provider = get_ai_provider()

    try:
        analysis = await provider.analyze_anomaly(
            test_result=request.test_result,
            related_context=request.related_context
        )
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


@router.post("/suggest-improvements", response_model=List[str])
async def suggest_improvements(
    request: SuggestImprovementsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    AI 改进建议

    根据测试用例和历史执行结果提供改进建议。
    """
    provider = get_ai_provider()

    try:
        suggestions = await provider.suggest_improvements(
            test_case={"id": request.test_case_id},
            recent_results=request.recent_results
        )
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI suggestion failed: {str(e)}")
