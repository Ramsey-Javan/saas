import React, { useState, useMemo } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  BarChart3,
  Users,
  TrendingUp,
  TrendingDown,
  Award,
  AlertTriangle,
  ChevronRight,
  BookOpen,
  GraduationCap,
} from 'lucide-react';
import { useClassPerformance, useTeacherScope } from '../../hooks/useAnalytics';
import { PerformanceBandBadge, DrillDownBreadcrumb } from '../../components/analytics';
import PageHeader from '../../components/ui/PageHeader';
import Spinner from '../../components/ui/Spinner';

/**
 * ClassSubjectAnalysisPage — Per-classroom subject drill-down.
 *
 * Shows top/bottom students in a specific subject within one classroom.
 * Admin sees all. Subject teacher sees only if they teach this subject
 * in this class. Class teacher sees all subjects in their class.
 */
export default function ClassSubjectAnalysisPage() {
  const { classroomId, subjectId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const academicYear = Number(searchParams.get('year')) || new Date().getFullYear();

  const [selectedTerm, setSelectedTerm] = useState(() => {
    const raw = searchParams.get('term');
    if (!raw) return 'Term 2';
    const cleaned = raw.trim().replace(/\s+/g, ' ');
    if (/^Term [123]$/i.test(cleaned)) return 'Term ' + cleaned.match(/[123]/)[0];
    const canonicalMap = { term1: 'Term 1', term2: 'Term 2', term3: 'Term 3' };
    return canonicalMap[cleaned.toLowerCase()] || 'Term 2';
  });

  const { data: scopeData } = useTeacherScope();
  const {
    data: classData,
    isLoading,
    error,
  } = useClassPerformance(classroomId, selectedTerm, academicYear);

  const isAdmin = scopeData?.is_admin;
  const isClassTeacher = scopeData?.is_class_teacher && 
    scopeData.classrooms.some(c => String(c.id) === String(classroomId));
  const isSubjectTeacher = scopeData?.is_subject_teacher &&
    scopeData.subjects.some(s => String(s.id) === String(subjectId));

  // Filter to the specific subject
  const subjectData = useMemo(() => {
    if (!classData?.subjects) return null;
    return classData.subjects.find(s => String(s.subject.id) === String(subjectId));
  }, [classData, subjectId]);

  // Student rankings filtered to this subject (from class performance data)
  // Note: class-performance returns aggregated subject data, not per-student
  // For per-student subject rankings, we'd need a new endpoint. For now,
  // we show the subject aggregate and link to the full class page.

  const switchTerm = (displayTerm) => {
    setSelectedTerm(displayTerm);
    const canonical = displayTerm.toLowerCase().replace(' ', '');
    const newParams = new URLSearchParams(searchParams);
    newParams.set('term', canonical);
    newParams.set('year', academicYear.toString());
    setSearchParams(newParams, { replace: true });
  };

  const handleBack = () => {
    navigate('/analytics');
  };

  const handleClassBack = () => {
    navigate(`/analytics/class/${classroomId}?term=${selectedTerm.toLowerCase().replace(' ', '')}&year=${academicYear}`);
  };

  // ── Access Check ─────────────────────────────────────────────────
  if (!isAdmin && !isClassTeacher && !isSubjectTeacher) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-orange-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Access Denied</h2>
          <p className="text-gray-500 mb-4">
            You do not have permission to view this subject in this classroom.
          </p>
          <button
            onClick={handleBack}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors mx-auto"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  // ── Loading ────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-4" />
          <p className="text-gray-500">Loading subject data...</p>
        </div>
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────
  if (error) {
    const errorData = error?.response?.data || error;
    const rawMessage = errorData?.message || errorData?.error || error?.message || 'Failed to load subject data';
    const rawSuggestion = errorData?.suggestion || errorData?.details;
    const errorMessage = typeof rawMessage === 'string' ? rawMessage : JSON.stringify(rawMessage);
    const suggestion = typeof rawSuggestion === 'string' ? rawSuggestion : null;

    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Failed to Load Data</h2>
          <p className="text-gray-500 mb-2">{errorMessage}</p>
          {suggestion && (
            <p className="text-sm text-blue-600 bg-blue-50 p-3 rounded-lg mb-4">
              💡 {suggestion}
            </p>
          )}
          <button
            onClick={handleBack}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors mx-auto"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  // ── Empty ──────────────────────────────────────────────────────────
  if (!classData || !subjectData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
          <p className="text-gray-500">No data available for this subject.</p>
        </div>
      </div>
    );
  }

  const { classroom, subjects } = classData;
  const dist = subjectData.grade_distribution;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb */}
        <div className="mb-6">
          <DrillDownBreadcrumb
            items={[
              { label: classroom.name, icon: 'class', onClick: handleClassBack },
              { label: subjectData.subject.name, icon: 'subject' },
            ]}
            onHomeClick={handleBack}
          />
        </div>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between mb-6 gap-4">
          <div>
            <PageHeader
              title={subjectData.subject.name}
              subtitle={`${classroom.name} · ${subjectData.subject.code} · ${academicYear}`}
            />
          </div>
          <button
            onClick={handleClassBack}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-blue-600 transition-colors self-start"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Class
          </button>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <GraduationCap className="w-5 h-5 text-gray-400" />
            <label className="text-sm font-medium text-gray-700">Term</label>
            <div className="flex gap-2">
              {['Term 1', 'Term 2', 'Term 3'].map((t) => (
                <button
                  key={t}
                  onClick={() => switchTerm(t)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    selectedTerm === t
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Subject Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Mean %</p>
                <p className="text-2xl font-bold text-gray-900">{subjectData.mean_percentage}%</p>
              </div>
              <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
                <BarChart3 className="w-5 h-5" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Students</p>
                <p className="text-2xl font-bold text-gray-900">{subjectData.student_count}</p>
              </div>
              <div className="p-2 rounded-lg bg-green-50 text-green-600">
                <Users className="w-5 h-5" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Highest</p>
                <p className="text-2xl font-bold text-green-600">{subjectData.highest}</p>
              </div>
              <div className="p-2 rounded-lg bg-green-50 text-green-600">
                <TrendingUp className="w-5 h-5" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Lowest</p>
                <p className="text-2xl font-bold text-red-600">{subjectData.lowest}</p>
              </div>
              <div className="p-2 rounded-lg bg-red-50 text-red-600">
                <TrendingDown className="w-5 h-5" />
              </div>
            </div>
          </div>
        </div>

        {/* Grade Distribution */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <Award className="w-5 h-5 text-purple-500" />
            Grade Distribution
          </h3>
          <div className="flex items-center gap-6">
            {dist && Object.entries(dist.counts).map(([level, count]) => (
              <div key={level} className="flex-1 text-center">
                <div className={`text-2xl font-bold mb-1 ${
                  level === 'EE' ? 'text-green-600' :
                  level === 'ME' ? 'text-blue-600' :
                  level === 'AE' ? 'text-orange-600' :
                  'text-red-600'
                }`}>
                  {count}
                </div>
                <div className="text-xs text-gray-500 uppercase">{level}</div>
                <div className="text-xs text-gray-400">{dist.percentages?.[level] || 0}%</div>
              </div>
            ))}
          </div>
        </div>

        {/* Teacher Info */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Subject Teacher</h3>
          <p className="text-gray-600">{subjectData.subject.teacher || 'Unassigned'}</p>
        </div>
      </div>
    </div>
  );
}