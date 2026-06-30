import api from './client'

export const academicsApi = {
  getSubjects: (params) => api.get('/academics/subjects/', { params }),
  getSubject: (id) => api.get(`/academics/subjects/${id}/`),
  createSubject: (data) => api.post('/academics/subjects/', data),
  updateSubject: (id, data) => api.patch(`/academics/subjects/${id}/`, data),
  deleteSubject: (id) => api.delete(`/academics/subjects/${id}/`),
  loadCurriculum: () => api.post('/academics/subjects/load-curriculum/'),

  getStrands: (params) => api.get('/academics/strands/', { params }),
  createStrand: (data) => api.post('/academics/strands/', data),
  updateStrand: (id, data) => api.patch(`/academics/strands/${id}/`, data),
  deleteStrand: (id) => api.delete(`/academics/strands/${id}/`),

  getSubStrands: (params) => api.get('/academics/sub-strands/', { params }),
  createSubStrand: (data) => api.post('/academics/sub-strands/', data),
  updateSubStrand: (id, data) => api.patch(`/academics/sub-strands/${id}/`, data),
  deleteSubStrand: (id) => api.delete(`/academics/sub-strands/${id}/`),

  getOutcomes: (params) => api.get('/academics/outcomes/', { params }),
  createOutcome: (data) => api.post('/academics/outcomes/', data),
  updateOutcome: (id, data) => api.patch(`/academics/outcomes/${id}/`, data),
  deleteOutcome: (id) => api.delete(`/academics/outcomes/${id}/`),

  getAssignments: (params) => api.get('/academics/assignments/', { params }),
  getMyClasses: () => api.get('/academics/assignments/my-classes/'),
  createAssignment: (data) => api.post('/academics/assignments/', data),
  updateAssignment: (id, data) => api.patch(`/academics/assignments/${id}/`, data),
  deleteAssignment: (id) => api.delete(`/academics/assignments/${id}/`),

  // Grades & Performance
  getGrades: (params) => api.get('/academics/grades/', { params }),
  createGrade: (data) => api.post('/academics/grades/', data),
  bulkGrade: (data) => api.post('/academics/grades/bulk/', data),
  importGradesCSV: (formData) => api.post('/academics/grades/import-csv/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  getStudentReport: (params) => api.get('/academics/grades/student-report/', { params }),
  getGradeSheet: (params) => api.get('/academics/grades/grade-sheet/', { params }),
  getClassExamAverage: (params) => api.get('/academics/grades/class-exam-average/', { params }),

  getExamConfig: () => api.get('/academics/exam-config/'),
  updateExamConfig: (data) => api.put('/academics/exam-config/', data),

  getExamSetups: (params) => api.get('/academics/exam-setups/', { params }),
  getExamSetup: (id) => api.get(`/academics/exam-setups/${id}/`),
  createExamSetup: (data) => api.post('/academics/exam-setups/', data),
  updateExamSetup: (id, data) => api.patch(`/academics/exam-setups/${id}/`, data),
  deleteExamSetup: (id) => api.delete(`/academics/exam-setups/${id}/`),
  addExamSubject: (id, data) => api.post(`/academics/exam-setups/${id}/subjects/`, data),
  getMarksSheet: (id) => api.get(`/academics/exam-setups/${id}/marks-sheet/`),
  syncToCBC: (id) => api.post(`/academics/exam-setups/${id}/sync-to-cbc/`),
  getSyncHistory: (id) => api.get(`/academics/exam-setups/${id}/sync-history/`),

  getExamResults: (params) => api.get('/academics/exam-results/', { params }),
  createExamResult: (data) => api.post('/academics/exam-results/', data),
  updateExamResult: (id, data) => api.patch(`/academics/exam-results/${id}/`, data),
  bulkEnterResults: (data) => api.post('/academics/exam-results/bulk/', data),
  importResultsCSV: (formData) => api.post('/academics/exam-results/import-csv/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  getStudentResults: (params) => api.get('/academics/exam-results/student-results/', { params }),

  getNationalSessions: (params) => api.get('/academics/national-exam-sessions/', { params }),
  getNationalSession: (id) => api.get(`/academics/national-exam-sessions/${id}/`),
  createNationalSession: (data) => api.post('/academics/national-exam-sessions/', data),
  updateNationalSession: (id, data) => api.patch(`/academics/national-exam-sessions/${id}/`, data),
  registerClass: (id) => api.post(`/academics/national-exam-sessions/${id}/register-class/`),
  downloadNationalExamCSV: (id) => api.get(`/academics/national-exam-sessions/${id}/download-csv/`, {
    responseType: 'blob',
  }),
  importNationalExamCSV: (id, formData) => api.post(`/academics/national-exam-sessions/${id}/import-csv/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  getCandidates: (params) => api.get('/academics/national-exam-candidates/', { params }),
  createCandidate: (data) => api.post('/academics/national-exam-candidates/', data),
  updateCandidate: (id, data) => api.patch(`/academics/national-exam-candidates/${id}/`, data),
  bulkUpdateIndexNumbers: (data) => api.post('/academics/national-exam-candidates/bulk-update-index/', data),
  getNationalResults: (params) => api.get('/academics/national-exam-results/', { params }),
  createNationalResult: (data) => api.post('/academics/national-exam-results/', data),
  updateNationalResult: (id, data) => api.patch(`/academics/national-exam-results/${id}/`, data),

  getSessions: (params) => api.get('/academics/sessions/', { params }),
  getSession: (id) => api.get(`/academics/sessions/${id}/`),
  createSession: (data) => api.post('/academics/sessions/', data),
  markAttendance: (sessionId, data) => api.post(`/academics/sessions/${sessionId}/mark/`, data),
  lockSession: (id) => api.patch(`/academics/sessions/${id}/lock/`),
  getTodaySessions: () => api.get('/academics/sessions/today/'),
  getStudentAttendanceSummary: (params) => api.get('/academics/sessions/student-summary/', { params }),
  getClassAttendanceSummary: (params) => api.get('/academics/sessions/class-summary/', { params }),

  getTimetables: (params) => api.get('/academics/timetables/', { params }),
  uploadTimetable: (formData) => api.post('/academics/timetables/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  deleteTimetable: (id) => api.delete(`/academics/timetables/${id}/`),

  getActivities: (params) => api.get('/academics/activities/', { params }),
  createActivity: (data) => api.post('/academics/activities/', data),
  getCoCurricular: (params) => api.get('/academics/co-curricular/', { params }),
  createCoCurricular: (data) => api.post('/academics/co-curricular/', data),
  updateCoCurricular: (id, data) => api.patch(`/academics/co-curricular/${id}/`, data),

  getReportCards: (params) => api.get('/academics/report-cards/', { params }),
  getReportCard: (id) => api.get(`/academics/report-cards/${id}/`),
  updateReportCard: (id, data) => api.patch(`/academics/report-cards/${id}/`, data),
  generateReportCards: (data) => api.post('/academics/report-cards/generate/', data),
  generateAnnualReportCards: (data) => api.post('/academics/report-cards/generate-annual/', data),
  publishReportCard: (id) => api.post(`/academics/report-cards/${id}/publish/`),
  getReportCardPdf: (id) => api.get(`/academics/report-cards/${id}/pdf/`, {
    responseType: 'blob',
  }),
  getStudentReportCards: (studentId) => api.get(`/academics/report-cards/student/${studentId}/`),
}