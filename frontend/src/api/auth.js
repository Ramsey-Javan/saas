import api from './client'

export const authAPI = {
  login: ({ email, password }) => api.post('/auth/token/', { email, password }),
  register: (data) => api.post('/auth/register/', data),
  refresh: (refreshToken) => api.post('/auth/token/refresh/', { refresh: refreshToken }),
  verify: (token) => api.post('/auth/token/verify/', { token }),
  logout: () => api.post('/auth/logout/'),
  changePassword: ({ old_password, new_password }) =>
    api.post('/auth/users/change-password/', { old_password, new_password }),

  // ── Forgot password ──
  requestPasswordReset: (email) =>
    api.post('/auth/password-reset-request/', { email }),
  checkPasswordResetToken: (uid, token) =>
    api.get('/auth/password-reset-check/', { params: { uid, token } }),
  confirmPasswordReset: ({ uid, token, new_password }) =>
    api.post('/auth/password-reset-confirm/', { uid, token, new_password }),
}