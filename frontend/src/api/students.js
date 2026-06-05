import api from './client'

export const studentsApi = {
  // Students
  getStudents: (params) => api.get('/students/', { params }),
  getStudent: (id) => api.get(`/students/${id}/`),
  createStudent: (data, config = {}) => {
    if (data instanceof FormData) {
      return api.post('/students/', data, {
        headers: { 'Content-Type': 'multipart/form-data' },
        ...config,
      })
    }
    return api.post('/students/', data, config)
  },
  updateStudent: (id, data, config = {}) => {
    if (data instanceof FormData) {
      return api.patch(`/students/${id}/`, data, {
        headers: { 'Content-Type': 'multipart/form-data' },
        ...config,
      })
    }
    return api.patch(`/students/${id}/`, data, config)
  },
  deleteStudent: (id) => api.delete(`/students/${id}/`),

  // Classrooms
  getClassrooms: (params) => api.get('/students/classrooms/', { params }),
  getClassroom: (id) => api.get(`/students/classrooms/${id}/`),
  createClassroom: (data) => api.post('/students/classrooms/', data),
  getClassroomStudents: (id, params) => api.get(`/students/classrooms/${id}/students/`, { params }),

  // Guardians
  getGuardians: (params) => api.get('/students/guardians/', { params }),
  createGuardian: (data) => api.post('/students/guardians/', data),

  // Search & Transfer
  searchStudents: (query) => api.get('/students/search/', { params: { q: query } }),
  transferStudent: (id, classroomId) => api.post(`/students/${id}/transfer/`, { classroom: classroomId }),
  updateStudentStatus: (id, studentStatus) => api.post(`/students/${id}/archive/`, { status: studentStatus }),
  archiveStudent: (id, archiveStatus) => api.post(`/students/${id}/archive/`, { status: archiveStatus }),
  promoteAllStudents: () => api.post('/students/promote-all/', { confirm: true }),
  bulkImport: (data) => api.post('/students/bulk-import/', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  downloadImportTemplate: () => api.get('/students/import-template/', {
    responseType: 'blob',
  }),
}
