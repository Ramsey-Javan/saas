import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

/**
 * SubjectComparisonChart — Grouped bar chart comparing subjects.
 *
 * Props:
 *   data: Array of { subject: 'Mathematics', mean: 68.5, median: 70, pass_rate: 72.5 }
 *   title: String
 *   height: Number (default 300)
 *   showPassRate: Boolean — also show pass rate line
 */
export default function SubjectComparisonChart({
  data,
  title = 'Subject Comparison',
  height = 300,
  showPassRate = true,
}) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">{title}</h3>
        <div className="flex items-center justify-center h-64 text-gray-400">
          No subject data available
        </div>
      </div>
    );
  }

  const chartData = data.map((item) => ({
    name: item.subject?.name || item.subject || 'Unknown',
    mean: parseFloat(item.mean) || 0,
    median: parseFloat(item.median) || 0,
    pass_rate: parseFloat(item.pass_rate) || 0,
  }));

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
      </div>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            angle={-30}
            textAnchor="end"
            height={60}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 12, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine
            y={50}
            stroke="#ef4444"
            strokeDasharray="3 3"
            label={{
              value: 'Passing (50%)',
              position: 'insideBottomRight',
              fontSize: 10,
              fill: '#ef4444',
            }}
          />
          <Bar
            dataKey="mean"
            name="Mean %"
            fill="#3b82f6"
            radius={[4, 4, 0, 0]}
          />
          <Bar
            dataKey="median"
            name="Median %"
            fill="#10b981"
            radius={[4, 4, 0, 0]}
          />
          {showPassRate && (
            <Bar
              dataKey="pass_rate"
              name="Pass Rate %"
              fill="#f59e0b"
              radius={[4, 4, 0, 0]}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}