import api from './client'

export const communicationApi = {
  getTemplates: (params) => api.get('/communication/templates/', { params }),
  createTemplate: (data) => api.post('/communication/templates/', data),
  updateTemplate: (id, data) => api.patch(`/communication/templates/${id}/`, data),
  deleteTemplate: (id) => api.delete(`/communication/templates/${id}/`),
  previewTemplate: (id, vars) =>
    api.post(`/communication/templates/${id}/preview/`, { template_vars: vars }),

  getAnnouncements: (params) => api.get('/communication/announcements/', { params }),
  createAnnouncement: (data) => api.post('/communication/announcements/', data),
  updateAnnouncement: (id, data) => api.patch(`/communication/announcements/${id}/`, data),
  sendAnnouncement: (id) => api.post(`/communication/announcements/${id}/send/`),
  cancelAnnouncement: (id) => api.post(`/communication/announcements/${id}/cancel/`),

  getLogs: (params) => api.get('/communication/logs/', { params }),
  getLogSummary: () => api.get('/communication/logs/summary/'),

  getNotifications: (params) => api.get('/communication/notifications/', { params }),
  markRead: (ids) => api.post('/communication/notifications/mark-read/', { ids }),
  markAllRead: () => api.post('/communication/notifications/mark-all-read/'),
  getUnreadCount: () => api.get('/communication/notifications/unread-count/'),
}
