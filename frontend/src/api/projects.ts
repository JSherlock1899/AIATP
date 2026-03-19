import apiClient from './index'

export interface Project {
  id: number
  name: string
  description: string
  project_key: string
  created_at: string
  updated_at: string
}

export interface ProjectListResponse {
  data: Project[]
  total: number
}

export interface CreateProjectRequest {
  name: string
  description: string
  project_key: string
}

export const projectsApi = {
  list: (): Promise<ProjectListResponse> => {
    return apiClient.get('/projects')
  },

  getById: (id: number): Promise<Project> => {
    return apiClient.get(`/projects/${id}`)
  },

  create: (data: CreateProjectRequest): Promise<Project> => {
    return apiClient.post('/projects', data)
  },

  update: (id: number, data: Partial<CreateProjectRequest>): Promise<Project> => {
    return apiClient.put(`/projects/${id}`, data)
  },

  delete: (id: number): Promise<void> => {
    return apiClient.delete(`/projects/${id}`)
  }
}
