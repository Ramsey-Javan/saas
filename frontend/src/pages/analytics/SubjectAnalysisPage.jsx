import React, { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  BookOpen,
  BarChart3,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Users,
} from 'lucide-react';
import { useSubjectSchoolAnalysis, useTeacherScope } from '../../hooks/useAnalytics';
import { PerformanceBandBadge, DrillDownBreadcrumb } from '../../components/analytics';
import PageHeader from '../../components/ui/PageHeader';
import Spinner from '../../components/ui/Spinner';

function levelFromMean(mean) {
  const pct = parseFloat(mean);
  if (pct >= 75) return 'EE';
  if (pct >= 50) return 'ME';
  if (pct >= 30) return 'AE';
  return 'BE';
}

/**
 * SubjectAnalysisPage — Cross-class comparison for ONE subject.
 *
 * "How does Math compare across Grade 6 / 7 / 8?" -- ranks every
 * classroom that sat this subject this term, side by side, and calls
 * out the strongest and weakest class for it.
 */
export default function SubjectAnalysisPage() {
  const { subjectId } = useParams();
  const navigate = useNavigate();

  const currentYear = new Date().getFullYear();
  const [term, setTerm] = useState('Term 2');
  const [academicYear, setAcademicYear] = useState(currentYear);

  // --- Access Control Logic ---
  const { data: scopeData } = useTeacherScope();
  const isAdmin = scopeData?.is_admin;

  // Subject teachers: only see subjects they teach
  const allowedSubjectIds = useMemo(() => {
    if (isAdmin) return null;
    return new Set((scopeData?.subjects || []).map(s => String(s.id)));
  }, [scopeData, isAdmin]);

  // Access check
  const canView = isAdmin || allowedSubjectIds?.has(String(subjectId));

  // Access denied for subject teachers not assigned to this subject
  if (!canView) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-orange-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Access Denied</h2>
          <p className="text-gray-500 mb-4">
            You are not assigned to teach this subject.
          </p>
          <button
            onClick={() => navigate('/analytics')}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors mx-auto"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const {
    data: analysisData,
    isLoading,
    error,
  } = useSubjectSchoolAnalysis(subjectId, term, academicYear);

  const handleBack = () => {
    navigate('/analytics');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-4" />
          <p className="text-gray-500">Loading subject analysis...</p>
        </div>
      </div>
    );
  }

  // "No data yet" is a normal, expected state (not a system failure) --
  // shown as a calm empty state rather than a scary error screen.
  if (error?.suggestion || error?.details?.suggestion) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-6">
            <DrillDownBreadcrumb items={[{ label: 'Subject Analysis', icon: 'subject' }]} onHomeClick={handleBack} />
          </div>
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <BookOpen className="w-12 h-12 text-blue-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-700 mb-2">No Data Yet</h3>
            <p className="text-gray-500 max-w-md mx-auto mb-4">
              {error.suggestion || error.details?.suggestion || 'No results have been recorded for this subject and term yet.'}
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
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Failed to Load Data</h2>
          <p className="text-gray-500 mb-4">{error.message}</p>
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

  const { subject, school_mean_percentage, classrooms, best_classroom, weakest_classroom } = analysisData;
  const maxMean = Math.max(...classrooms.map((c) => parseFloat(c.mean_percentage)), 1);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <DrillDownBreadcrumb items={[{ label: subject.name, icon: 'subject' }]} onHomeClick={handleBack} />
        </div>

        <div className="flex items-start justify-between mb-6">
          <PageHeader
            title={`${subject.name} — Cross-Class Comparison`}
            subtitle="How this subject performs across every class in the school"
          />
          <button
            onClick={handleBack}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-blue-600 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-4 mb-6 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-gray-400" />
            <label className="text-sm font-medium text-gray-700">Term</label>
            <select
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="Term 1">Term 1</option>
              <option value="Term 2">Term 2</option>
              <option value="Term 3">Term 3</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-gray-400" />
            <label className="text-sm font-medium text-gray-700">Year</label>
            <select
              value={academicYear}
              onChange={(e) => setAcademicYear(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500"
            >
              {[currentYear + 1, currentYear, currentYear - 1, currentYear - 2].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
        </div>

        {/* School mean + best/worst callouts */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-500">School-wide Mean</span>
              <BarChart3 className="w-5 h-5 text-blue-500" />
            </div>
            <div className="text-2xl font-bold text-gray-900">{school_mean_percentage}%</div>
            <div className="mt-1">
              <PerformanceBandBadge level={levelFromMean(school_mean_percentage)} size="sm" showLabel={false} />
            </div>
          </div>

          {best_classroom && (
            <div className="bg-white rounded-lg shadow p-5">
              <div className="flex items-center gap-1 mb-2 text-sm text-gray-500">
                <TrendingUp className="w-4 h-4 text-green-500" />
                Strongest Class
              </div>
              <p className="font-semibold text-gray-900">{best_classroom.classroom.name}</p>
              <p className="text-sm text-gray-600">{best_classroom.mean_percentage}%</p>
            </div>
          )}

          {weakest_classroom && (
            <div className="bg-white rounded-lg shadow p-5">
              <div className="flex items-center gap-1 mb-2 text-sm text-gray-500">
                <TrendingDown className="w-4 h-4 text-red-500" />
                Needs Support
              </div>
              <p className="font-semibold text-gray-900">{weakest_classroom.classroom.name}</p>
              <p className="text-sm text-gray-600">{weakest_classroom.mean_percentage}%</p>
            </div>
          )}
        </div>

        {/* Per-classroom ranked bars */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-purple-500" />
            Every Class, Ranked
          </h3>
          <div className="space-y-3">
            {classrooms.map((c) => (
              <div key={c.classroom.id} className="flex items-center gap-4">
                <div className="w-32 flex-shrink-0 text-sm font-medium text-gray-700 truncate">
                  {c.classroom.name}
                </div>
                <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full flex items-center justify-end px-2"
                    style={{ width: `${(parseFloat(c.mean_percentage) / maxMean) * 100}%` }}
                  >
                    <span className="text-xs font-semibold text-white">{c.mean_percentage}%</span>
                  </div>
                </div>
                <div className="w-16 flex-shrink-0">
                  <PerformanceBandBadge level={levelFromMean(c.mean_percentage)} size="sm" showLabel={false} />
                </div>
                <div className="w-20 flex-shrink-0 text-xs text-gray-400 text-right">
                  {c.student_count} students
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}