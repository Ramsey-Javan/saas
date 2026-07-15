import React, { useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { useSubjectTeacherClassrooms } from '../../hooks/useAnalytics';
import { ClassDistributionChart, PerformanceBandBadge, DrillDownBreadcrumb } from '../../components/analytics';
import PageHeader from '../../components/ui/PageHeader';
import Spinner from '../../components/ui/Spinner';
import { AlertTriangle, Users, ChevronDown, ChevronUp, Search } from 'lucide-react';

export default function SubjectTeacherDetailPage() {
  const { subjectId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const term = searchParams.get('term') || 'Term 2';
  const year = parseInt(searchParams.get('year') || new Date().getFullYear(), 10);

  const { data, isLoading, error } = useSubjectTeacherClassrooms(subjectId, year, term);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" className="mx-auto mb-4" />
        <p className="text-gray-500">Loading subject details...</p>
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
            onClick={() => navigate('/analytics')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <DrillDownBreadcrumb
          items={[{ label: data?.subject_name || 'Subject' }]}
          onHomeClick={() => navigate('/analytics')}
        />
        <PageHeader
          title={data?.subject_name || 'Subject Details'}
          subtitle={`${term} • ${year}`}
          className="mt-2 mb-6"
        />

        {data?.classrooms?.length === 0 && (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <p className="text-gray-500">No data available for this subject.</p>
          </div>
        )}

        {/* Classroom Cards — full width stack on mobile, 2-col on desktop */}
        <div className="space-y-6">
          {data?.classrooms?.map((cls) => (
            <ClassroomSection key={cls.id} classroom={cls} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Full-width Classroom Section ───────────────────────────────────
function ClassroomSection({ classroom }) {
  const [showAll, setShowAll] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const filteredStudents = showAll && searchQuery
    ? classroom.all_students?.filter(s =>
        s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.admission_number?.toLowerCase().includes(searchQuery.toLowerCase())
      ) || []
    : classroom.all_students || [];

  const displayStudents = showAll ? filteredStudents : classroom.all_students?.slice(0, 5) || [];

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header: stats + chart side by side on desktop */}
      <div className="p-4 sm:p-6 lg:p-8">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
          {/* Left: Classroom info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2">
              <h3 className="text-xl sm:text-2xl font-bold text-gray-900">{classroom.name}</h3>
              {classroom.stream && (
                <span className="text-xs sm:text-sm bg-gray-100 px-2.5 py-1 rounded-full text-gray-600 font-medium">
                  {classroom.stream}
                </span>
              )}
            </div>
            <div className="flex items-baseline gap-3 mb-2">
              <span className="text-4xl sm:text-5xl font-bold text-gray-900">{classroom.mean_percentage}%</span>
              <PerformanceBandBadge level={classroom.cbc_level} size="md" showLabel={true} />
            </div>
            <p className="text-sm sm:text-base text-gray-500">
              {classroom.student_count} students • {classroom.result_count} results
            </p>
          </div>

          {/* Right: Grade Distribution Chart */}
          <div className="w-full lg:w-80 xl:w-96 flex-shrink-0">
            <ClassDistributionChart
              data={classroom.grade_distribution ?
                Object.entries(classroom.grade_distribution.counts).map(([level, count]) => ({
                  level,
                  label: {EE: 'Exceeding', ME: 'Meeting', AE: 'Approaching', BE: 'Below'}[level],
                  count,
                  percentage: parseFloat(classroom.grade_distribution.percentages[level]) || 0,
                  color: {EE: '#22c55e', ME: '#eab308', AE: '#f97316', BE: '#ef4444'}[level],
                })) : []
              }
              title="Grade Distribution"
              height={220}
              totalStudents={classroom.student_count}
            />
          </div>
        </div>
      </div>

      {/* Student List — full width table */}
      <div className="border-t border-gray-100 p-4 sm:p-6 lg:p-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <h4 className="text-base sm:text-lg font-semibold text-gray-800 flex items-center gap-2">
            <Users className="w-5 h-5 text-gray-400" />
            {showAll ? `All Students (${classroom.student_count})` : 'Top Performers'}
          </h4>
          <button
            onClick={() => setShowAll(!showAll)}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1 self-start sm:self-auto"
          >
            {showAll ? (
              <>Show Less <ChevronUp className="w-4 h-4" /></>
            ) : (
              <>View All Students <ChevronDown className="w-4 h-4" /></>
            )}
          </button>
        </div>

        {/* Search bar */}
        {showAll && (
          <div className="relative mb-4 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search by name or admission number..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        )}

        {/* Student Table */}
        <div className="overflow-x-auto -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left">
                <th className="pb-3 pr-4 font-medium text-gray-500 w-12">Rank</th>
                <th className="pb-3 pr-4 font-medium text-gray-500">Student</th>
                <th className="pb-3 pr-4 font-medium text-gray-500 hidden sm:table-cell">Admission #</th>
                <th className="pb-3 pr-4 font-medium text-gray-500 text-center hidden md:table-cell">Level</th>
                <th className="pb-3 font-medium text-gray-500 text-right">Score</th>
              </tr>
            </thead>
            <tbody>
              {displayStudents.map((student, index) => (
                <StudentTableRow
                  key={student.id}
                  student={student}
                  rank={index + 1}
                />
              ))}
              {showAll && filteredStudents.length === 0 && searchQuery && (
                <tr>
                  <td colSpan="5" className="py-8 text-center text-gray-400">
                    No students match "{searchQuery}"
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ── Student Table Row ──────────────────────────────────────────────
function StudentTableRow({ student, rank }) {
  const mean = parseFloat(student.mean) || 0;
  const level = mean >= 75 ? 'EE' : mean >= 50 ? 'ME' : mean >= 30 ? 'AE' : 'BE';
  const levelColor = {
    EE: 'bg-green-100 text-green-700',
    ME: 'bg-yellow-100 text-yellow-700',
    AE: 'bg-orange-100 text-orange-700',
    BE: 'bg-red-100 text-red-700',
  }[level];
  const levelLabel = { EE: 'Exceeding', ME: 'Meeting', AE: 'Approaching', BE: 'Below' }[level];

  return (
    <tr className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
      <td className="py-3 pr-4">
        <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
          rank <= 3 ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'
        }`}>
          {rank}
        </span>
      </td>
      <td className="py-3 pr-4">
        <p className="font-medium text-gray-900">{student.name}</p>
      </td>
      <td className="py-3 pr-4 text-gray-500 hidden sm:table-cell">
        {student.admission_number || '—'}
      </td>
      <td className="py-3 pr-4 text-center hidden md:table-cell">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium ${levelColor}`}>
          {levelLabel}
        </span>
      </td>
      <td className="py-3 text-right">
        <span className={`font-semibold ${
          mean >= 75 ? 'text-green-600' : mean >= 50 ? 'text-yellow-600' : mean >= 30 ? 'text-orange-600' : 'text-red-600'
        }`}>
          {mean}%
        </span>
      </td>
    </tr>
  );
}