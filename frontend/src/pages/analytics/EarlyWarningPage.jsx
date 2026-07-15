import React, { useState, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  AlertTriangle,
  TrendingDown,
  BookX,
  CalendarX,
  ChevronRight,
  Filter,
  GraduationCap,
  Users,
} from 'lucide-react';
import { useEarlyWarning } from '../../hooks/useAnalytics';
import { PerformanceBandBadge, DrillDownBreadcrumb } from '../../components/analytics';
import PageHeader from '../../components/ui/PageHeader';
import Spinner from '../../components/ui/Spinner';
import { useAuthStore } from '../../store/authStore';

const RISK_ICON_MAP = {
  declining: TrendingDown,
  slight_decline: TrendingDown,
  multiple_be: BookX,
  overall_be: AlertTriangle,
  missing_results: CalendarX,
};

const RISK_LEVEL_STYLES = {
  high: {
    border: 'border-red-300',
    bg: 'bg-red-50',
    badge: 'bg-red-100 text-red-800',
    icon: 'text-red-500',
    dot: 'bg-red-500',
  },
  medium: {
    border: 'border-orange-300',
    bg: 'bg-orange-50',
    badge: 'bg-orange-100 text-orange-800',
    icon: 'text-orange-500',
    dot: 'bg-orange-500',
  },
  low: {
    border: 'border-yellow-300',
    bg: 'bg-yellow-50',
    badge: 'bg-yellow-100 text-yellow-800',
    icon: 'text-yellow-500',
    dot: 'bg-yellow-500',
  },
};

/**
 * EarlyWarningPage — Full-page at-risk student listing.
 *
 * Admins see all at-risk students school-wide.
 * Teachers see only their own classroom's at-risk students.
 */
export default function EarlyWarningPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuthStore();
  const currentYear = new Date().getFullYear();

  const [riskFilter, setRiskFilter] = useState('all');

  const academicYear = Number(searchParams.get('year')) || currentYear;

  const [selectedTerm, setSelectedTerm] = useState(() => {
    const raw = searchParams.get('term');
    if (!raw) return 'Term 2';
    const cleaned = raw.trim().replace(/\s+/g, ' ');
    if (/^Term [123]$/i.test(cleaned)) return 'Term ' + cleaned.match(/[123]/)[0];
    const canonicalMap = { term1: 'Term 1', term2: 'Term 2', term3: 'Term 3' };
    return canonicalMap[cleaned.toLowerCase()] || 'Term 2';
  });

  const {
    data,
    isLoading,
    error,
  } = useEarlyWarning(selectedTerm, academicYear);

  // Teachers only see their own classroom slice
  const visibleStudents = useMemo(() => {
    if (!data?.students) return [];
    if (user?.role === 'teacher' && user?.assigned_classrooms?.length > 0) {
      const allowedIds = new Set(user.assigned_classrooms.map(c => c.id));
      return data.students.filter(s => allowedIds.has(s.student?.classroom?.id));
    }
    return data.students;
  }, [data, user]);

  const filteredStudents = useMemo(() => {
    if (riskFilter === 'all') return visibleStudents;
    return visibleStudents.filter(s => s.risk_level === riskFilter);
  }, [visibleStudents, riskFilter]);

  const riskCounts = useMemo(() => {
    const counts = { high: 0, medium: 0, low: 0 };
    visibleStudents.forEach(s => { counts[s.risk_level] = (counts[s.risk_level] || 0) + 1; });
    return counts;
  }, [visibleStudents]);

  const switchTerm = (displayTerm) => {
    setSelectedTerm(displayTerm);
    const canonical = displayTerm.toLowerCase().replace(' ', '');
    const newParams = new URLSearchParams(searchParams);
    newParams.set('term', canonical);
    newParams.set('year', academicYear.toString());
    setSearchParams(newParams, { replace: true });
  };

  const handleStudentClick = (studentId) => {
    const canonical = selectedTerm.toLowerCase().replace(' ', '');
    navigate(`/analytics/student/${studentId}?term=${canonical}&year=${academicYear}`);
  };

  const handleBack = () => {
    navigate('/analytics');
  };

  // ── Loading ────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-4" />
          <p className="text-gray-500">Loading early warning data...</p>
        </div>
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────
  if (error) {
    const errorData = error?.response?.data || error;
    const rawMessage = errorData?.message || errorData?.error || error?.message || 'Failed to load early warning data';
    const rawSuggestion = errorData?.suggestion || errorData?.details;
    const errorMessage = typeof rawMessage === 'string' ? rawMessage : JSON.stringify(rawMessage);
    const suggestion = typeof rawSuggestion === 'string' ? rawSuggestion : null;

    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Failed to Load Early Warning Data</h2>
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
  if (!data || !Array.isArray(data.students)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
          <p className="text-gray-500">No early warning data available.</p>
        </div>
      </div>
    );
  }

  const hasAnyAtRisk = filteredStudents.length > 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb */}
        <div className="mb-6">
          <DrillDownBreadcrumb
            items={[{ label: 'Early Warning', icon: 'school' }]}
            onHomeClick={handleBack}
          />
        </div>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between mb-6 gap-4">
          <div>
            <PageHeader
              title="Early Warning System"
              subtitle={`${academicYear} · ${visibleStudents.length} at-risk students${user?.role === 'teacher' ? ' in your classroom' : ' school-wide'}`}
            />
          </div>
          <button
            onClick={handleBack}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-blue-600 transition-colors self-start"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
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

          <div className="h-6 w-px bg-gray-200 hidden sm:block" />

          <div className="flex items-center gap-2">
            <Filter className="w-5 h-5 text-gray-400" />
            <label className="text-sm font-medium text-gray-700">Risk Level</label>
            <div className="flex bg-gray-100 rounded-lg p-0.5">
              {[
                { key: 'all', label: 'All', count: visibleStudents.length },
                { key: 'high', label: 'High', count: riskCounts.high },
                { key: 'medium', label: 'Medium', count: riskCounts.medium },
                { key: 'low', label: 'Low', count: riskCounts.low },
              ].map((f) => (
                <button
                  key={f.key}
                  onClick={() => setRiskFilter(f.key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    riskFilter === f.key
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {f.key !== 'all' && (
                    <span className={`w-2 h-2 rounded-full ${RISK_LEVEL_STYLES[f.key]?.dot || 'bg-gray-400'}`} />
                  )}
                  {f.label}
                  <span className="text-xs text-gray-400">({f.count})</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Total At Risk</p>
                <p className="text-2xl font-bold text-gray-900">{visibleStudents.length}</p>
              </div>
              <div className="p-2 rounded-lg bg-red-50 text-red-600">
                <AlertTriangle className="w-5 h-5" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">High Risk</p>
                <p className="text-2xl font-bold text-red-600">{riskCounts.high}</p>
              </div>
              <div className="p-2 rounded-lg bg-red-50 text-red-600">
                <TrendingDown className="w-5 h-5" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Medium Risk</p>
                <p className="text-2xl font-bold text-orange-600">{riskCounts.medium}</p>
              </div>
              <div className="p-2 rounded-lg bg-orange-50 text-orange-600">
                <AlertTriangle className="w-5 h-5" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Low Risk</p>
                <p className="text-2xl font-bold text-yellow-600">{riskCounts.low}</p>
              </div>
              <div className="p-2 rounded-lg bg-yellow-50 text-yellow-600">
                <Users className="w-5 h-5" />
              </div>
            </div>
          </div>
        </div>

        {/* No Data Banner */}
        {!hasAnyAtRisk && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-green-500 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-green-800">No at-risk students detected</p>
              <p className="text-xs text-green-600">
                All students are performing at acceptable levels for {selectedTerm}.
              </p>
            </div>
          </div>
        )}

        {/* Student List */}
        {hasAnyAtRisk && (
          <div className="space-y-3">
            {filteredStudents.map((studentData) => {
              const { student, risk_level, risk_factors, current_term_mean, previous_term_mean, recommended_action } = studentData;
              const styles = RISK_LEVEL_STYLES[risk_level];

              return (
                <div
                  key={student.id}
                  onClick={() => handleStudentClick(student.id)}
                  className={`bg-white border rounded-lg p-5 cursor-pointer hover:shadow-md transition-shadow ${styles.border}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-semibold text-gray-900 text-lg">{student.name}</h4>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium uppercase ${styles.badge}`}>
                          {risk_level}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 mb-3">
                        {student.admission_number} · {student.classroom?.name || '—'}
                      </p>

                      <div className="flex flex-wrap gap-2 mb-3">
                        {risk_factors.map((factor, idx) => {
                          const FactorIcon = RISK_ICON_MAP[factor.type] || AlertTriangle;
                          return (
                            <span
                              key={idx}
                              className="inline-flex items-center gap-1 text-xs bg-gray-100 px-2 py-1 rounded-md"
                            >
                              <FactorIcon className={`w-3 h-3 ${styles.icon}`} />
                              {factor.message}
                            </span>
                          );
                        })}
                      </div>

                      <div className="flex items-center gap-6 text-sm mb-2">
                        <span className="text-gray-600">
                          Current Mean:{' '}
                          <strong className={current_term_mean < 50 ? 'text-red-600' : 'text-gray-900'}>
                            {current_term_mean}%
                          </strong>
                        </span>
                        {previous_term_mean && (
                          <span className="text-gray-500">
                            Previous: {previous_term_mean}%
                          </span>
                        )}
                        <PerformanceBandBadge
                          level={studentData.cbc_level || (current_term_mean >= 75 ? 'EE' : current_term_mean >= 50 ? 'ME' : current_term_mean >= 30 ? 'AE' : 'BE')}
                          size="sm"
                          showLabel={false}
                        />
                      </div>

                      {studentData.subjects_at_risk?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-2">
                          {studentData.subjects_at_risk.map((subj) => (
                            <span key={subj} className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">
                              {subj}
                            </span>
                          ))}
                        </div>
                      )}

                      <p className="text-xs text-gray-500 italic">
                        💡 {recommended_action}
                      </p>
                    </div>

                    <ChevronRight className="w-5 h-5 text-gray-300 flex-shrink-0 mt-2" />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}