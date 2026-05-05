import api from './client'  

export const authAPI = {
  login: ({ email, password }) => api.post('/auth/token/', { email, password }),
  register: (data) => api.post('/auth/register/', data),
  refresh: (refreshToken) => api.post('/auth/token/refresh/', { refresh: refreshToken }),
  verify: (token) => api.post('/auth/token/verify/', { token }),
  logout: () => api.post('/auth/logout/'),
}