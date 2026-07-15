import { useQuery } from '@tanstack/react-query';
import {
  fetchSchoolSummary,
  fetchEarlyWarning,
  fetchSchoolClassrooms,
  fetchClassPerformance,
  fetchStudentPerformance,
  fetchStudentLongitudinal,
  fetchSubjectComparison,
  fetchGradeDistribution,
  fetchCohortReference,
  fetchClassRanking,
  fetchSubjectSchoolAnalysis,
  fetchTeacherScope,
  fetchSubjectTeacherSummary,
  fetchSubjectTeacherClassrooms,
} from '../api/analytics';

const STALE_TIME_LIVE = 5 * 60 * 1000;
const STALE_TIME_HISTORICAL = 60 * 60 * 1000;

function getStaleTime(academicYear) {
  const currentYear = new Date().getFullYear();
  return academicYear >= currentYear - 1 ? STALE_TIME_LIVE : STALE_TIME_HISTORICAL;
}

// ------------------------------------------------------------------
// Helpers to normalize axios responses (works whether client.js
// returns the raw response object or response.data directly).
// ------------------------------------------------------------------
function unwrap(response) {
  // Axios response object: { data, status, headers, ... }
  if (response && typeof response === 'object' && 'data' in response) {
    return response.data;
  }
  // Already unwrapped
  return response;
}

function isBackendEmptyPayload(data) {
  return (
    data &&
    typeof data === 'object' &&
    (data.empty === true || data._empty === true)
  );
}

// ------------------------------------------------------------------
// Normalizer: passes healthy data through, turns structured "no data"
// responses into a stable empty-state object that components can
// render with <EmptyState> instead of crashing.
// ------------------------------------------------------------------
function normalize(data) {
  const payload = unwrap(data);

  // Structured backend empty state: { empty: true, error, suggestion, filters }
  if (isBackendEmptyPayload(payload)) {
    // Keep the payload intact so the UI can read error / suggestion / filters.
    // Components should check `data.empty` to decide whether to render
    // charts or an EmptyState.
    return payload;
  }

  // Legacy defensive check: some older endpoints return { code, message }
  // for permission errors.  We still want to throw real errors.
  if (
    payload &&
    typeof payload === 'object' &&
    'code' in payload &&
    'message' in payload
  ) {
    const err = new Error(payload.message);
    err.code = payload.code;
    err.details = payload.details;
    throw err;
  }

  return payload;
}

// ------------------------------------------------------------------
// Hooks
// ------------------------------------------------------------------

export function useSchoolSummary(academicYear, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'school-summary', academicYear],
    queryFn: () => fetchSchoolSummary(academicYear).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!academicYear,
    ...options,
  });
}

export function useClassPerformance(classroomId, term, academicYear, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'class-performance', classroomId, term, academicYear],
    queryFn: () => fetchClassPerformance(classroomId, term, academicYear).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!classroomId && !!term && !!academicYear,
    ...options,
  });
}

export function useStudentPerformance(studentId, term, academicYear, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'student-performance', studentId, term, academicYear],
    queryFn: () => fetchStudentPerformance(studentId, term, academicYear).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!studentId && !!term && !!academicYear,
    ...options,
  });
}

export function useStudentLongitudinal(studentId, academicYear, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'student-longitudinal', studentId, academicYear],
    queryFn: () => fetchStudentLongitudinal(studentId, academicYear).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!studentId && !!academicYear,
    ...options,
  });
}

export function useSubjectComparison(classroomId, term, academicYear, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'subject-comparison', classroomId, term, academicYear],
    queryFn: () => fetchSubjectComparison(classroomId, term, academicYear).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!classroomId && !!term && !!academicYear,
    ...options,
  });
}

export function useGradeDistribution(classroomId, examType, term, academicYear, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'grade-distribution', classroomId, examType, term, academicYear],
    queryFn: () => fetchGradeDistribution(classroomId, examType, term, academicYear).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!classroomId && !!examType && !!term && !!academicYear,
    ...options,
  });
}

export function useEarlyWarning(term, academicYear, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'early-warning', term, academicYear],
    queryFn: () => fetchEarlyWarning(term, academicYear).then(normalize),
    staleTime: STALE_TIME_LIVE,
    enabled: !!term && !!academicYear,
    ...options,
  });
}

export function useCohortReference(classroomId, subjectId, term, academicYear, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'cohort-reference', classroomId, subjectId, term, academicYear],
    queryFn: () => fetchCohortReference(classroomId, subjectId, term, academicYear).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!classroomId && !!subjectId && !!term && !!academicYear,
    ...options,
  });
}

export function useClassRanking(classroomId, term, academicYear, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'class-ranking', classroomId, term, academicYear],
    queryFn: () => fetchClassRanking(classroomId, term, academicYear).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!classroomId && !!term && !!academicYear,
    ...options,
  });
}

export function useSchoolClassrooms(term, academicYear, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'school-classrooms', term, academicYear],
    queryFn: () => fetchSchoolClassrooms(term, academicYear).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!term && !!academicYear,
    ...options,
  });
}

export function useSubjectSchoolAnalysis(subjectId, term, academicYear, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'subject-school-analysis', subjectId, term, academicYear],
    queryFn: () => fetchSubjectSchoolAnalysis(subjectId, term, academicYear).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!subjectId && !!term && !!academicYear,
    ...options,
  });
}

export function useTeacherScope(options = {}) {
  return useQuery({
    queryKey: ['analytics', 'teacher-scope'],
    queryFn: () => fetchTeacherScope().then(normalize),
    staleTime: STALE_TIME_LIVE,
    ...options,
  });
}

export function useSubjectTeacherSummary(academicYear, term, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'subject-teacher-summary', academicYear, term],
    queryFn: () => fetchSubjectTeacherSummary(academicYear, term).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!academicYear,
    ...options,
  });
}

export function useSubjectTeacherClassrooms(subjectId, academicYear, term, options = {}) {
  return useQuery({
    queryKey: ['analytics', 'subject-teacher-classrooms', subjectId, academicYear, term],
    queryFn: () => fetchSubjectTeacherClassrooms(subjectId, academicYear, term).then(normalize),
    staleTime: getStaleTime(academicYear),
    enabled: !!subjectId && !!academicYear,
    ...options,
  });
}