import { useMemo } from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { CheckCircle, Clock, AlertCircle, XCircle } from 'lucide-react'
import { Card } from '@/components/ui'

const COLORS = {
  paid: '#10b981',
  partial: '#f59e0b',
  unpaid: '#ef4444',
  overdue: '#7c3aed',
}

const STATUS_ICONS = {
  paid: CheckCircle,
  partial: Clock,
  unpaid: XCircle,
  overdue: AlertCircle,
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm">
      <div className="flex items-center gap-2 mb-1">
        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: data.color }} />
        <span className="font-medium text-gray-900 capitalize">{data.name}</span>
      </div>
      <p className="text-gray-600">Count: <span className="font-semibold">{data.value.toLocaleString()}</span></p>
      <p className="text-gray-600">Amount: <span className="font-semibold">KES {data.amount?.toLocaleString()}</span></p>
      <p className="text-gray-600">Percentage: <span className="font-semibold">{data.percentage}%</span></p>
    </div>
  )
}

export default function PaymentStatusChart({ data, compact = false }) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) {
      return [
        { name: 'paid', value: 520, amount: 3120000, color: COLORS.paid },
        { name: 'partial', value: 180, amount: 890000, color: COLORS.partial },
        { name: 'unpaid', value: 120, amount: 1450000, color: COLORS.unpaid },
        { name: 'overdue', value: 40, amount: 480000, color: COLORS.overdue },
      ]
    }
    const total = data.reduce((sum, d) => sum + d.value, 0)
    return data.map(d => ({
      ...d,
      color: COLORS[d.name] || '#9ca3af',
      percentage: total > 0 ? Math.round((d.value / total) * 100) : 0,
    }))
  }, [data])

  const totalStudents = chartData.reduce((sum, d) => sum + d.value, 0)
  const totalAmount = chartData.reduce((sum, d) => sum + (d.amount || 0), 0)

  if (compact) {
    return (
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-700">Payment Status</h3>
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={65}
                paddingAngle={3}
                dataKey="value"
                stroke="none"
              >
                {chartData.map((entry, index) => (
                  <Cell key={index} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {chartData.map(item => {
            const Icon = STATUS_ICONS[item.name]
            return (
              <div key={item.name} className="flex items-center gap-2 text-xs">
                <Icon size={12} style={{ color: item.color }} />
                <span className="capitalize text-gray-600">{item.name}:</span>
                <span className="font-semibold text-gray-900">{item.value}</span>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Payment Status Breakdown</h3>
          <p className="text-sm text-gray-500 mt-0.5">Distribution of student fee statuses</p>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={70}
                outerRadius={110}
                paddingAngle={4}
                dataKey="value"
                stroke="none"
              >
                {chartData.map((entry, index) => (
                  <Cell key={index} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend
                verticalAlign="bottom"
                height={36}
                formatter={(value) => <span className="capitalize text-sm text-gray-600">{value}</span>}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-3">
          {chartData.map(item => {
            const Icon = STATUS_ICONS[item.name]
            return (
              <div key={item.name} className="flex items-center gap-4 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors">
                <div className="h-10 w-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${item.color}15` }}>
                  <Icon size={20} style={{ color: item.color }} />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-900 capitalize">{item.name}</span>
                    <span className="text-sm font-bold text-gray-900">{item.value}</span>
                  </div>
                  <div className="flex items-center justify-between mt-0.5">
                    <span className="text-xs text-gray-500">KES {item.amount?.toLocaleString()}</span>
                    <span className="text-xs font-medium" style={{ color: item.color }}>{item.percentage}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-gray-200 rounded-full mt-2 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${item.percentage}%`, backgroundColor: item.color }}
                    />
                  </div>
                </div>
              </div>
            )
          })}
          <div className="pt-3 border-t border-gray-200">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Total Students</span>
              <span className="font-bold text-gray-900">{totalStudents.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between text-sm mt-1">
              <span className="text-gray-600">Total Amount</span>
              <span className="font-bold text-gray-900">KES {totalAmount.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </div>
    </Card>
  )
}