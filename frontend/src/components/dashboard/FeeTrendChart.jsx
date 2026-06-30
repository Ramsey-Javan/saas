import { useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart
} from 'recharts'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { Card } from '@/components/ui'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm">
      <p className="font-medium text-gray-900 mb-1">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-gray-600">{entry.name}:</span>
          <span className="font-semibold text-gray-900">KES {entry.value?.toLocaleString()}</span>
        </div>
      ))}
    </div>
  )
}

export default function FeeTrendChart({ data, compact = false }) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) {
      return [
        { label: 'Jan', collected: 450000, expected: 500000 },
        { label: 'Feb', collected: 520000, expected: 550000 },
        { label: 'Mar', collected: 480000, expected: 500000 },
        { label: 'Apr', collected: 610000, expected: 600000 },
        { label: 'May', collected: 580000, expected: 600000 },
        { label: 'Jun', collected: 650000, expected: 620000 },
      ]
    }
    return data
  }, [data])

  const totalCollected = chartData.reduce((sum, d) => sum + (d.collected || 0), 0)
  const totalExpected = chartData.reduce((sum, d) => sum + (d.expected || 0), 0)
  const collectionRate = totalExpected > 0 ? Math.round((totalCollected / totalExpected) * 100) : 0
  const trend = chartData.length > 1
    ? (chartData[chartData.length - 1].collected || 0) - (chartData[0].collected || 0)
    : 0

  if (compact) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">Fee Collection Trend</h3>
          <div className="flex items-center gap-1 text-xs">
            {trend > 0 ? (
              <TrendingUp size={12} className="text-green-500" />
            ) : trend < 0 ? (
              <TrendingDown size={12} className="text-red-500" />
            ) : (
              <Minus size={12} className="text-gray-400" />
            )}
            <span className={trend > 0 ? 'text-green-600' : trend < 0 ? 'text-red-600' : 'text-gray-500'}>
              {trend > 0 ? '+' : ''}{trend === 0 ? 'No change' : `KES ${Math.abs(trend).toLocaleString()}`}
            </span>
          </div>
        </div>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorCollected" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--brand-primary)" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="var(--brand-primary)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} tickFormatter={v => `K${(v/1000).toFixed(0)}k`} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="collected" stroke="var(--brand-primary)" strokeWidth={2} fill="url(#colorCollected)" name="Collected" />
              <Area type="monotone" dataKey="expected" stroke="#e5e7eb" strokeWidth={1} strokeDasharray="4 4" fill="transparent" name="Expected" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Collection rate: <span className="font-semibold text-gray-900">{collectionRate}%</span></span>
          <span className="text-gray-500">Total: <span className="font-semibold text-gray-900">KES {totalCollected.toLocaleString()}</span></span>
        </div>
      </div>
    )
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Fee Collection Trend</h3>
          <p className="text-sm text-gray-500 mt-0.5">Collected vs Expected fees over time</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm">
            <div className="w-3 h-3 rounded-full bg-[var(--brand-primary)]" />
            <span className="text-gray-600">Collected</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <div className="w-3 h-3 rounded-full bg-gray-300" />
            <span className="text-gray-600">Expected</span>
          </div>
        </div>
      </div>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorCollectedFull" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--brand-primary)" stopOpacity={0.2} />
                <stop offset="95%" stopColor="var(--brand-primary)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#6b7280' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 12, fill: '#6b7280' }} axisLine={false} tickLine={false} tickFormatter={v => `K${(v/1000).toFixed(0)}k`} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="collected" stroke="var(--brand-primary)" strokeWidth={2.5} fill="url(#colorCollectedFull)" name="Collected" />
            <Area type="monotone" dataKey="expected" stroke="#d1d5db" strokeWidth={1.5} strokeDasharray="5 5" fill="transparent" name="Expected" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-gray-100">
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-900">{collectionRate}%</p>
          <p className="text-xs text-gray-500 mt-1">Collection Rate</p>
        </div>
        <div className="text-center border-x border-gray-100">
          <p className="text-2xl font-bold text-gray-900">KES {totalCollected.toLocaleString()}</p>
          <p className="text-xs text-gray-500 mt-1">Total Collected</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-900">KES {(totalExpected - totalCollected).toLocaleString()}</p>
          <p className="text-xs text-gray-500 mt-1">Outstanding</p>
        </div>
      </div>
    </Card>
  )
}