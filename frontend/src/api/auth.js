import api from './client'  

export const authAPI = {
  login: (credentials) => api.post('/auth/login/', credentials),
  register: (data) => api.post('/auth/register/', data),
  refresh: (refreshToken) => api.post('/auth/token/refresh/', { refresh: refreshToken }),
  verify: (token) => api.post('/auth/token/verify/', { token }),
  logout: () => api.post('/auth/logout/'),
}