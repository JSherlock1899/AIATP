import apiClient from './index'

// 后端 TestCaseResponse 格式
export interface TestCase {
  id: number
  endpoint_id: number
  name: string
  description: string | null
  status: string
  request_config: {
    method: string
    url: string
    headers?: Record<string, string>
    params?: Record<string, string>
    body?: any
    timeout?: number
  }
  test_data: Record<string, any> | null
  expected_response: {
    assertions: Assertion[]
  } | null
  is_enabled: boolean
  created_at: string
  updated_at: string | null
}

export interface Assertion {
  type: 'status' | 'jsonpath' | 'header' | 'regex'
  field: string
  expected: any
  description?: string
}

export interface TestResult {
  id: number
  test_case_id: number
  status: string
  response_data: Record<string, any> | null
  response_time: number
  error_message: string | null
  assertion_results: AssertionResult[]
  executed_at: string
}

export interface AssertionResult {
  assertion_type: string
  field: string
  expected: any
  actual: any
  passed: boolean
  description?: string
  error_message?: string
}

export interface CreateTestCaseRequest {
  endpoint_id: number
  name: string
  description?: string
  request_config: {
    method: string
    url: string
    headers?: Record<string, string>
    params?: Record<string, string>
    body?: any
    timeout?: number
  }
  test_data?: Record<string, any>
  assertions: Assertion[]
  is_enabled?: boolean
}

export interface UpdateTestCaseRequest {
  name?: string
  description?: string
  request_config?: {
    method: string
    url: string
    headers?: Record<string, string>
    params?: Record<string, string>
    body?: any
    timeout?: number
  }
  test_data?: Record<string, any>
  assertions?: Assertion[]
  is_enabled?: boolean
}

export interface TestExecutionRequest {
  test_case_ids: number[]
  base_url?: string
}

export interface TestExecutionResponse {
  total: number
  passed: number
  failed: number
  error: number
  skipped: number
  results: TestResult[]
  execution_time: number
}

export const testCasesApi = {
  // 列出所有测试用例（可按 endpoint_id 筛选）
  list: (endpointId?: number): Promise<TestCase[]> => {
    const params = endpointId ? `?endpoint_id=${endpointId}` : ''
    return apiClient.get(`/test-cases${params}`)
  },

  // 获取单个测试用例
  getById: (testCaseId: number): Promise<TestCase> => {
    return apiClient.get(`/test-cases/${testCaseId}`)
  },

  // 创建测试用例
  create: (data: CreateTestCaseRequest): Promise<TestCase> => {
    return apiClient.post('/test-cases', data)
  },

  // 更新测试用例
  update: (testCaseId: number, data: UpdateTestCaseRequest): Promise<TestCase> => {
    return apiClient.put(`/test-cases/${testCaseId}`, data)
  },

  // 删除测试用例
  delete: (testCaseId: number): Promise<void> => {
    return apiClient.delete(`/test-cases/${testCaseId}`)
  },

  // 批量执行测试用例
  execute: (testCaseIds: number[], baseUrl?: string): Promise<TestExecutionResponse> => {
    return apiClient.post('/test-cases/execute', {
      test_case_ids: testCaseIds,
      base_url: baseUrl
    })
  },

  // 获取测试用例的历史结果
  getResults: (testCaseId: number): Promise<TestResult[]> => {
    return apiClient.get(`/test-cases/${testCaseId}/results`)
  }
}
