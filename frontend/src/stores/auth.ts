import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import apiClient from '@/api'

export interface User {
  id: number
  username: string
  email: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface RegisterResponse {
  id: number
  username: string
  email: string
  created_at: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)

  const isLoggedIn = computed(() => !!token.value)

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const response = await (apiClient.post('/auth/login', {
        email,
        password
      }) as Promise<LoginResponse>)
      token.value = response.access_token
      localStorage.setItem('token', response.access_token)
      ElMessage.success('登录成功')
      return true
    } catch (error) {
      return false
    }
  }

  const logout = () => {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    ElMessage.success('已退出登录')
  }

  const register = async (username: string, email: string, password: string): Promise<boolean> => {
    try {
      await (apiClient.post('/auth/register', {
        username,
        email,
        password
      }) as Promise<RegisterResponse>)
      ElMessage.success('注册成功，请登录')
      return true
    } catch (error) {
      return false
    }
  }

  const getToken = () => {
    return token.value
  }

  return {
    token,
    user,
    isLoggedIn,
    login,
    logout,
    register,
    getToken
  }
})
