import { useState } from 'react'
import { BarChart3, PieChart, TrendingUp, Users, Calendar } from 'lucide-react'
import { Card } from '@/components/ui'
import FeeTrendChart from './FeeTrendChart'
import PaymentStatusChart from './PaymentStatusChart'
import EnrollmentChart from './EnrollmentChart'
import DefaultersWidget from './DefaultersWidget'
import AttendanceWidget from './AttendanceWidget'

const TABS = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'fees', label: 'Fee Trends', icon: TrendingUp },
  { id: 'payments', label: 'Payments', icon: PieChart },
  { id: 'enrollment', label: 'Enrollment', icon: Users },
  { id: 'attendance', label: 'Attendance', icon: Calendar },
]

function EmptyState({ message, icon: Icon }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-400 bg-gray-50/50 rounded-xl border border-dashed border-gray-200">
      <Icon size={32} className="mb-3 opacity-40" />
      <p className="text-sm font-medium text-gray-500">{message}</p>
      <p className="text-xs text-gray-400 mt-1">No data available for the selected period</p>
    </div>
  )
}

function hasData(data) {
  return Array.isArray(data) && data.length > 0
}

export default function AnalyticsSection({ analyticsData, timeRange, onTimeRangeChange }) {
  const [activeTab, setActiveTab] = useState('overview')

  const timeRanges = [
    { value: '7d', label: 'Last 7 days' },
    { value: '30d', label: 'Last 30 days' },
    { value: 'term', label: 'This Term' },
    { value: 'year', label: 'This Year' },
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {hasData(analyticsData?.feeTrends) ? (
              <FeeTrendChart data={analyticsData.feeTrends} compact />
            ) : (
              <EmptyState message="No fee trends available" icon={TrendingUp} />
            )}
            {hasData(analyticsData?.paymentStatus) ? (
              <PaymentStatusChart data={analyticsData.paymentStatus} compact />
            ) : (
              <EmptyState message="No payment status data" icon={PieChart} />
            )}
            {hasData(analyticsData?.enrollment) ? (
              <EnrollmentChart data={analyticsData.enrollment} compact />
            ) : (
              <EmptyState message="No enrollment data available" icon={Users} />
            )}
            {hasData(analyticsData?.defaulters) ? (
              <DefaultersWidget data={analyticsData.defaulters} compact />
            ) : (
              <EmptyState message="No defaulters data available" icon={BarChart3} />
            )}
          </div>
        )
      case 'fees':
        return hasData(analyticsData?.feeTrends) ? (
          <FeeTrendChart data={analyticsData.feeTrends} />
        ) : (
          <EmptyState message="No fee trend data available" icon={TrendingUp} />
        )
      case 'payments':
        return hasData(analyticsData?.paymentStatus) ? (
          <PaymentStatusChart data={analyticsData.paymentStatus} />
        ) : (
          <EmptyState message="No payment status data available" icon={PieChart} />
        )
      case 'enrollment':
        return hasData(analyticsData?.enrollment) ? (
          <EnrollmentChart data={analyticsData.enrollment} />
        ) : (
          <EmptyState message="No enrollment data available" icon={Users} />
        )
      case 'attendance':
        return hasData(analyticsData?.attendance) ? (
          <AttendanceWidget data={analyticsData.attendance} />
        ) : (
          <EmptyState message="No attendance data available" icon={Calendar} />
        )
      default:
        return null
    }
  }

  return (
    <Card className="p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Analytics & Insights</h2>
          <p className="text-sm text-gray-500 mt-0.5">Track key metrics and trends</p>
        </div>
        <div className="flex items-center gap-2">
          {timeRanges.map(range => (
            <button
              key={range.value}
              onClick={() => onTimeRangeChange(range.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                timeRange === range.value
                  ? 'bg-[var(--brand-primary)] text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 overflow-x-auto pb-1 scrollbar-hide">
        {TABS.map(tab => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? 'bg-[var(--brand-primary-light)] text-[var(--brand-primary)]'
                  : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
              }`}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {renderTabContent()}
    </Card>
  )
}