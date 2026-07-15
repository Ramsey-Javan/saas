import client from './client'

// FIX: Removed /api prefix — client.js already adds it
const BASE = '/analytics'

// ── BUG FIX: the backend's canonical term values are 'term1'/'term2'/
// 'term3' (matching ExamSetup.term's own choices exactly) -- but every
// page in this app tracks the term as a human label ("Term 1", "Term 2",
// "Term 3") for display. Rather than touch every page's state/UI, this
// converts at the API boundary only, right before each request goes out.
function toCanonicalTerm(term) {
  if (!term) return term
  const map = { 'Term 1': 'term1', 'Term 2': 'term2', 'Term 3': 'term3' }
  return map[term] || term
}

export function fetchSchoolSummary(academicYear) {
  return client.get(`${BASE}/school-summary/`, { params: { academic_year: academicYear } })
}

export function fetchClassPerformance(classroomId, term, academicYear) {
  return client.get(`${BASE}/class-performance/`, {
    params: { classroom_id: classroomId, term: toCanonicalTerm(term), academic_year: academicYear },
  })
}

export function fetchStudentPerformance(studentId, term, academicYear) {
  return client.get(`${BASE}/student-performance/`, {
    params: { student_id: studentId, term: toCanonicalTerm(term), academic_year: academicYear },
  })
}

export function fetchStudentLongitudinal(studentId, academicYear) {
  return client.get(`${BASE}/student-longitudinal/`, {
    params: { student_id: studentId, academic_year: academicYear },
  })
}

export function fetchSubjectComparison(classroomId, term, academicYear) {
  return client.get(`${BASE}/subject-comparison/`, {
    params: { classroom_id: classroomId, term: toCanonicalTerm(term), academic_year: academicYear },
  })
}

export function fetchGradeDistribution(classroomId, examType, term, academicYear) {
  return client.get(`${BASE}/grade-distribution/`, {
    params: { classroom_id: classroomId, exam_type: examType, term: toCanonicalTerm(term), academic_year: academicYear },
  })
}

export function fetchEarlyWarning(term, academicYear) {
  return client.get(`${BASE}/early-warning/`, {
    params: { term: toCanonicalTerm(term), academic_year: academicYear },
  })
}

export function fetchCohortReference(classroomId, subjectId, term, academicYear) {
  return client.get(`${BASE}/cohort-reference/`, {
    params: { classroom_id: classroomId, subject_id: subjectId, term: toCanonicalTerm(term), academic_year: academicYear },
  })
}

export function fetchClassRanking(classroomId, term, academicYear) {
  return client.get(`${BASE}/class-ranking/`, {
    params: { classroom_id: classroomId, term: toCanonicalTerm(term), academic_year: academicYear },
  })
}

export function fetchSchoolClassrooms(term, academicYear) {
  return client.get(`${BASE}/school-classrooms/`, {
    params: { term: toCanonicalTerm(term), academic_year: academicYear },
  })
}

export function fetchSubjectSchoolAnalysis(subjectId, term, academicYear) {
  return client.get(`${BASE}/subject-school-analysis/`, {
    params: { subject_id: subjectId, term: toCanonicalTerm(term), academic_year: academicYear },
  })
}

export function fetchTeacherScope() {
  return client.get(`${BASE}/teacher-scope/`);
}

export function fetchSubjectTeacherSummary(academicYear, term = null) {
  const params = { academic_year: academicYear };
  if (term) params.term = toCanonicalTerm(term);
  return client.get(`${BASE}/subject-teacher-summary/`, { params });
}

export function fetchSubjectTeacherClassrooms(subjectId, academicYear, term = null) {
  const params = { subject_id: subjectId, academic_year: academicYear };
  if (term) params.term = toCanonicalTerm(term);
  return client.get(`${BASE}/subject-teacher-classrooms/`, { params });
}