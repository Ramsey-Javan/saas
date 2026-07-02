import axios from 'axios'
import { useAuthStore } from '@/store/authStore'
import { toastBus } from '@/lib/toastBus'

function getBaseURL() {
  const hostname = window.location.hostname

  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return '/api'
  }

  const parts = hostname.split('.')
  if (parts.length >= 3) {
    return `https://${hostname}/api`
  }

  return '/api'
}

const api = axios.create({
  baseURL: getBaseURL(),
  headers: { 'Content-Type': 'application/json' },
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

    if (error.response?.status === 401 && !original._retry) {
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
        const { data } = await axios.post(`${getBaseURL()}/auth/token/refresh/`, {
          refresh: refreshToken,
        })

        const newAccess = data.access
        // Use setAccessToken, NOT setAuth, here. setAuth(user, newAccess,
        // refreshToken) with no 4th arg defaults `tenant` to null, which
        // was wiping `school` (and therefore all branding) back to
        // defaults on every silent refresh -- this was the root cause of
        // theming "resetting after some time." setAccessToken only ever
        // touches the access token.
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

    toastBus.emit(
      error.response?.data?.message || 'Something went wrong.',
      'error'
    )
    return Promise.reject(error)
  }
)

export default api