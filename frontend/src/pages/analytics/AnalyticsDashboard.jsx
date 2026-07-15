import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart3,
  Users,
  FileText,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  ChevronRight,
  GraduationCap,
  BookOpen,
  Award,
  AlertCircle,
} from 'lucide-react';
import {
  useSchoolSummary,
  useEarlyWarning,
  useTeacherScope,
  useSubjectTeacherSummary,
} from '../../hooks/useAnalytics';
import {
  PerformanceTrendChart,
  ClassDistributionChart,
  EarlyWarningCard,
  DrillDownBreadcrumb,
  PerformanceBandBadge,
} from '../../components/analytics';
import EmptyState from '../../components/ui/EmptyState';
import { useAuthStore } from '../../store/authStore';
import PageHeader from '../../components/ui/PageHeader';
import Spinner from '../../components/ui/Spinner';

// ── MAIN ROUTER ─────────────────────────────────────────────────────
export default function AnalyticsDashboard() {
  const currentYear = new Date().getFullYear();
  const [academicYear, setAcademicYear] = useState(currentYear);
  const [selectedTerm, setSelectedTerm] = useState('Term 2');

  const { data: scopeData, isLoading: scopeLoading } = useTeacherScope();

  if (scopeLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-4" />
          <p className="text-gray-500">Loading analytics...</p>
        </div>
      </div>
    );
  }

  const isAdmin = scopeData?.is_admin;
  const isClassTeacher = scopeData?.is_class_teacher;
  const isSubjectTeacher = scopeData?.is_subject_teacher;
  const isPureSubjectTeacher = isSubjectTeacher && !isAdmin && !isClassTeacher;

  if (isPureSubjectTeacher) {
    return (
      <SubjectTeacherView
        academicYear={academicYear}
        selectedTerm={selectedTerm}
        onYearChange={setAcademicYear}
        onTermChange={setSelectedTerm}
      />
    );
  }

  return (
    <AdminClassTeacherView
      academicYear={academicYear}
      selectedTerm={selectedTerm}
      onYearChange={setAcademicYear}
      onTermChange={setSelectedTerm}
    />
  );
}

// ── SUBJECT TEACHER VIEW ───────────────────────────────────────────
function SubjectTeacherView({ academicYear, selectedTerm, onYearChange, onTermChange }) {
  const navigate = useNavigate();
  const currentYear = new Date().getFullYear();

  const {
    data: subjectTeacherData,
    isLoading,
    error,
  } = useSubjectTeacherSummary(academicYear, selectedTerm);

  const {
    data: warningData,
    isLoading: warningLoading,
    error: warningError,
  } = useEarlyWarning(selectedTerm, academicYear);

  // ── FIXED: unified "no data" detection ───────────────────────────
  // Handles: axios error, backend empty envelope, or truly empty data
  const hasWarningError = !!warningError;
  const hasWarningEmpty = warningData?.empty === true;
  const hasWarningData = warningData && !hasWarningEmpty && Array.isArray(warningData.students);

  const warningFallbackMessage = useMemo(() => {
    if (hasWarningError) {
      return warningError.message || 'Failed to load early warning data.';
    }
    if (hasWarningEmpty) {
      return warningData.suggestion || warningData.error || 'No exam results recorded for this term yet.';
    }
    return 'No data available for this term';
  }, [hasWarningError, hasWarningEmpty, warningError, warningData]);

  // FIXED: backend returns term_trend as [{subject_id, subject_name, terms: [{term, mean}]}]
  // We need to pivot to chart-friendly format: [{term: 'term1', subject_1: 45, subject_2: 60}]
  const { trendData, trendSubjects } = useMemo(() => {
    const raw = subjectTeacherData?.term_trend;
    if (!raw || !raw.length) {
      return { trendData: [], trendSubjects: [] };
    }

    // Collect all unique terms across all subjects
    const termSet = new Set();
    const subjectMap = {};
    raw.forEach((subj) => {
      subjectMap[subj.subject_id] = {
        key: `subject_${subj.subject_id}`,
        name: subj.subject_name,
        color: '#3b82f6',
      };
      subj.terms?.forEach((t) => termSet.add(t.term));
    });

    // Build rows: one per term, columns per subject
    const rows = [];
    Array.from(termSet).forEach((termName) => {
      const row = { term: termName };
      raw.forEach((subj) => {
        const found = subj.terms?.find((t) => t.term === termName);
        row[`subject_${subj.subject_id}`] = found?.mean != null ? parseFloat(found.mean) : null;
      });
      rows.push(row);
    });

    return {
      trendData: rows,
      trendSubjects: Object.values(subjectMap),
    };
  }, [subjectTeacherData]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-4" />
          <p className="text-gray-500">Loading subject analytics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Failed to Load Analytics</h2>
          <p className="text-gray-500 mb-4">{error.message}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <DrillDownBreadcrumb items={[]} onHomeClick={() => navigate('/analytics')} />
          <PageHeader
            title="Subject Analytics Dashboard"
            subtitle="Performance overview for the subjects and classes you teach"
            className="mt-2"
          />
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <GraduationCap className="w-5 h-5 text-gray-400" />
            <label className="text-sm font-medium text-gray-700">Academic Year</label>
            <select
              value={academicYear}
              onChange={(e) => onYearChange(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {[currentYear + 1, currentYear, currentYear - 1, currentYear - 2].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-gray-400" />
            <label className="text-sm font-medium text-gray-700">Term</label>
            <select
              value={selectedTerm}
              onChange={(e) => onTermChange(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="Term 1">Term 1</option>
              <option value="Term 2">Term 2</option>
              <option value="Term 3">Term 3</option>
            </select>
          </div>
        </div>

        {/* Subject-Classroom Cards */}
        {subjectTeacherData?.subject_classrooms?.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            {subjectTeacherData.subject_classrooms.map((sc) => (
              <div
                key={`${sc.subject_id}-${sc.classroom_id}`}
                className="bg-white rounded-lg shadow p-5 cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => navigate(`/analytics/subject-teacher/${sc.subject_id}?term=${encodeURIComponent(selectedTerm)}&year=${academicYear}`)}
              >
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-gray-900">{sc.subject_name}</h3>
                    <p className="text-sm text-gray-500">
                      {sc.classroom_name}
                      {sc.stream && <span className="ml-1 text-xs bg-gray-100 px-2 py-0.5 rounded">{sc.stream}</span>}
                    </p>
                  </div>
                  <BookOpen className="w-5 h-5 text-blue-500" />
                </div>

                <div className="flex items-end justify-between mb-3">
                  <div>
                    <p className="text-3xl font-bold text-gray-900">{sc.mean_percentage}%</p>
                    <PerformanceBandBadge level={sc.cbc_level} size="sm" showLabel={false} />
                  </div>
                  <div className="text-right text-sm text-gray-500">
                    <p>{sc.student_count} students</p>
                    <p>{sc.result_count} results</p>
                  </div>
                </div>

                {(sc.top_student || sc.bottom_student) && (
                  <div className="border-t border-gray-100 pt-3 space-y-2">
                    {sc.top_student && (
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <Award className="w-4 h-4 text-green-500" />
                          <span className="text-gray-600">Top:</span>
                          <span className="font-medium text-gray-900">{sc.top_student.name}</span>
                        </div>
                        <span className="font-semibold text-green-600">{sc.top_student.mean}%</span>
                      </div>
                    )}
                    {sc.bottom_student && (
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <AlertCircle className="w-4 h-4 text-orange-500" />
                          <span className="text-gray-600">Needs help:</span>
                          <span className="font-medium text-gray-900">{sc.bottom_student.name}</span>
                        </div>
                        <span className="font-semibold text-orange-600">{sc.bottom_student.mean}%</span>
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-3 pt-3 border-t border-gray-100">
                  <button className="w-full text-center text-sm text-blue-600 hover:text-blue-700 font-medium">
                    View Details →
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow p-12 text-center mb-6">
            <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-700 mb-2">No Subject Data</h3>
            <p className="text-gray-500">No exam results recorded for your subjects this term yet.</p>
          </div>
        )}

        {/* Charts */}
        {trendData.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <PerformanceTrendChart
              data={trendData}
              subjects={trendSubjects}
              title="Term-over-Term Performance by Subject"
              height={320}
            />
            <ClassDistributionChart
              data={subjectTeacherData.grade_distribution ?
                Object.entries(subjectTeacherData.grade_distribution.counts).map(([level, count]) => ({
                  level,
                  label: {EE: 'Exceeding', ME: 'Meeting', AE: 'Approaching', BE: 'Below'}[level],
                  count,
                  percentage: parseFloat(subjectTeacherData.grade_distribution.percentages[level]) || 0,
                  color: {EE: '#22c55e', ME: '#eab308', AE: '#f97316', BE: '#ef4444'}[level],
                })) : []
              }
              title="Overall Grade Distribution"
              height={320}
            />
          </div>
        )}

        {/* Early Warning + Spotlight */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-500" />
              At-Risk Students in Your Subjects
            </h3>
            {/* ── FIXED: unified guard for error, empty envelope, and valid data ── */}
            {hasWarningError || hasWarningEmpty ? (
              <div className="text-center py-8">
                <p className="text-gray-500">{warningFallbackMessage}</p>
              </div>
            ) : hasWarningData && warningData.students.length > 0 ? (
              <div className="space-y-3">
                {warningData.students.slice(0, 5).map((student) => (
                  <div
                    key={student.student.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div>
                      <p className="font-medium text-gray-900">{student.student.name}</p>
                      <p className="text-sm text-gray-500">
                        {student.student.classroom?.name}
                        {student.subject_risks && (
                          <span className="ml-2 text-xs text-red-500">
                            {student.subject_risks.map(r => r.subject_name).join(', ')}
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="text-right">
                      <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                        student.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                        student.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {student.risk_level}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-400">
                <p>No at-risk students in your subjects this term.</p>
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-purple-500" />
              Performance Spotlight
            </h3>
            {subjectTeacherData?.top_students?.length > 0 ? (
              <div className="space-y-4">
                <div>
                  <p className="text-sm font-medium text-gray-500 mb-2 flex items-center gap-1">
                    <TrendingUp className="w-4 h-4 text-green-500" />
                    Top Performers
                  </p>
                  <div className="space-y-2">
                    {subjectTeacherData.top_students.slice(0, 3).map((student, i) => (
                      <div key={student.id} className="flex items-center justify-between p-2 bg-green-50 rounded-lg">
                        <div className="flex items-center gap-2">
                          <span className="w-5 h-5 rounded-full bg-green-200 text-green-700 text-xs font-bold flex items-center justify-center">
                            {i + 1}
                          </span>
                          <span className="font-medium text-gray-900">{student.name}</span>
                        </div>
                        <span className="font-semibold text-green-700">{student.mean}%</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 mb-2 flex items-center gap-1">
                    <TrendingDown className="w-4 h-4 text-red-500" />
                    Needs Support
                  </p>
                  <div className="space-y-2">
                    {subjectTeacherData.bottom_students.slice(0, 3).map((student, i) => (
                      <div key={student.id} className="flex items-center justify-between p-2 bg-red-50 rounded-lg">
                        <div className="flex items-center gap-2">
                          <span className="w-5 h-5 rounded-full bg-red-200 text-red-700 text-xs font-bold flex items-center justify-center">
                            {i + 1}
                          </span>
                          <span className="font-medium text-gray-900">{student.name}</span>
                        </div>
                        <span className="font-semibold text-red-700">{student.mean}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-400">
                <p>No student performance data available.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── ADMIN / CLASS TEACHER VIEW ─────────────────────────────────────
function AdminClassTeacherView({ academicYear, selectedTerm, onYearChange, onTermChange }) {
  const navigate = useNavigate();
  const currentYear = new Date().getFullYear();

  const {
    data: summaryData,
    isLoading: summaryLoading,
    error: summaryError,
    refetch: refetchSummary,
  } = useSchoolSummary(academicYear);

  const {
    data: warningData,
    isLoading: warningLoading,
    error: warningError,
  } = useEarlyWarning(selectedTerm, academicYear);

  // ── FIXED: unified "no data" detection ───────────────────────────
  const hasWarningError = !!warningError;
  const hasWarningEmpty = warningData?.empty === true;
  const hasWarningData = warningData && !hasWarningEmpty && Array.isArray(warningData.students);

  const warningFallbackMessage = useMemo(() => {
    if (hasWarningError) {
      return warningError.message || 'Failed to load early warning data.';
    }
    if (hasWarningEmpty) {
      return warningData.suggestion || warningData.error || 'No exam results recorded for this term yet.';
    }
    return 'No data available for this term';
  }, [hasWarningError, hasWarningEmpty, warningError, warningData]);

  const trendChartData = useMemo(() => {
    if (!summaryData?.terms) return [];
    return summaryData.terms.map((t) => ({
      term: t.term,
      mean: t.mean ? parseFloat(t.mean) : null,
    }));
  }, [summaryData]);

  const gradeDistData = useMemo(() => {
    if (!summaryData?.grade_distribution) return [];
    const dist = summaryData.grade_distribution;
    const COLOR_MAP = { EE: '#22c55e', ME: '#eab308', AE: '#f97316', BE: '#ef4444' };
    const LABEL_MAP = { EE: 'Exceeding', ME: 'Meeting', AE: 'Approaching', BE: 'Below' };
    return Object.entries(dist.counts).map(([level, count]) => ({
      level,
      label: LABEL_MAP[level],
      count,
      percentage: parseFloat(dist.percentages[level]) || 0,
      color: COLOR_MAP[level],
    }));
  }, [summaryData]);

  const isTeacherView = summaryData?.is_teacher_view;

  if (summaryLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-4" />
          <p className="text-gray-500">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (summaryError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">
            {summaryError.code === 'insufficient_data' ? 'No Data Available' : 'Failed to Load Analytics'}
          </h2>
          <p className="text-gray-500 mb-4">{summaryError.message}</p>
          {summaryError.details?.suggestion && (
            <p className="text-sm text-gray-400 mb-4">{summaryError.details.suggestion}</p>
          )}
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => refetchSummary()}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (summaryData?.empty) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md w-full rounded-2xl bg-white shadow-sm border border-gray-100 p-8">
          <EmptyState
            icon={AlertTriangle}
            title={summaryData.error || 'No data available'}
            description={summaryData.suggestion || 'There are no exam results recorded for the selected period yet.'}
          />
        </div>
      </div>
    );
  }

  const handleClassClick = (classroomId) => {
    navigate(`/analytics/class/${classroomId}?term=${encodeURIComponent(selectedTerm)}&year=${academicYear}`);
  };

  const handleStudentClick = (studentId) => {
    navigate(`/analytics/student/${studentId}?term=${encodeURIComponent(selectedTerm)}&year=${academicYear}`);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <DrillDownBreadcrumb items={[]} onHomeClick={() => navigate('/analytics')} />
          <PageHeader
            title="Exam Analytics Dashboard"
            subtitle="Track school-wide performance, identify trends, and support at-risk students"
            className="mt-2"
          />
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <GraduationCap className="w-5 h-5 text-gray-400" />
            <label className="text-sm font-medium text-gray-700">Academic Year</label>
            <select
              value={academicYear}
              onChange={(e) => onYearChange(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {[currentYear + 1, currentYear, currentYear - 1, currentYear - 2].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-gray-400" />
            <label className="text-sm font-medium text-gray-700">Term</label>
            <select
              value={selectedTerm}
              onChange={(e) => onTermChange(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="Term 1">Term 1</option>
              <option value="Term 2">Term 2</option>
              <option value="Term 3">Term 3</option>
            </select>
          </div>
        </div>

        {/* Summary Cards */}
        {summaryData && (
          <>
            {!isTeacherView && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <div className="bg-white rounded-lg shadow p-5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-500">School Mean</span>
                    <BarChart3 className="w-5 h-5 text-blue-500" />
                  </div>
                  <div className="text-2xl font-bold text-gray-900">{summaryData.mean_percentage}%</div>
                  <div className="mt-1">
                    <PerformanceBandBadge
                      level={summaryData.mean_percentage >= 75 ? 'EE' : summaryData.mean_percentage >= 50 ? 'ME' : summaryData.mean_percentage >= 30 ? 'AE' : 'BE'}
                      size="sm"
                      showLabel={false}
                    />
                  </div>
                </div>
                <div className="bg-white rounded-lg shadow p-5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-500">Students Assessed</span>
                    <Users className="w-5 h-5 text-green-500" />
                  </div>
                  <div className="text-2xl font-bold text-gray-900">{summaryData.total_students}</div>
                  <p className="text-xs text-gray-400 mt-1">across {summaryData.total_exams} exams</p>
                </div>
                <div className="bg-white rounded-lg shadow p-5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-500">Total Results</span>
                    <FileText className="w-5 h-5 text-purple-500" />
                  </div>
                  <div className="text-2xl font-bold text-gray-900">{summaryData.total_results}</div>
                  <p className="text-xs text-gray-400 mt-1">
                    {summaryData.terms?.find(t => t.term === selectedTerm)?.result_count || 0} this term
                  </p>
                </div>
                <div className="bg-white rounded-lg shadow p-5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-500">At-Risk Students</span>
                    <AlertTriangle className="w-5 h-5 text-red-500" />
                  </div>
                  <div className="text-2xl font-bold text-gray-900">
                    {hasWarningError || hasWarningEmpty ? '—' : (warningData?.at_risk_count || 0)}
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {hasWarningError || hasWarningEmpty ? 'No data available' : `of ${warningData?.total_students_evaluated || summaryData.total_students} evaluated`}
                  </p>
                </div>
              </div>
            )}

            {isTeacherView && summaryData?.classrooms?.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                {summaryData.classrooms.map(cls => (
                  <div key={cls.id} className="bg-white rounded-lg shadow p-5">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-semibold text-gray-800">
                        {cls.name}
                        {cls.stream && <span className="ml-2 text-xs bg-gray-100 px-2 py-0.5 rounded">{cls.stream}</span>}
                      </h3>
                      <Users className="w-5 h-5 text-blue-500" />
                    </div>
                    <p className="text-2xl font-bold text-gray-900">{cls.mean != null ? `${cls.mean}%` : '—'}</p>
                    <button onClick={() => handleClassClick(cls.id)} className="text-blue-600 text-sm mt-2 hover:underline flex items-center gap-1">
                      View Class <ChevronRight className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Subject-classroom cards for combo teachers */}
            {summaryData?.subject_classrooms?.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  Your Subject Assignments
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {summaryData.subject_classrooms.map(sc => (
                    <div
                      key={`${sc.subject_id}-${sc.classroom_id}`}
                      className="bg-white rounded-lg shadow p-5 cursor-pointer hover:shadow-md transition-shadow border-l-4 border-blue-500"
                      onClick={() => navigate(`/analytics/subject-teacher/${sc.subject_id}?term=${encodeURIComponent(selectedTerm)}&year=${academicYear}`)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold text-gray-800">{sc.subject_name}</h3>
                        <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded font-medium">
                          {sc.classroom_name}
                          {sc.stream && ` ${sc.stream}`}
                        </span>
                      </div>
                      <p className="text-2xl font-bold text-gray-900">
                        {sc.mean_percentage != null ? `${sc.mean_percentage}%` : '—'}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        {sc.student_count} students • {sc.result_count} results
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <PerformanceTrendChart
            data={trendChartData}
            subjects={[{ key: 'mean', name: 'School Mean', color: '#3b82f6' }]}
            title="Term-over-Term Performance"
            height={320}
          />
          <ClassDistributionChart
            data={gradeDistData}
            title="School Grade Distribution"
            height={320}
            totalStudents={summaryData?.total_students}
          />
        </div>

        {/* Early Warning + Class Rankings */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-2">
            {/* ── FIXED: unified guard for error, empty envelope, and valid data ── */}
            {hasWarningError || hasWarningEmpty ? (
              <div className="bg-white rounded-lg shadow p-6">
                <div className="text-center py-8">
                  <AlertTriangle className="w-12 h-12 text-yellow-500 mx-auto mb-3" />
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">No Early Warning Data</h3>
                  <p className="text-gray-500 text-sm mb-4">{warningFallbackMessage}</p>
                  <p className="text-xs text-gray-400">Try selecting a different term or check back after exam results are recorded.</p>
                </div>
              </div>
            ) : hasWarningData && warningData.students.length > 0 ? (
              <div className="bg-white rounded-lg shadow p-6 flex flex-col justify-between h-full">
                <EarlyWarningCard data={warningData} onStudentClick={handleStudentClick} maxDisplay={5} />
                {warningData.at_risk_count > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <button
                      onClick={() => navigate(`/analytics/early-warning?term=${encodeURIComponent(selectedTerm)}&year=${academicYear}`)}
                      className="w-full text-center py-2 px-4 bg-gray-50 text-blue-600 hover:bg-blue-50 text-sm font-medium rounded-lg border border-gray-200 transition-colors duration-150"
                    >
                      View {warningData.at_risk_count} at-risk students →
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow p-6">
                <div className="text-center py-8">
                  <AlertTriangle className="w-12 h-12 text-yellow-500 mx-auto mb-3" />
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">No At-Risk Students</h3>
                  <p className="text-gray-500 text-sm">No students are flagged as at-risk for this term.</p>
                </div>
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg shadow p-6 flex flex-col justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Class Rankings</h3>
              {summaryData?.top_performing_class && (
                <div className="mb-4">
                  <p className="text-sm text-gray-500 mb-2 flex items-center gap-1">
                    <TrendingUp className="w-4 h-4 text-green-500" /> Top Performing
                  </p>
                  <button
                    onClick={() => handleClassClick(summaryData.top_performing_class.id)}
                    className="w-full flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 transition-colors"
                  >
                    <div>
                      <p className="font-medium text-gray-900">{summaryData.top_performing_class.name}</p>
                      <p className="text-sm text-gray-600">Mean: {summaryData.top_performing_class.mean}%</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-green-600" />
                  </button>
                </div>
              )}
              {summaryData?.lowest_performing_class && (
                <div className="mb-4">
                  <p className="text-sm text-gray-500 mb-2 flex items-center gap-1">
                    <TrendingDown className="w-4 h-4 text-red-500" /> Needs Attention
                  </p>
                  <button
                    onClick={() => handleClassClick(summaryData.lowest_performing_class.id)}
                    className="w-full flex items-center justify-between p-3 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition-colors"
                  >
                    <div>
                      <p className="font-medium text-gray-900">{summaryData.lowest_performing_class.name}</p>
                      <p className="text-sm text-gray-600">Mean: {summaryData.lowest_performing_class.mean}%</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-red-600" />
                  </button>
                </div>
              )}
              {!summaryData?.top_performing_class && !summaryData?.lowest_performing_class && (
                <div className="text-center py-8 text-gray-400">
                  <Minus className="w-8 h-8 mx-auto mb-2" />
                  <p>No class ranking data available</p>
                </div>
              )}
            </div>
            <div className="mt-4 pt-4 border-t border-gray-100">
              <button
                onClick={() => navigate(`/analytics/school-performance?term=${encodeURIComponent(selectedTerm)}&year=${academicYear}`)}
                className="w-full text-center py-2 px-4 bg-gray-50 text-blue-600 hover:bg-blue-50 text-sm font-medium rounded-lg border border-gray-200 transition-colors duration-150"
              >
                View All Classes
              </button>
            </div>
          </div>
        </div>

        {/* Term Breakdown Table */}
        {summaryData?.terms && summaryData.terms.some(t => t.mean) && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Term Breakdown</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Term</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Mean %</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Exams</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Results</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {summaryData.terms.map((term) => (
                    <tr key={term.term} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-3 px-4 font-medium text-gray-900">{term.term}</td>
                      <td className="py-3 px-4">
                        {term.mean ? <span className="font-semibold">{term.mean}%</span> : <span className="text-gray-400">—</span>}
                      </td>
                      <td className="py-3 px-4 text-gray-600">{term.exam_count}</td>
                      <td className="py-3 px-4 text-gray-600">{term.result_count}</td>
                      <td className="py-3 px-4">
                        {term.mean ? (
                          <PerformanceBandBadge
                            level={parseFloat(term.mean) >= 75 ? 'EE' : parseFloat(term.mean) >= 50 ? 'ME' : parseFloat(term.mean) >= 30 ? 'AE' : 'BE'}
                            size="sm"
                            showLabel={false}
                          />
                        ) : (
                          <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">No data</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}