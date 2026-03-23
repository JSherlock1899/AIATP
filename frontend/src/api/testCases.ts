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

export type AssertionType = 'status' | 'jsonpath' | 'header' | 'regex' | 'response_time' | 'json_size' | 'array_count' | 'range'

export interface Assertion {
  type: AssertionType
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

// SSE event types
export interface StreamProgress {
  current: number
  total: number
  test_case_id: number
  status: 'running'
  passed: number
  failed: number
  error: number
  skipped: number
}

export interface StreamResult {
  test_case_id: number
  result_id?: number
  status: string
  response_time: number
  error_message?: string
  assertion_results: AssertionResult[]
  passed: boolean
  passed_count: number
  failed_count: number
  error_count: number
  skipped_count: number
}

export interface StreamComplete {
  total: number
  passed: number
  failed: number
  error: number
  skipped: number
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

  // 流式执行测试用例（SSE）- 使用 fetch + ReadableStream 替代 EventSource
  executeStream: (
    testCaseIds: number[],
    baseUrl: string | undefined,
    callbacks: {
      onProgress?: (data: StreamProgress) => void
      onResult?: (data: StreamResult) => void
      onComplete?: (data: StreamComplete) => void
      onError?: (error: Error) => void
    }
  ): (() => void) => {
    const { onProgress, onResult, onComplete, onError } = callbacks
    let aborted = false

    // Use fetch with ReadableStream for POST request with streaming response
    fetch(`${apiClient.defaults.baseURL}/test-cases/execute/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        test_case_ids: testCaseIds,
        base_url: baseUrl
      })
    }).then(async response => {
      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      try {
        while (true) {
          if (aborted) break
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (aborted) break
            if (line.startsWith('event: ')) {
              const eventType = line.slice(7)
              continue
            }
            if (line.startsWith('data: ')) {
              const data = line.slice(6)
              try {
                const parsed = JSON.parse(data)
                if (eventType === 'progress') {
                  onProgress?.(parsed)
                } else if (eventType === 'result') {
                  onResult?.(parsed)
                } else if (eventType === 'complete') {
                  onComplete?.(parsed)
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', e)
              }
            }
          }
        }
      } finally {
        reader.releaseLock()
      }
    }).catch(err => {
      console.error('Stream error:', err)
      if (!aborted) {
        onError?.(err instanceof Error ? err : new Error('Stream error'))
      }
    })

    // Return cleanup function
    return () => {
      aborted = true
    }
  },

  // 获取测试用例的历史结果
  getResults: (testCaseId: number): Promise<TestResult[]> => {
    return apiClient.get(`/test-cases/${testCaseId}/results`)
  }
}
