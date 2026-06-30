import api from './client'

export const staffApi = {
  getStaff: (params) => api.get('/auth/staff/', { params }),
  getStaffMember: (id) => api.get(`/auth/staff/${id}/`),
  onboardStaff: (data) => api.post('/auth/staff/onboard/', data),
  updateStaff: (id, data) => api.patch(`/auth/staff/${id}/`, data),
  updateStaffProfile: (id, data) => api.patch(`/auth/staff/${id}/`, data),
  changeStaffRole: (id, role) => api.post(`/auth/staff/${id}/change-role/`, { role }),
  getAssignments: (id) => api.get(`/auth/staff/${id}/assignments/`),
  deactivateStaff: (id, data) => api.post(`/auth/staff/${id}/deactivate/`, data),
  sendInvite: (id, data) => api.post(`/auth/staff/${id}/send-invite/`, data),
  getInvites: (params) => api.get('/auth/staff-invites/', { params }),
  resendInvite: (id) => api.post(`/auth/staff-invites/${id}/resend/`),
  cancelInvite: (id) => api.post(`/auth/staff-invites/${id}/cancel/`),
  checkInvite: (token) => api.get('/auth/invite-check/', { params: { token } }),
  acceptInvite: (token, password) => api.post('/auth/accept-invite/', { token, password }),
  getSchoolProfile: () => api.get('/auth/school-profile/'),
  updateSchoolProfile: (data) => api.patch('/auth/school-profile/', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
}
