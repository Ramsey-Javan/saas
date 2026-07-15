import React, { useState, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  School,
  Users,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronRight,
  ChevronDown,
  LayoutGrid,
  List,
  Calendar,
  Award,
  AlertTriangle,
  FileText,
} from 'lucide-react';
import { useSchoolClassrooms } from '../../hooks/useAnalytics';
import { PerformanceBandBadge, DrillDownBreadcrumb } from '../../components/analytics';
import PageHeader from '../../components/ui/PageHeader';
import Spinner from '../../components/ui/Spinner';

/**
 * SchoolPerformancePage — School-wide classroom performance overview.
 *
 * Features:
 * - All classrooms ranked by performance (mean %)
 * - Group by grade_level with stream breakdown
 * - Toggle between "Group by Grade" and "All Streams" views
 * - Summary stats (total classes, students, school mean)
 * - Click any classroom to drill into ClassPerformancePage
 * - Handles classrooms without exam data (shows "No data" badge)
 */
export default function SchoolPerformancePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const academicYear = Number(searchParams.get('year')) || new Date().getFullYear();

  // Robust term normalisation from URL
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

  const [viewMode, setViewMode] = useState('grade'); // 'grade' | 'list'
  const [expandedGrades, setExpandedGrades] = useState(new Set());

  const {
    data,
    isLoading,
    error,
  } = useSchoolClassrooms(selectedTerm, academicYear);

  // Auto-expand grades that have data
  useMemo(() => {
    if (data?.grade_levels) {
      const withData = new Set(
        data.grade_levels
          .filter(g => g.aggregate.with_data_count > 0)
          .map(g => g.grade_level)
      );
      setExpandedGrades(withData);
    }
  }, [data]);

  const toggleGrade = (gradeLevel) => {
    setExpandedGrades((prev) => {
      const next = new Set(prev);
      if (next.has(gradeLevel)) {
        next.delete(gradeLevel);
      } else {
        next.add(gradeLevel);
      }
      return next;
    });
  };

  const switchTerm = (displayTerm) => {
    setSelectedTerm(displayTerm);
    const canonical = displayTerm.toLowerCase().replace(' ', '');
    const newParams = new URLSearchParams(searchParams);
    newParams.set('term', canonical);
    newParams.set('year', academicYear.toString());
    setSearchParams(newParams, { replace: true });
  };

  const handleClassClick = (classroomId) => {
    const canonical = selectedTerm.toLowerCase().replace(' ', '');
    navigate(`/analytics/class/${classroomId}?term=${canonical}&year=${academicYear}`);
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
          <p className="text-gray-500">Loading school performance...</p>
        </div>
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────
  if (error) {
    const errorData = error?.response?.data || error;
    const rawMessage = errorData?.message || errorData?.error || error?.message || 'Failed to load school data';
    const rawSuggestion = errorData?.suggestion || errorData?.details;

    // Never render an object as a React child
    const errorMessage = typeof rawMessage === 'string' ? rawMessage : JSON.stringify(rawMessage);
    const suggestion = typeof rawSuggestion === 'string' ? rawSuggestion : null;

    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Failed to Load School Data</h2>
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
  if (!data  || !Array.isArray(data.grade_levels) || data.grade_levels.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
          <p className="text-gray-500">No data available.</p>
        </div>
      </div>
    );
  }

  const {
    grade_levels,
    all_classrooms,
    total_classrooms,
    total_students,
    classrooms_with_data,
    school_mean,
  } = data;

  const hasAnyData = classrooms_with_data > 0;

  // ── Render helpers ─────────────────────────────────────────────────
  const TrendIcon = ({ value }) => {
    if (value === undefined || value === null) return <Minus className="w-4 h-4 text-gray-400" />;
    if (value > 0) return <TrendingUp className="w-4 h-4 text-green-500" />;
    if (value < 0) return <TrendingDown className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-yellow-500" />;
  };

  const StatCard = ({ title, value, subtitle, icon: Icon, color }) => (
    <div className="bg-white rounded-lg shadow p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500 mb-1">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
        </div>
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb */}
        <div className="mb-6">
          <DrillDownBreadcrumb
            items={[{ label: 'School Performance', icon: 'school' }]}
            onHomeClick={handleBack}
          />
        </div>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between mb-6 gap-4">
          <div>
            <PageHeader
              title="School Performance"
              subtitle={`${academicYear} · All classrooms and streams`}
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
            <Calendar className="w-5 h-5 text-gray-400" />
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
            <label className="text-sm font-medium text-gray-700">View</label>
            <div className="flex bg-gray-100 rounded-lg p-0.5">
              <button
                onClick={() => setViewMode('grade')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  viewMode === 'grade'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <LayoutGrid className="w-4 h-4" />
                By Grade
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  viewMode === 'list'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <List className="w-4 h-4" />
                All Streams
              </button>
            </div>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            title="Total Classes"
            value={total_classrooms}
            subtitle={`${classrooms_with_data} with exam data`}
            icon={School}
            color="bg-blue-50 text-blue-600"
          />
          <StatCard
            title="Total Students"
            value={total_students}
            subtitle="Across all classrooms"
            icon={Users}
            color="bg-green-50 text-green-600"
          />
          <StatCard
            title="School Mean"
            value={school_mean != null ? `${school_mean}%` : '—'}
            subtitle={hasAnyData ? 'Across all classes' : 'No exam data'}
            icon={BarChart3}
            color="bg-purple-50 text-purple-600"
          />
          <StatCard
            title="Top Class"
            value={all_classrooms[0]?.name || '—'}
            subtitle={all_classrooms[0]?.mean_percentage != null ? `${all_classrooms[0].mean_percentage}%` : ''}
            icon={Award}
            color="bg-yellow-50 text-yellow-600"
          />
        </div>

        {/* No Data Banner */}
        {!hasAnyData && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-800">No exam data for {selectedTerm}</p>
              <p className="text-xs text-amber-600">
                Classrooms are set up but no exam results have been entered yet for this term.
              </p>
            </div>
          </div>
        )}

        {/* ── GROUP BY GRADE VIEW ────────────────────────────────────── */}
        {viewMode === 'grade' && (
          <div className="space-y-4">
            {grade_levels.map((grade) => {
              const isExpanded = expandedGrades.has(grade.grade_level);
              const hasData = grade.aggregate.with_data_count > 0;

              return (
                <div
                  key={grade.grade_level}
                  className="bg-white rounded-lg shadow overflow-hidden"
                >
                  {/* Grade Header */}
                  <div
                    className="p-4 flex items-center justify-between cursor-pointer hover:bg-gray-50 transition-colors"
                    onClick={() => toggleGrade(grade.grade_level)}
                  >
                    <div className="flex items-center gap-3">
                      {isExpanded ? (
                        <ChevronDown className="w-5 h-5 text-gray-400" />
                      ) : (
                        <ChevronRight className="w-5 h-5 text-gray-400" />
                      )}
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">
                          {grade.grade_level}
                        </h3>
                        <p className="text-sm text-gray-500">
                          {grade.aggregate.classroom_count} stream{grade.aggregate.classroom_count !== 1 ? 's' : ''}
                          {hasData && ` · ${grade.aggregate.student_count} students`}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      {hasData ? (
                        <>
                          <div className="text-right">
                            <p className="text-2xl font-bold text-gray-900">
                              {grade.aggregate.mean_percentage}%
                            </p>
                            <p className="text-xs text-gray-500">Grade Mean</p>
                          </div>
                          <PerformanceBandBadge
                            level={grade.aggregate.cbc_level}
                            size="md"
                            showLabel={false}
                          />
                        </>
                      ) : (
                        <span className="text-sm text-gray-400 bg-gray-100 px-3 py-1 rounded-full">
                          No data
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Streams List */}
                  {isExpanded && (
                    <div className="border-t border-gray-100">
                      {grade.classrooms.map((cls) => (
                        <div
                          key={cls.id}
                          onClick={() => cls.has_data && handleClassClick(cls.id)}
                          className={`p-4 flex items-center justify-between border-b border-gray-50 last:border-0 ${
                            cls.has_data
                              ? 'hover:bg-blue-50 cursor-pointer transition-colors'
                              : 'opacity-60'
                          }`}
                        >
                          <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center text-sm font-bold text-gray-600">
                              {cls.rank || '—'}
                            </div>
                            <div>
                              <p className="font-medium text-gray-900">
                                {cls.stream || 'Main'}
                              </p>
                              <p className="text-xs text-gray-500">
                                {cls.student_count} students
                                {cls.has_data && ` · ${cls.result_count || 0} results`}
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center gap-4">
                            {cls.has_data ? (
                              <>
                                <div className="text-right">
                                  <p className="text-lg font-semibold text-gray-900">
                                    {cls.mean_percentage}%
                                  </p>
                                  <p className="text-xs text-gray-500">Mean</p>
                                </div>
                                <PerformanceBandBadge
                                  level={cls.cbc_level}
                                  size="sm"
                                  showLabel={false}
                                />
                                <ChevronRight className="w-5 h-5 text-gray-300" />
                              </>
                            ) : (
                              <span className="text-sm text-gray-400 bg-gray-100 px-3 py-1 rounded-full flex items-center gap-1">
                                <FileText className="w-3 h-3" />
                                No exam data
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ── ALL STREAMS LIST VIEW ──────────────────────────────────── */}
        {viewMode === 'list' && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="text-left py-3 px-4 font-medium text-gray-600 w-16">Rank</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Class</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Stream</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Students</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Mean %</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Level</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Grade Spread</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {all_classrooms.length > 0 ? (
                    all_classrooms.map((cls) => (
                      <tr
                        key={cls.id}
                        onClick={() => handleClassClick(cls.id)}
                        className="border-b border-gray-100 hover:bg-blue-50 cursor-pointer transition-colors"
                      >
                        <td className="py-3 px-4">
                          <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full font-bold text-sm ${
                            cls.rank === 1 ? 'bg-yellow-100 text-yellow-700' :
                            cls.rank === 2 ? 'bg-gray-100 text-gray-600' :
                            cls.rank === 3 ? 'bg-orange-100 text-orange-700' :
                            'bg-gray-50 text-gray-500'
                          }`}>
                            {cls.rank}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-medium text-gray-900">
                          {cls.grade_level}
                        </td>
                        <td className="py-3 px-4 text-gray-600">
                          {cls.stream || '—'}
                        </td>
                        <td className="py-3 px-4 text-center text-gray-600">
                          {cls.student_count}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span className="font-semibold text-gray-900">
                            {cls.mean_percentage}%
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          <PerformanceBandBadge
                            level={cls.cbc_level}
                            size="sm"
                            showLabel={false}
                          />
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex justify-center gap-1">
                            {cls.grade_distribution && Object.entries(cls.grade_distribution.counts).map(([level, count]) => (
                              count > 0 && (
                                <span
                                  key={level}
                                  className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                                    level === 'EE' ? 'bg-green-100 text-green-700' :
                                    level === 'ME' ? 'bg-blue-100 text-blue-700' :
                                    level === 'AE' ? 'bg-orange-100 text-orange-700' :
                                    'bg-red-100 text-red-700'
                                  }`}
                                  title={`${level}: ${count} students`}
                                >
                                  {level}:{count}
                                </span>
                              )
                            ))}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <ChevronRight className="w-5 h-5 text-gray-300 inline-block" />
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-gray-400">
                        <FileText className="w-10 h-10 mx-auto mb-3 text-gray-300" />
                        <p>No classrooms with exam data for {selectedTerm}</p>
                        <p className="text-sm mt-1">Enter exam results to see rankings</p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Also show classrooms without data at the bottom */}
            {grade_levels.some(g => g.classrooms.some(c => !c.has_data)) && (
              <div className="border-t border-gray-200 bg-gray-50 p-4">
                <p className="text-sm font-medium text-gray-600 mb-3">
                  Classrooms without exam data
                </p>
                <div className="flex flex-wrap gap-2">
                  {grade_levels.flatMap(g => g.classrooms).filter(c => !c.has_data).map((cls) => (
                    <span
                      key={cls.id}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600"
                    >
                      <School className="w-3.5 h-3.5 text-gray-400" />
                      {cls.name}
                      <span className="text-xs text-gray-400">({cls.student_count} students)</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}