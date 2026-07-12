import axios from 'axios'
import { useAuthStore } from '@/store/authStore'
import { toastBus } from '@/lib/toastBus'

function getBaseURL() {
  if (import.meta.env.VITE_API_URL) {
    return `${import.meta.env.VITE_API_URL}/api`
  }
  // Use relative path so Vercel rewrites handle proxying to the backend
  return '/api'
}

const api = axios.create({
  baseURL: getBaseURL(),
  headers: { 
    'Content-Type': 'application/json',
    'Accept': 'application/json',  // Tells Django this is an API call
  },
  withCredentials: true,
})

api.interceptors.request.use(config => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  config.headers['Cache-Control'] = 'no-cache'
  return config
},
  (error) => Promise.reject(error)
)

let isRefreshing = false
let refreshQueue = []

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config

    // Handle Network error (no response at all)
    if (!error.response) {
      error.message = 'Network error. Please check your connection and try again.'
      toastBus.emit(error.message, 'error')
      return Promise.reject(error)
    }

    const { status, data, headers } = error.response
    const contentType = headers['content-type'] || ''

    // 1. JWT Token Refresh Logic (Kept intact)
    if (status === 401 && !original._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          refreshQueue.push({ resolve, reject })
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return api(original)
        })
      }
      original._retry = true
      isRefreshing = true
      const refreshToken = useAuthStore.getState().refreshToken
      if (!refreshToken) {
        useAuthStore.getState().logout()
        return Promise.reject(error)
      }
      try {
        const { data: refreshData } = await axios.post(`/api/auth/token/refresh/`, {
          refresh: refreshToken,
        })
        const newAccess = refreshData.access
        useAuthStore.getState().setAccessToken(newAccess)
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

    // 2. HTML Error Sanitization
    // If Django returned HTML (debug page, 404 page, etc.), replace it with clean JSON
    if (contentType.includes('text/html') || typeof data === 'string') {
      const messages = {
        400: 'Bad request. Please check your input and try again.',
        401: 'Your session has expired. Please log in again.',
        403: 'You do not have permission to perform this action.',
        404: 'The requested resource was not found.',
        405: 'This action is not allowed.',
        408: 'Request timed out. Please try again.',
        413: 'The request payload is too large.',
        422: 'The request could not be processed.',
        429: 'Too many requests. Please slow down.',
        500: 'Something went wrong on our end. Please try again later.',
        502: 'The server is temporarily unavailable. Please try again later.',
        503: 'The service is temporarily unavailable. Please try again later.',
      }

      error.response.data = {
        error: {
          code: `http_${status}`,
          message: messages[status] || `Server error (${status}). Please try again later.`,
          details: { url: original?.url }
        }
      }
    }

    // Update updated data reference after potential sanitization
    const updatedData = error.response.data

    // 3. Readable Error String Resolution
    if (updatedData?.error?.message) {
      error.message = updatedData.error.message
    } else if (updatedData?.message) {
      error.message = updatedData.message
    } else if (updatedData?.detail) {
      error.message = updatedData.detail
    } else if (updatedData?.non_field_errors?.[0]) {
      error.message = updatedData.non_field_errors[0]
    } else if (typeof updatedData === 'string' && updatedData.length > 0) {
      error.message = updatedData.substring(0, 200)
    } else {
      error.message = error.message || `Request failed with status ${status}`
    }

    // 4. Toast the clean, unified error string
    toastBus.emit(error.message, 'error')

    return Promise.reject(error)
  }
)

export default api
