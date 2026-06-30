import api from './client'

export const dashboardApi = {
  getStats: (timeRange = '30d') => api.get('/dashboard/stats/', { params: { time_range: timeRange } }),
  getUpcomingEvents: () => api.get('/dashboard/upcoming-events/'),
  createSchoolEvent: (data) => api.post('/dashboard/events/', data),
  deleteSchoolEvent: (id) => api.delete(`/dashboard/events/${id}/`),

}