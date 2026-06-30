import api from './client'

export const platformApi = {
  getSchools: (params) => api.get('/platform/platform-schools/', { params }),
  getSchool: (id) => api.get(`/platform/platform-schools/${id}/`),
  createSchool: (data) => api.post('/platform/platform-schools/', data),
  toggleActive: (id) => api.patch(`/platform/platform-schools/${id}/toggle-active/`),
  changePlan: (id, plan) => api.patch(`/platform/platform-schools/${id}/change-plan/`, { plan }),
  seedDemoData: (id) => api.post(`/platform/platform-schools/${id}/seed-demo-data/`),
  getPlatformStats: () => api.get('/platform/platform-schools/stats/'),
  onboardSchool: (data) => api.post('/platform/schools/onboard/', data),
  checkSubdomainAvailability: (subdomain) => api.get('/platform/schools/check-subdomain/', {
    params: { subdomain },
  }),
}