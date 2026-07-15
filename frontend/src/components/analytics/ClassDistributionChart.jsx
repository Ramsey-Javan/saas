import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

/**
 * ClassDistributionChart — Histogram showing grade distribution (EE/ME/AE/BE).
 *
 * Props:
 *   data: Array of { level, label, count, percentage, color }
 *   title: String
 *   height: Number (default 300)
 *   totalStudents: Number
 */
export default function ClassDistributionChart({
  data,
  title = 'Grade Distribution',
  height = 300,
  totalStudents,
}) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">{title}</h3>
        <div className="flex items-center justify-center h-64 text-gray-400">
          No distribution data available
        </div>
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload[0]) return null;
    const item = payload[0].payload;
    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3">
        <p className="font-semibold text-gray-800">{item.label}</p>
        <p className="text-sm text-gray-600">Students: {item.count}</p>
        <p className="text-sm text-gray-600">Percentage: {item.percentage}%</p>
        {totalStudents && (
          <p className="text-xs text-gray-400 mt-1">
            of {totalStudents} total students
          </p>
        )}
      </div>
    );
  };

  const CustomLabel = (props) => {
    const { x, y, width, value, index } = props;
    const item = data[index];
    if (!item) return null;
    return (
      <text
        x={x + width / 2}
        y={y - 8}
        fill="#374151"
        textAnchor="middle"
        fontSize={12}
        fontWeight={600}
      >
        {item.count} ({item.percentage}%)
      </text>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">{title}</h3>
      {totalStudents && (
        <p className="text-sm text-gray-500 mb-2">
          Total students: {totalStudents}
        </p>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 20, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
          <XAxis
            dataKey="level"
            tick={{ fontSize: 13, fill: '#374151', fontWeight: 600 }}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <YAxis
            tick={{ fontSize: 12, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            allowDecimals={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar
            dataKey="count"
            radius={[6, 6, 0, 0]}
            label={<CustomLabel />}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-3 mt-4 justify-center">
        {data.map((item) => (
          <div key={item.level} className="flex items-center gap-1.5">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-xs text-gray-600">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}