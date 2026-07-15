
import React, { useState, useMemo } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Users,
  BookOpen,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  ChevronRight,
  BarChart3,
} from 'lucide-react';
import {
  useClassPerformance,
  useSubjectComparison,
  useGradeDistribution,
  useClassRanking,
} from '../../hooks/useAnalytics';
import {
  ClassDistributionChart,
  SubjectComparisonChart,
  PerformanceBandBadge,
  DrillDownBreadcrumb,
} from '../../components/analytics';
import PageHeader from '../../components/ui/PageHeader';
import Spinner from '../../components/ui/Spinner';

/**
 * ClassPerformancePage — Drill-down view for a specific class.
 *
 * Features:
 * - Per-subject performance table
 * - Grade distribution chart
 * - Subject comparison chart
 * - Student rankings table
 * - Filter by term and exam type
 */
export default function ClassPerformancePage() {
  const { classroomId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const initialTerm = searchParams.get('term') || 'Term 2';
  const initialYear = Number(searchParams.get('year')) || new Date().getFullYear();

  const [term, setTerm] = useState(initialTerm);
  const [academicYear, setAcademicYear] = useState(initialYear);
  const [selectedExamType, setSelectedExamType] = useState('midterm');

  const {
    data: classData,
    isLoading: classLoading,
    error: classError,
  } = useClassPerformance(classroomId, term, academicYear);

  const {
    data: subjectComparisonData,
    isLoading: comparisonLoading,
  } = useSubjectComparison(classroomId, term, academicYear);

  const {
    data: gradeDistData,
    isLoading: distLoading,
  } = useGradeDistribution(classroomId, selectedExamType, term, academicYear);

  const {
    data: rankingData,
    isLoading: rankingLoading,
  } = useClassRanking(classroomId, term, academicYear);

  // Transform grade distribution data for chart
  const chartGradeData = useMemo(() => {
    if (!gradeDistData?.bins) return [];
    return gradeDistData.bins;
  }, [gradeDistData]);

  // Transform subject comparison for chart
  const chartSubjectData = useMemo(() => {
    if (!subjectComparisonData?.subjects) return [];
    return subjectComparisonData.subjects;
  }, [subjectComparisonData]);

  const handleStudentClick = (studentId) => {
    navigate(`/analytics/student/${studentId}?year=${academicYear}`);
  };

  const handleBack = () => {
    navigate('/analytics');
  };

  // Loading state
  if (classLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-4" />
          <p className="text-gray-500">Loading class analytics...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (classError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Failed to Load Class Data</h2>
          <p className="text-gray-500 mb-4">{classError.message}</p>
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

  if (!classData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
          <p className="text-gray-500">No data available for this class.</p>
        </div>
      </div>
    );
  }

  const { classroom, subjects, student_count } = classData;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb */}
        <div className="mb-6">
          <DrillDownBreadcrumb
            items={[
              { label: classroom.name, icon: 'class' },
            ]}
            onHomeClick={handleBack}
          />
        </div>

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <PageHeader
              title={classroom.name}
              subtitle={`${student_count} students · ${classroom.grade_level || 'Grade Level N/A'}`}
            />
          </div>
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
              {[new Date().getFullYear() + 1, new Date().getFullYear(), new Date().getFullYear() - 1, new Date().getFullYear() - 2].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Exam Type</label>
            <select
              value={selectedExamType}
              onChange={(e) => setSelectedExamType(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="opener">Opener</option>
              <option value="midterm">Mid-Term</option>
              <option value="endterm">End Term</option>
              <option value="mock">Mock</option>
            </select>
          </div>
        </div>

        {/* Subject Performance Table */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-500" />
            Subject Performance
          </h3>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Subject</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Teacher</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-600">Mean %</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-600">Highest</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-600">Lowest</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-600">Students</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-600">Grade Spread</th>
                </tr>
              </thead>
              <tbody>
                {subjects.map((subject) => (
                  <tr key={subject.subject.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div>
                        <p className="font-medium text-gray-900">{subject.subject.name}</p>
                        <p className="text-xs text-gray-400">{subject.subject.code}</p>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {subject.teacher?.name || '—'}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className="font-semibold text-gray-900">{subject.mean_percentage}%</span>
                    </td>
                    <td className="py-3 px-4 text-center text-green-600 font-medium">
                      {subject.highest}
                    </td>
                    <td className="py-3 px-4 text-center text-red-600 font-medium">
                      {subject.lowest}
                    </td>
                    <td className="py-3 px-4 text-center text-gray-600">
                      {subject.student_count}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-center gap-1">
                        {Object.entries(subject.grade_distribution.counts).map(([level, count]) => (
                          count > 0 && (
                            <span
                              key={level}
                              className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                                level === 'EE' ? 'bg-green-100 text-green-700' :
                                level === 'ME' ? 'bg-yellow-100 text-yellow-700' :
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <SubjectComparisonChart
            data={chartSubjectData}
            title="Subject Comparison"
            height={320}
          />

          <ClassDistributionChart
            data={chartGradeData}
            title={`${selectedExamType.charAt(0).toUpperCase() + selectedExamType.slice(1)} Grade Distribution`}
            height={320}
            totalStudents={gradeDistData?.total_students}
          />
        </div>

        {/* Student Rankings */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-purple-500" />
            Student Rankings
          </h3>

          {rankingLoading ? (
            <div className="text-center py-8">
              <Spinner size="md" className="mx-auto mb-2" />
              <p className="text-gray-400">Loading rankings...</p>
            </div>
          ) : rankingData?.rankings?.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Rank</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Student</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Admission #</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Mean %</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Level</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rankingData.rankings.map((entry) => (
                    <tr
                      key={entry.student.id}
                      className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                      onClick={() => handleStudentClick(entry.student.id)}
                    >
                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full font-bold text-sm ${
                          entry.rank === 1 ? 'bg-yellow-100 text-yellow-700' :
                          entry.rank === 2 ? 'bg-gray-100 text-gray-600' :
                          entry.rank === 3 ? 'bg-orange-100 text-orange-700' :
                          'bg-gray-50 text-gray-500'
                        }`}>
                          {entry.rank}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-medium text-gray-900">
                        {entry.student.name}
                      </td>
                      <td className="py-3 px-4 text-gray-500">
                        {entry.student.admission_number || '—'}
                      </td>
                      <td className="py-3 px-4 text-center font-semibold">
                        {entry.mean_percentage}%
                      </td>
                      <td className="py-3 px-4 text-center">
                        <PerformanceBandBadge level={entry.cbc_level} size="sm" showLabel={false} />
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button className="text-blue-600 hover:text-blue-800 text-sm font-medium flex items-center gap-1 ml-auto">
                          View
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400">
              <TrendingUp className="w-8 h-8 mx-auto mb-2" />
              <p>No ranking data available</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}