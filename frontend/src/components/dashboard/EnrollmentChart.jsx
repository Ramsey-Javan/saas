import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Users, GraduationCap } from 'lucide-react'
import { Card } from '@/components/ui'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm">
      <p className="font-medium text-gray-900 mb-1">{label}</p>
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-[var(--brand-primary)]" />
        <span className="text-gray-600">Students:</span>
        <span className="font-semibold text-gray-900">{payload[0].value}</span>
      </div>
    </div>
  )
}

export default function EnrollmentChart({ data, compact = false }) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) {
      return [
        { grade: 'PP1', count: 45, male: 22, female: 23 },
        { grade: 'PP2', count: 52, male: 28, female: 24 },
        { grade: 'Grade 1', count: 68, male: 35, female: 33 },
        { grade: 'Grade 2', count: 71, male: 38, female: 33 },
        { grade: 'Grade 3', count: 65, male: 32, female: 33 },
        { grade: 'Grade 4', count: 74, male: 40, female: 34 },
        { grade: 'Grade 5', count: 82, male: 42, female: 40 },
        { grade: 'Grade 6', count: 78, male: 39, female: 39 },
        { grade: 'Grade 7', count: 85, male: 44, female: 41 },
        { grade: 'Grade 8', count: 90, male: 48, female: 42 },
        { grade: 'Grade 9', count: 88, male: 45, female: 43 },
      ]
    }
    return data
  }, [data])

  const totalStudents = chartData.reduce((sum, d) => sum + d.count, 0)
  const avgClassSize = Math.round(totalStudents / chartData.length)
  const largestGrade = chartData.reduce((max, d) => d.count > max.count ? d : max, chartData[0])

  if (compact) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">Enrollment by Grade</h3>
          <span className="text-xs text-gray-500">{totalStudents} total</span>
        </div>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
              <XAxis dataKey="grade" tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} interval={1} />
              <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={24}>
                {chartData.map((entry, index) => (
                  <Cell key={index} fill={entry.grade === largestGrade.grade ? 'var(--brand-primary)' : '#e5e7eb'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Largest: <span className="font-semibold text-gray-900">{largestGrade.grade} ({largestGrade.count})</span></span>
          <span className="text-gray-500">Avg class: <span className="font-semibold text-gray-900">{avgClassSize}</span></span>
        </div>
      </div>
    )
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Enrollment by Grade</h3>
          <p className="text-sm text-gray-500 mt-0.5">Student distribution across grade levels</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <GraduationCap size={16} />
          <span>{totalStudents} students across {chartData.length} grades</span>
        </div>
      </div>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
            <XAxis dataKey="grade" tick={{ fontSize: 12, fill: '#6b7280' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 12, fill: '#6b7280' }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={40}>
              {chartData.map((entry, index) => (
                <Cell key={index} fill={entry.grade === largestGrade.grade ? 'var(--brand-primary)' : '#d1d5db'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-gray-100">
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-900">{totalStudents}</p>
          <p className="text-xs text-gray-500 mt-1">Total Students</p>
        </div>
        <div className="text-center border-x border-gray-100">
          <p className="text-2xl font-bold text-gray-900">{avgClassSize}</p>
          <p className="text-xs text-gray-500 mt-1">Avg Class Size</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-900">{largestGrade.grade}</p>
          <p className="text-xs text-gray-500 mt-1">Largest Grade ({largestGrade.count})</p>
        </div>
      </div>
    </Card>
  )
}