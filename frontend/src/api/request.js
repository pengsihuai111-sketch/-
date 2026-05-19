import axios from 'axios'
import { ElMessage } from 'element-plus'
import { getToken, removeToken } from '../utils/storage'

const request = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

request.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    if (err.response?.status === 401) {
      removeToken()
      window.location.href = '/login'
      return Promise.reject(err)
    }
    ElMessage.error(msg)
    return Promise.reject(err)
  }
)

export default request
