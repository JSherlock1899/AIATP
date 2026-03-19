import apiClient from './index'

export interface SourceCodeProject {
  id: number
  project_id: number
  name: string
  source_path: string
  language: string
  status: 'pending' | 'parsing' | 'completed' | 'failed'
  error_message?: string
  endpoints_count: number
  created_at: string
  parsed_at?: string
}

export interface ParseRequest {
  project_id: number
  name: string
  source_path: string
}

export interface ParseResponse {
  id: number
  name: string
  source_path: string
  status: string
  endpoints_count: number
  message?: string
}

export interface Endpoint {
  id: number
  path: string
  method: string
  summary?: string
  description?: string
  parameters: Array<{
    name: string
    location: string
    required: boolean
  }>
  request_body?: any
  responses: any[]
}

export const sourceCodeApi = {
  parse: (projectId: number, data: ParseRequest): Promise<ParseResponse> => {
    return apiClient.post(`/projects/${projectId}/source-code/parse`, data)
  },

  list: (projectId: number): Promise<SourceCodeProject[]> => {
    return apiClient.get(`/projects/${projectId}/source-code`)
  },

  get: (projectId: number, sourceProjectId: number): Promise<SourceCodeProject> => {
    return apiClient.get(`/projects/${projectId}/source-code/${sourceProjectId}`)
  },

  getEndpoints: (projectId: number, sourceProjectId: number): Promise<Endpoint[]> => {
    return apiClient.get(`/projects/${projectId}/source-code/${sourceProjectId}/endpoints`)
  },

  delete: (projectId: number, sourceProjectId: number): Promise<void> => {
    return apiClient.delete(`/projects/${projectId}/source-code/${sourceProjectId}`)
  }
}
