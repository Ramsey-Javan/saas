import React from 'react';
import { AlertTriangle, TrendingDown, BookX, CalendarX } from 'lucide-react';
import PerformanceBandBadge from './PerformanceBandBadge';

/**
 * EarlyWarningCard — Alert card for at-risk students.
 *
 * Props:
 *   data: {
 *     at_risk_count: 12,
 *     total_students_evaluated: 450,
 *     students: [
 *       {
 *         student: { id, name, admission_number, classroom: { id, name } },
 *         risk_level: 'high' | 'medium' | 'low',
 *         risk_factors: [{ type, message, severity }],
 *         current_term_mean: 42.5,
 *         previous_term_mean: 57.5,
 *         subjects_at_risk: ['Mathematics', 'Science'],
 *         recommended_action: 'Schedule parent-teacher meeting'
 *       }
 *     ]
 *   }
 *   onStudentClick: (studentId) => void
 *   maxDisplay: Number (default 5)
 */
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
  },
  medium: {
    border: 'border-orange-300',
    bg: 'bg-orange-50',
    badge: 'bg-orange-100 text-orange-800',
    icon: 'text-orange-500',
  },
  low: {
    border: 'border-yellow-300',
    bg: 'bg-yellow-50',
    badge: 'bg-yellow-100 text-yellow-800',
    icon: 'text-yellow-500',
  },
};

export default function EarlyWarningCard({
  data,
  onStudentClick,
  maxDisplay = 5,
}) {
  // ── DEFENSIVE GUARD ─────────────────────────────────────────────
  // Handle: null, empty-state envelope from backend, or missing students array
  if (!data || data.empty === true || !data.students || data.students.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="w-5 h-5 text-green-500" />
          <h3 className="text-lg font-semibold text-gray-800">Early Warning System</h3>
        </div>
        <div className="text-center py-8">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
            <AlertTriangle className="w-8 h-8 text-green-500" />
          </div>
          <p className="text-gray-600 font-medium">
            {data?.suggestion || data?.error || 'No at-risk students detected'}
          </p>
          <p className="text-sm text-gray-400 mt-1">
            {data?.empty
              ? 'Try selecting a different term or check back after exam results are recorded.'
              : 'All students are performing at acceptable levels.'}
          </p>
        </div>
      </div>
    );
  }
  // ── END GUARD ───────────────────────────────────────────────────

  const displayStudents = data.students.slice(0, maxDisplay);

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <h3 className="text-lg font-semibold text-gray-800">Early Warning System</h3>
        </div>
        <span className="text-sm text-gray-500">
          {data.at_risk_count} of {data.total_students_evaluated} at risk
        </span>
      </div>

      <div className="space-y-3">
        {displayStudents.map((studentData) => {
          const { student, risk_level, risk_factors, current_term_mean, recommended_action } = studentData;
          const styles = RISK_LEVEL_STYLES[risk_level];

          return (
            <div
              key={student.id}
              className={`border rounded-lg p-4 ${styles.border} ${styles.bg} cursor-pointer hover:shadow-md transition-shadow`}
              onClick={() => onStudentClick?.(student.id)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-semibold text-gray-900">{student.name}</h4>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium uppercase ${styles.badge}`}>
                      {risk_level}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mb-2">
                    {student.admission_number} · {student.classroom?.name}
                  </p>

                  <div className="flex flex-wrap gap-2 mb-2">
                    {risk_factors.map((factor, idx) => {
                      const FactorIcon = RISK_ICON_MAP[factor.type] || AlertTriangle;
                      return (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1 text-xs bg-white/80 px-2 py-1 rounded-md"
                        >
                          <FactorIcon className={`w-3 h-3 ${styles.icon}`} />
                          {factor.message}
                        </span>
                      );
                    })}
                  </div>

                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-gray-600">
                      Current Mean: <strong className={current_term_mean < 50 ? 'text-red-600' : 'text-gray-900'}>
                        {current_term_mean}%
                      </strong>
                    </span>
                    {studentData.previous_term_mean && (
                      <span className="text-gray-500">
                        Previous: {studentData.previous_term_mean}%
                      </span>
                    )}
                  </div>

                  {studentData.subjects_at_risk?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {studentData.subjects_at_risk.map((subj) => (
                        <span key={subj} className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">
                          {subj}
                        </span>
                      ))}
                    </div>
                  )}

                  <p className="text-xs text-gray-500 mt-2 italic">
                    {recommended_action}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}