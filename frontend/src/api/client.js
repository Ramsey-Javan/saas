import axios from 'axios'
import { useAuthStore } from '@/store/authStore'

/**
 * Determines the API base URL from the current subdomain 
 * 
 * In production:
 *    stmarys.myapp.co.ke -> https://stmarys.myapp.co.ke/api
 * 
 * In local dev:
 *    localhost:3000 -> http://localhost:8000/api (via Vite proxy)
 */

function getBaseURL() {
  const hostname = window.location.hostname

  if (hostname === 'localhost' || hostname === '127.0.0.1' ) {
    return '/api'
  } 

  // extract sub domains for production 
  const parts = hostname.split('.')
  if (parts.length >= 3) {
    return `https://${hostname}/api`
  }

  return '/api' // default fallback
}

const api = axios.create({
  baseURL: getBaseURL(),
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // include cookies for authentication
})

// __ Request interceptor: attach JWT Access token ________________________
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}, 
  (error) => Promise.reject(error)
)

// ____ Response interceptor: auto-refresh on 401 ________________________

let isRefreshing = false
let refreshQueue = []

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config

    if (error.response?.status === 401 && !original._retry) {
      if (isRefreshing) {
        // Queue requests while refreshing
        return new Promise((resolve, reject) => {
          refreshQueue.push({ resolve, reject })
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return api(original)
        })
      }

      original._retry = true
      isRefreshing = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        useAuthStore.getState().logout()
        return Promise.reject(error)
      }

      try {
        const { data } = await axios.post(`${getBaseURL()}/auth/token/refresh/`, {
          refresh: refreshToken,
        })

        const newAccess = data.access
        localStorage.setItem('access_token', newAccess)

        refreshQueue.forEach(({ resolve }) => resolve(newAccess))
        refreshQueue = []

        original.headers.Authorization = `Bearer ${newAccess}`
        return api(original)
      } catch (refreshError) {
        refreshQueue.forEach(({ reject }) => reject(refreshError))
        refreshQueue = []
        useAuthStore.getState().logout()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export default api