import { apiClient } from './client';

// Auth endpoints
export const authAPI = {
  login: (email, password) => apiClient.post('/auth/token/', { email, password }),
  refreshToken: (refreshToken) => apiClient.post('/auth/token/refresh/', { refresh: refreshToken }),
  getCurrentUser: () => apiClient.get('/auth/users/me/'),
};

// Student endpoints
export const studentAPI = {
  list: () => apiClient.get('/students/students/'),
  get: (id) => apiClient.get(`/students/students/${id}/`),
  create: (data) => apiClient.post('/students/students/', data),
  update: (id, data) => apiClient.put(`/students/students/${id}/`, data),
  delete: (id) => apiClient.delete(`/students/students/${id}/`),
};

// Finance endpoints
export const financeAPI = {
  getFeeStructures: () => apiClient.get('/finance/fee-structures/'),
  getPayments: () => apiClient.get('/finance/payments/'),
  createPayment: (data) => apiClient.post('/finance/payments/', data),
};

// Academics endpoints
export const academicsAPI = {
  getClasses: () => apiClient.get('/academics/classes/'),
  getGrades: () => apiClient.get('/academics/grades/'),
  getAttendance: () => apiClient.get('/academics/attendance/'),
};

// Communication endpoints
export const communicationAPI = {
  getNotifications: () => apiClient.get('/communication/notifications/'),
  getSMSLogs: () => apiClient.get('/communication/sms-logs/'),
};

// Tenants endpoints
export const tenantsAPI = {
  list: () => apiClient.get('/tenants/'),
  get: (id) => apiClient.get(`/tenants/${id}/`),
};
