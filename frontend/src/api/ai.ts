import apiClient from './index'

export interface AssertionSuggestion {
  type: 'status' | 'jsonpath' | 'header' | 'regex'
  field: string
  expected: any
  description?: string
  confidence: number
}

export interface TestCaseSuggestion {
  name: string
  description?: string
  method: string
  url: string
  headers?: Record<string, string>
  body?: any
  assertions: AssertionSuggestion[]
  test_data?: Record<string, any>
  reasoning?: string
}

export interface AnomalyAnalysis {
  error_type: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  root_cause: string
  suggestion: string
  related_tests?: number[]
  confidence: number
}

export interface ApiInfo {
  path: string
  method: string
  summary?: string
  description?: string
  parameters?: any[]
  request_body?: any
  responses?: any
}

export interface AIStatus {
  provider: string
  available: boolean
  model?: string
  error?: string
}

export const aiApi = {
  // 获取 AI 服务状态
  getStatus: (): Promise<AIStatus> => {
    return apiClient.get('/ai/status')
  },

  // AI 生成测试用例
  generateTestCases: (apiInfo: ApiInfo, count: number = 3): Promise<TestCaseSuggestion[]> => {
    return apiClient.post('/ai/generate-test-cases', {
      api_info: apiInfo,
      count
    })
  },

  // AI 生成断言
  generateAssertions: (
    apiResponse: Record<string, any>,
    context?: Record<string, any>
  ): Promise<AssertionSuggestion[]> => {
    return apiClient.post('/ai/generate-assertions', {
      api_response: apiResponse,
      context
    })
  },

  // AI 分析异常
  analyzeAnomaly: (
    testResult: Record<string, any>,
    relatedContext?: Record<string, any>
  ): Promise<AnomalyAnalysis> => {
    return apiClient.post('/ai/analyze-anomaly', {
      test_result: testResult,
      related_context: relatedContext
    })
  },

  // AI 改进建议
  suggestImprovements: (
    testCaseId: number,
    recentResults: Record<string, any>[]
  ): Promise<string[]> => {
    return apiClient.post('/ai/suggest-improvements', {
      test_case_id: testCaseId,
      recent_results: recentResults
    })
  }
}
