import apiClient from './index'

export interface TestCase {
  id: number
  project_id: number
  name: string
  method: string
  path: string
  headers: Record<string, string>
  body: string
  expected_status: number
  created_at: string
  updated_at: string
}

export interface TestCaseListResponse {
  data: TestCase[]
  total: number
}

export interface CreateTestCaseRequest {
  project_id: number
  name: string
  method: string
  path: string
  headers?: Record<string, string>
  body?: string
  expected_status?: number
}

export interface TestResult {
  id: number
  test_case_id: number
  status: string
  response_status: number
  response_body: string
  response_time: number
  executed_at: string
}

export const testCasesApi = {
  list: (projectId: number): Promise<TestCaseListResponse> => {
    return apiClient.get(`/projects/${projectId}/test-cases`)
  },

  getById: (projectId: number, testCaseId: number): Promise<TestCase> => {
    return apiClient.get(`/projects/${projectId}/test-cases/${testCaseId}`)
  },

  create: (data: CreateTestCaseRequest): Promise<TestCase> => {
    return apiClient.post('/test-cases', data)
  },

  update: (projectId: number, testCaseId: number, data: Partial<CreateTestCaseRequest>): Promise<TestCase> => {
    return apiClient.put(`/projects/${projectId}/test-cases/${testCaseId}`, data)
  },

  delete: (projectId: number, testCaseId: number): Promise<void> => {
    return apiClient.delete(`/projects/${projectId}/test-cases/${testCaseId}`)
  },

  execute: (projectId: number, testCaseId: number): Promise<TestResult> => {
    return apiClient.post(`/projects/${projectId}/test-cases/${testCaseId}/execute`)
  },

  getResults: (projectId: number, testCaseId: number): Promise<TestResult[]> => {
    return apiClient.get(`/projects/${projectId}/test-cases/${testCaseId}/results`)
  }
}
