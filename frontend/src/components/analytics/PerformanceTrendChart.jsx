import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

/**
 * PerformanceTrendChart — Line chart showing term-over-term trajectory.
 *
 * Props:
 *   data: Array of { term, subjectName: percentage, ... }
 *   subjects: Array of { key: 'math', name: 'Mathematics', color: '#8884d8' }
 *   cohortAverage: Number — dashed reference line value (optional)
 *   title: String
 *   height: Number (default 300)
 */
export default function PerformanceTrendChart({
  data,
  subjects,
  cohortAverage,
  title = 'Performance Trend',
  height = 300,
}) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">{title}</h3>
        <div className="flex items-center justify-center h-64 text-gray-400">
          No trend data available
        </div>
      </div>
    );
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload) return null;
    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3">
        <p className="font-semibold text-gray-800 mb-1">{label}</p>
        {payload.map((entry, idx) => (
          <p key={idx} className="text-sm" style={{ color: entry.color }}>
            {entry.name}: {entry.value}%
          </p>
        ))}
        {cohortAverage && (
          <p className="text-sm text-gray-500 mt-1 border-t pt-1">
            Class Average: {cohortAverage}%
          </p>
        )}
      </div>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="term"
            tick={{ fontSize: 12, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 12, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 12, paddingTop: 10 }}
          />
          {cohortAverage !== undefined && cohortAverage !== null && (
            <ReferenceLine
              y={cohortAverage}
              stroke="#9ca3af"
              strokeDasharray="5 5"
              strokeWidth={1}
              label={{
                value: `Class Avg: ${cohortAverage}%`,
                position: 'insideTopRight',
                fontSize: 11,
                fill: '#9ca3af',
              }}
            />
          )}
          {subjects.map((subj) => (
            <Line
              key={subj.key}
              type="monotone"
              dataKey={subj.key}
              name={subj.name}
              stroke={subj.color}
              strokeWidth={2.5}
              dot={{ r: 4, strokeWidth: 2, fill: '#fff' }}
              activeDot={{ r: 6, strokeWidth: 2 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}