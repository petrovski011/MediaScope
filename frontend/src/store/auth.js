import { create } from 'zustand'
import api from '../lib/api'

export const useAuth = create((set) => ({
  user: null,
  token: localStorage.getItem('ms_token'),

  login: async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('ms_token', data.access_token)
    set({ token: data.access_token, user: data.user })
    return data
  },

  logout: () => {
    localStorage.removeItem('ms_token')
    set({ token: null, user: null })
  },

  fetchMe: async () => {
    const { data } = await api.get('/auth/me')
    set({ user: data })
    return data
  },
}))
