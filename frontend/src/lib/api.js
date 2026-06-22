import axios from 'axios'
import { useToastStore } from '../store/toast'

const api = axios.create({ baseURL: '/api/v1' })

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('ms_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

api.interceptors.response.use(
  r => r,
  err => {
    const status = err.response?.status
    if (status === 401) {
      localStorage.removeItem('ms_token')
      window.location.href = '/login'
    } else if (status && status !== 404) {
      const detail = err.response?.data?.detail
      const msg = typeof detail === 'string'
        ? detail
        : `Greška servera (${status}): ${err.config?.url || ''}`
      useToastStore.getState().push(msg)
    } else if (!err.response) {
      useToastStore.getState().push('Server nije dostupan. Proveri konekciju.')
    }
    return Promise.reject(err)
  }
)

export default api
