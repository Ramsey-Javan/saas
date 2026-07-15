import React, { useState, useMemo } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  Award,
  Users,
  Calendar,
  BookOpen,
  ChevronDown,
  ChevronRight,
  FileText,
} from 'lucide-react';
import {
  useStudentPerformance,
  useStudentLongitudinal,
  useCohortReference,
} from '../../hooks/useAnalytics';
import {
  PerformanceTrendChart,
  PerformanceBandBadge,
  DrillDownBreadcrumb,
} from '../../components/analytics';
import PageHeader from '../../components/ui/PageHeader';
import Spinner from '../../components/ui/Spinner';

/**
 * StudentProfilePage — Individual student analytics deep dive.
 *
 * Features:
 * - Student header with photo, name, admission number
 * - Term-over-term line chart (all subjects)
 * - Current term subject breakdown (bar chart)
 * - Class rank + percentile
 * - Cohort reference line on all charts
 * - Performance trend indicator (improving/declining/stable)
 * - Expandable exam breakdown per subject (handles multiple exams per term)
 */
export default function StudentProfilePage() {
  const { studentId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const academicYear = Number(searchParams.get('year')) || new Date().getFullYear();
  
  // ── FIX: robust term normalisation ------------------------------------
  const [selectedTerm, setSelectedTerm] = useState(() => {
    const raw = searchParams.get('term');
    if (!raw) return 'Term 1';

    const cleaned = raw.trim().replace(/\s+/g, ' ');

    if (/^Term [123]$/i.test(cleaned)) {
      return 'Term ' + cleaned.match(/[123]/)[0];
    }

    const canonicalMap = { term1: 'Term 1', term2: 'Term 2', term3: 'Term 3' };
    return canonicalMap[cleaned.toLowerCase()] || 'Term 1';
  });

  const [expandedSubjects, setExpandedSubjects] = useState(new Set());

  const {
    data: performanceData,
    isLoading: perfLoading,
    error: perfError,
  } = useStudentPerformance(studentId, selectedTerm, academicYear);

  const {
    data: longitudinalData,
    isLoading: longLoading,
    error: longError,
  } = useStudentLongitudinal(studentId, academicYear);

  // Cohort reference for first subject (if available)
  const firstSubjectId = performanceData?.subjects?.[0]?.subject?.id;
  const classroomId = performanceData?.classroom?.id;

  const {
    data: cohortData,
  } = useCohortReference(
    classroomId,
    firstSubjectId,
    selectedTerm,
    academicYear,
    { enabled: !!classroomId && !!firstSubjectId }
  );

  // Terms that actually have data
  const availableTerms = useMemo(() => {
    if (!longitudinalData?.terms) return [];
    return longitudinalData.terms
      .filter((t) => t.has_data)
      .map((t) => t.term);
  }, [longitudinalData]);

  const switchToTerm = (canonicalTerm) => {
    const displayMap = { term1: 'Term 1', term2: 'Term 2', term3: 'Term 3' };
    const displayTerm = displayMap[canonicalTerm] || canonicalTerm;
    setSelectedTerm(displayTerm);
    const newParams = new URLSearchParams(searchParams);
    newParams.set('term', canonicalTerm);
    navigate(`?${newParams.toString()}`, { replace: true });
  };

  const toggleSubject = (subjectId) => {
    setExpandedSubjects((prev) => {
      const next = new Set(prev);
      if (next.has(subjectId)) {
        next.delete(subjectId);
      } else {
        next.add(subjectId);
      }
      return next;
    });
  };

  // Transform longitudinal data for trend chart
  const trendChartData = useMemo(() => {
    if (!longitudinalData?.terms) return [];
    return longitudinalData.terms
      .filter((t) => t.has_data)
      .map((termData) => {
        const point = { term: termData.term };
        termData.subjects.forEach((subj) => {
          point[subj.subject.name] = parseFloat(subj.percentage);
        });
        return point;
      });
  }, [longitudinalData]);

  // Subject list for chart legend
  const chartSubjects = useMemo(() => {
    if (!longitudinalData?.terms) return [];
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4'];
    const seen = new Set();
    const subjects = [];
    longitudinalData.terms.forEach((term) => {
      term.subjects?.forEach((subj) => {
        if (!seen.has(subj.subject.name)) {
          seen.add(subj.subject.name);
          subjects.push({
            key: subj.subject.name,
            name: subj.subject.name,
            color: colors[subjects.length % colors.length],
          });
        }
      });
    });
    return subjects;
  }, [longitudinalData]);

  const handleBack = () => {
    navigate('/analytics');
  };

  const handleClassClick = () => {
    if (performanceData?.classroom?.id) {
      navigate(`/analytics/class/${performanceData.classroom.id}?term=${encodeURIComponent(selectedTerm)}&year=${academicYear}`);
    }
  };

  // Loading state
  if (perfLoading || longLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-4" />
          <p className="text-gray-500">Loading student profile...</p>
        </div>
      </div>
    );
  }

  // Error extraction
  let errorMessage = 'Failed to load student data';
  let suggestion = null;
  let fieldErrors = [];

  if (perfError) {
    const data = perfError.response?.data;
    if (data) {
      if (data.error) {
        errorMessage = data.error;
        suggestion = data.suggestion;
      } else {
        fieldErrors = Object.entries(data)
          .filter(([k]) => k !== 'error' && k !== 'suggestion')
          .flatMap(([_, msgs]) => (Array.isArray(msgs) ? msgs : [msgs]));
        if (fieldErrors.length) {
          errorMessage = fieldErrors.join(' ');
        }
      }
    } else if (perfError.message) {
      errorMessage = perfError.message;
    }
  }

  // Error state
  if (perfError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Failed to Load Student Data</h2>
          <p className="text-gray-500 mb-2">{errorMessage}</p>
          {suggestion && (
            <p className="text-sm text-blue-600 bg-blue-50 p-3 rounded-lg mb-4">
              💡 {suggestion}
            </p>
          )}
          <div className="flex gap-2 justify-center">
            {availableTerms.length > 0 ? (
              availableTerms.map((t) => {
                const labelMap = { term1: 'Term 1', term2: 'Term 2', term3: 'Term 3' };
                return (
                  <button
                    key={t}
                    onClick={() => switchToTerm(t)}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Try {labelMap[t] || t}
                  </button>
                );
              })
            ) : (
              <button
                onClick={() => switchToTerm('term1')}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Try Term 1
              </button>
            )}
            <button
              onClick={handleBack}
              className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!performanceData || !longitudinalData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
          <p className="text-gray-500">No data available for this student.</p>
        </div>
      </div>
    );
  }

  const { student, classroom, overall_mean, class_rank, class_size, percentile, subjects } = performanceData;
  const { trend, velocity } = longitudinalData;

  const trendIcon = trend === 'improving'
    ? <TrendingUp className="w-5 h-5 text-green-500" />
    : trend === 'declining'
    ? <TrendingDown className="w-5 h-5 text-red-500" />
    : <Minus className="w-5 h-5 text-yellow-500" />;

  const trendLabel = trend === 'improving'
    ? 'Improving'
    : trend === 'declining'
    ? 'Declining'
    : trend === 'mixed'
    ? 'Mixed'
    : 'Stable';

  const trendColor = trend === 'improving'
    ? 'text-green-600 bg-green-50'
    : trend === 'declining'
    ? 'text-red-600 bg-red-50'
    : 'text-yellow-600 bg-yellow-50';

  const hasSubjects = subjects && subjects.length > 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb */}
        <div className="mb-6">
          <DrillDownBreadcrumb
            items={[
              ...(classroom
                ? [{ label: classroom.name, icon: 'class', onClick: handleClassClick }]
                : []),
              { label: student.name, icon: 'student' },
            ]}
            onHomeClick={handleBack}
          />
        </div>

        {/* Header with Student Info */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center text-2xl font-bold text-blue-600">
                {student.name?.charAt(0)?.toUpperCase() || '?'}
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{student.name}</h1>
                <p className="text-gray-500">{student.admission_number || 'No admission number'}</p>
                {classroom && (
                  <button
                    onClick={handleClassClick}
                    className="text-sm text-blue-600 hover:text-blue-800 mt-1 flex items-center gap-1"
                  >
                    <Users className="w-4 h-4" />
                    {classroom.name}
                  </button>
                )}
              </div>
            </div>
            <button
              onClick={handleBack}
              className="flex items-center gap-2 text-sm text-gray-500 hover:text-blue-600 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-100">
            <div className="text-center">
              <p className="text-sm text-gray-500 mb-1">Overall Mean</p>
              <p className="text-2xl font-bold text-gray-900">
                {overall_mean != null ? `${overall_mean}%` : '—'}
              </p>
              <div className="mt-1">
                {overall_mean != null && (
                  <PerformanceBandBadge
                    level={parseFloat(overall_mean) >= 75 ? 'EE' : parseFloat(overall_mean) >= 50 ? 'ME' : parseFloat(overall_mean) >= 30 ? 'AE' : 'BE'}
                    size="sm"
                    showLabel={false}
                  />
                )}
              </div>
            </div>
            <div className="text-center">
              <p className="text-sm text-gray-500 mb-1">Class Rank</p>
              <p className="text-2xl font-bold text-gray-900">
                {class_rank != null ? class_rank : '—'}
                <span className="text-sm font-normal text-gray-400"> / {class_size || '—'}</span>
              </p>
            </div>
            <div className="text-center">
              <p className="text-sm text-gray-500 mb-1">Percentile</p>
              <p className="text-2xl font-bold text-gray-900">
                {percentile != null ? `${percentile}%` : '—'}
              </p>
            </div>
            <div className="text-center">
              <p className="text-sm text-gray-500 mb-1">Year Trend</p>
              <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${trendColor}`}>
                {trendIcon}
                {trendLabel}
                {velocity !== 0 && velocity != null && (
                  <span className="text-xs opacity-75">
                    ({velocity > 0 ? '+' : ''}{velocity}/term)
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Term Selector */}
        <div className="bg-white rounded-lg shadow p-4 mb-6 flex items-center gap-4">
          <Calendar className="w-5 h-5 text-gray-400" />
          <label className="text-sm font-medium text-gray-700">View Term</label>
          <div className="flex gap-2">
            {['Term 1', 'Term 2', 'Term 3'].map((t) => (
              <button
                key={t}
                onClick={() => {
                  setSelectedTerm(t);
                  const newParams = new URLSearchParams(searchParams);
                  newParams.set('term', t.toLowerCase().replace(' ', ''));
                  navigate(`?${newParams.toString()}`, { replace: true });
                }}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
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

        {/* Longitudinal Trend Chart */}
        <div className="mb-6">
          <PerformanceTrendChart
            data={trendChartData}
            subjects={chartSubjects}
            cohortAverage={cohortData?.class_average ? parseFloat(cohortData.class_average) : null}
            title="Term-over-Term Trajectory"
            height={360}
          />
        </div>

        {/* Current Term Subject Breakdown */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-500" />
            {selectedTerm} Subject Breakdown
          </h3>

          {hasSubjects ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="text-left py-3 px-4 font-medium text-gray-600 w-8"></th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Subject</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Term Avg</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Level</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Class Avg</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Rank</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Gap</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Exams</th>
                  </tr>
                </thead>
                <tbody>
                  {subjects.map((subject) => {
                    const isExpanded = expandedSubjects.has(subject.subject.id);
                    const gap = parseFloat(subject.term_mean_percentage) - parseFloat(subject.class_average || 0);
                    const examCount = subject.exams?.length || 0;

                    return (
                      <React.Fragment key={subject.subject.id}>
                        {/* Main subject row */}
                        <tr
                          className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
                          onClick={() => toggleSubject(subject.subject.id)}
                        >
                          <td className="py-3 px-4">
                            {isExpanded ? (
                              <ChevronDown className="w-4 h-4 text-gray-400" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-gray-400" />
                            )}
                          </td>
                          <td className="py-3 px-4">
                            <div>
                              <p className="font-medium text-gray-900">{subject.subject.name}</p>
                              <p className="text-xs text-gray-400">{subject.subject.code}</p>
                            </div>
                          </td>
                          <td className="py-3 px-4 text-center font-semibold text-gray-900">
                            {subject.term_mean_percentage}%
                          </td>
                          <td className="py-3 px-4 text-center">
                            <PerformanceBandBadge level={subject.cbc_level} size="sm" showLabel={false} />
                          </td>
                          <td className="py-3 px-4 text-center text-gray-600">
                            {subject.class_average != null ? `${subject.class_average}%` : '—'}
                          </td>
                          <td className="py-3 px-4 text-center">
                            {subject.rank_in_subject ? (
                              <span className="inline-flex items-center gap-1">
                                <Award className="w-4 h-4 text-purple-500" />
                                #{subject.rank_in_subject}
                              </span>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span className={`font-medium ${gap >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {gap >= 0 ? '+' : ''}{gap.toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span className="inline-flex items-center gap-1 text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                              <FileText className="w-3 h-3" />
                              {examCount}
                            </span>
                          </td>
                        </tr>

                        {/* Expanded exam breakdown */}
                        {isExpanded && subject.exams && subject.exams.length > 0 && (
                          <tr className="bg-gray-50/50">
                            <td colSpan={8} className="py-3 px-4">
                              <div className="ml-8">
                                <p className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">
                                  Individual Exams
                                </p>
                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                                  {subject.exams.map((exam, idx) => (
                                    <div
                                      key={`${subject.subject.id}-${exam.exam_id}-${idx}`}
                                      className="bg-white border border-gray-200 rounded-lg p-3"
                                    >
                                      <div className="flex items-center justify-between mb-1">
                                        <span className="text-sm font-medium text-gray-800">
                                          {exam.exam_name}
                                        </span>
                                        <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                                          {exam.exam_type}
                                        </span>
                                      </div>
                                      <div className="flex items-center gap-3 text-sm">
                                        <span className="font-semibold text-gray-900">
                                          {exam.percentage}%
                                        </span>
                                        <span className="text-gray-400">
                                          {exam.marks}/{exam.total_marks}
                                        </span>
                                        <PerformanceBandBadge
                                          level={exam.cbc_level}
                                          size="sm"
                                          showLabel={false}
                                        />
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-10">
              <BookOpen className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 mb-1">No exam data recorded for {selectedTerm}.</p>
              <p className="text-sm text-gray-400 mb-4">This student has no grades entered for this term yet.</p>
              {availableTerms.length > 0 && (
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <span className="text-sm text-gray-600 mr-1">View a term with data:</span>
                  {availableTerms.map((t) => {
                    const labelMap = { term1: 'Term 1', term2: 'Term 2', term3: 'Term 3' };
                    return (
                      <button
                        key={t}
                        onClick={() => switchToTerm(t)}
                        className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-full text-sm font-medium hover:bg-blue-100 transition-colors"
                      >
                        {labelMap[t] || t}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Term-by-Term Summary Cards */}
        {longitudinalData.terms && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {longitudinalData.terms.map((termData) => (
              <div
                key={termData.term}
                className={`bg-white rounded-lg shadow p-5 ${
                  termData.term === selectedTerm.toLowerCase().replace(' ', '') ? 'ring-2 ring-blue-500' : ''
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-semibold text-gray-800">
                    {termData.term.replace('term', 'Term ').replace(/(^\w)(\d)/, '$1 $2')}
                  </h4>
                  {termData.has_data ? (
                    <PerformanceBandBadge
                      level={termData.overall_cbc_level}
                      size="sm"
                      showLabel={false}
                    />
                  ) : (
                    <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">No data</span>
                  )}
                </div>
                {termData.has_data ? (
                  <>
                    <p className="text-2xl font-bold text-gray-900 mb-1">
                      {termData.mean_percentage}%
                    </p>
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <Award className="w-4 h-4" />
                      Rank #{termData.class_rank} of {termData.class_size}
                    </div>
                    <div className="mt-3 space-y-1">
                      {termData.subjects.slice(0, 3).map((subj) => (
                        <div key={subj.subject.id} className="flex items-center justify-between text-sm">
                          <span className="text-gray-600">{subj.subject.name}</span>
                          <span className="font-medium">{subj.percentage}%</span>
                        </div>
                      ))}
                      {termData.subjects.length > 3 && (
                        <p className="text-xs text-gray-400">+{termData.subjects.length - 3} more subjects</p>
                      )}
                    </div>
                  </>
                ) : (
                  <p className="text-gray-400 text-sm">No exam data recorded</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}