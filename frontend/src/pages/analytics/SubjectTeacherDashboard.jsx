import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, AlertTriangle, GraduationCap, BookOpen, Award,
  AlertCircle, Users, TrendingUp, TrendingDown,
} from 'lucide-react';
import { useSubjectTeacherSummary, useEarlyWarning } from '../../hooks/useAnalytics';
import {
  PerformanceTrendChart, ClassDistributionChart,
  DrillDownBreadcrumb, PerformanceBandBadge,
} from '../../components/analytics';
import PageHeader from '../../components/ui/PageHeader';

export default function SubjectTeacherDashboard() {
  const navigate = useNavigate();
  const currentYear = new Date().getFullYear();
  const [academicYear, setAcademicYear] = useState(currentYear);
  const [selectedTerm, setSelectedTerm] = useState('Term 2');

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

  const isWarningDataError = warningData && typeof warningData === 'object' &&
                             'code' in warningData && 'message' in warningData;
  const effectiveWarningError = warningError || (isWarningDataError ? warningData : null);

  const warningErrorMessage = useMemo(() => {
    if (!effectiveWarningError) return 'No data available for this term';
    if (effectiveWarningError.code && effectiveWarningError.message) {
      return effectiveWarningError.message;
    }
    if (effectiveWarningError.response?.data?.message) {
      return effectiveWarningError.response.data.message;
    }
    if (effectiveWarningError.response?.data?.error) {
      return effectiveWarningError.response.data.error;
    }
    return effectiveWarningError.message || 'No data available for this term';
  }, [effectiveWarningError]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-500">Loading subject analytics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center text-red-600">
          <p className="font-semibold">Failed to load analytics.</p>
          <p className="text-sm text-gray-500">{error.message}</p>
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
              onChange={(e) => setAcademicYear(Number(e.target.value))}
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
              onChange={(e) => setSelectedTerm(e.target.value)}
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
                onClick={() => navigate(`/analytics/subject/${sc.subject_id}?term=${encodeURIComponent(selectedTerm)}&year=${academicYear}`)}
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
        {subjectTeacherData?.term_trend?.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <PerformanceTrendChart
              data={subjectTeacherData.term_trend.map(t => ({
                term: t.term,
                mean: t.mean ? parseFloat(t.mean) : null,
              }))}
              subjects={subjectTeacherData.term_trend.map(t => ({
                key: `subject_${t.subject_id}`,
                name: t.subject_name,
                color: '#3b82f6',
              }))}
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
            {effectiveWarningError ? (
              <div className="text-center py-8">
                <p className="text-gray-500">{warningErrorMessage}</p>
              </div>
            ) : warningData?.students?.length > 0 ? (
              <div className="space-y-3">
                {warningData.students.slice(0, 5).map((student) => (
                  <div key={student.student.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
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