import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Users, DollarSign, BookOpen, TrendingUp, TrendingDown, ArrowUpCircle, FileText,
  GraduationCap, CheckSquare, AlertTriangle, Receipt, CreditCard, BarChart3,
  UserPlus, UserMinus, UserCheck, Mail, Bell, CalendarDays, FileBarChart,
  ClipboardCheck, LogIn, LogOut, Settings, Award, School
} from 'lucide-react'
import { studentsApi } from '@/api/students'
import { dashboardApi } from '@/api/dashboard'
import { financeApi } from '@/api/finance'
import { Card, Spinner } from '@/components/ui'
import AnalyticsSection from '@/components/dashboard/AnalyticsSection'
import TodoWidget from '@/components/dashboard/TodoWidget'
import UpcomingEvents from '@/components/dashboard/UpcomingEvents'

function StatCard({ title, value, icon: Icon, trend, trendValue, color = 'blue', onClick, subtitle }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
    orange: 'bg-orange-50 text-orange-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    red: 'bg-red-50 text-red-600',
    cyan: 'bg-cyan-50 text-cyan-600',
  }

  const interactiveProps = onClick
    ? {
        role: 'button',
        tabIndex: 0,
        onClick,
        onKeyDown: (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onClick()
          }
        },
      }
    : {}

  return (
    <Card
      className={`p-6 ${onClick ? 'cursor-pointer transition-all hover:shadow-lg hover:-translate-y-0.5 focus-within:ring-2 focus-within:ring-[var(--brand-primary-ring)]' : ''}`}
      {...interactiveProps}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-gray-500 mb-1">{title}</p>
          <h3 className="text-2xl font-bold text-gray-900">{value}</h3>
          {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
          {trend && (
            <div className={`flex items-center gap-1 mt-2 text-sm ${trend === 'up' ? 'text-green-600' : 'text-red-600'}`}>
              {trend === 'up' ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
              <span>{trendValue}% from last month</span>
            </div>
          )}
        </div>
        <div className={`p-3 rounded-xl ${colors[color]}`}>
          <Icon size={24} />
        </div>
      </div>
    </Card>
  )
}

const ACTIVITY_ICON_MAP = {
  student_admitted: { icon: UserPlus, color: 'bg-blue-50 text-blue-600' },
  student_transferred: { icon: ArrowUpCircle, color: 'bg-orange-50 text-orange-600' },
  student_graduated: { icon: Award, color: 'bg-purple-50 text-purple-600' },
  student_dropped: { icon: UserMinus, color: 'bg-red-50 text-red-600' },
  student_promoted: { icon: GraduationCap, color: 'bg-emerald-50 text-emerald-600' },
  staff_invited: { icon: Mail, color: 'bg-cyan-50 text-cyan-600' },
  staff_joined: { icon: UserCheck, color: 'bg-green-50 text-green-600' },
  staff_deactivated: { icon: UserMinus, color: 'bg-red-50 text-red-600' },
  staff_reactivated: { icon: UserCheck, color: 'bg-green-50 text-green-600' },
  fee_paid: { icon: DollarSign, color: 'bg-green-50 text-green-600' },
  invoice_generated: { icon: FileText, color: 'bg-blue-50 text-blue-600' },
  invoice_bulk_generated: { icon: FileBarChart, color: 'bg-blue-50 text-blue-600' },
  waiver_approved: { icon: CheckSquare, color: 'bg-emerald-50 text-emerald-600' },
  waiver_applied: { icon: CheckSquare, color: 'bg-emerald-50 text-emerald-600' },
  receipt_issued: { icon: Receipt, color: 'bg-green-50 text-green-600' },
  announcement_sent: { icon: Bell, color: 'bg-purple-50 text-purple-600' },
  announcement_scheduled: { icon: CalendarDays, color: 'bg-purple-50 text-purple-600' },
  message_sent: { icon: Mail, color: 'bg-cyan-50 text-cyan-600' },
  exam_created: { icon: BookOpen, color: 'bg-blue-50 text-blue-600' },
  exam_results_published: { icon: FileBarChart, color: 'bg-purple-50 text-purple-600' },
  report_card_generated: { icon: FileText, color: 'bg-blue-50 text-blue-600' },
  report_card_published: { icon: FileText, color: 'bg-green-50 text-green-600' },
  attendance_marked: { icon: ClipboardCheck, color: 'bg-cyan-50 text-cyan-600' },
  grade_entered: { icon: Award, color: 'bg-orange-50 text-orange-600' },
  timetable_uploaded: { icon: CalendarDays, color: 'bg-blue-50 text-blue-600' },
  login: { icon: LogIn, color: 'bg-gray-50 text-gray-600' },
  logout: { icon: LogOut, color: 'bg-gray-50 text-gray-600' },
  settings_updated: { icon: Settings, color: 'bg-gray-50 text-gray-600' },
}

function ActivityItem({ item }) {
  const config = ACTIVITY_ICON_MAP[item.type] || { icon: School, color: 'bg-gray-50 text-gray-600' }
  const Icon = config.icon

  return (
    <div className="flex items-start gap-4 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors">
      <div className={`h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${config.color}`}>
        <Icon size={14} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900">{item.title}</p>
        <p className="text-xs text-gray-500 mt-0.5">{item.description}</p>
        {item.actor && item.actor !== 'System' && (
          <p className="text-xs text-gray-400 mt-1">by {item.actor}</p>
        )}
      </div>
      <span className="text-xs text-gray-400 flex-shrink-0">
        {new Date(item.timestamp).toLocaleString('en-KE', {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        })}
      </span>
    </div>
  )
}

export default function AdminDashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState({
    totalStudents: 0,
    totalTeachers: 0,
    totalRevenue: 0,
    pendingFees: 0,
    studentsChange: 0,
    teachersChange: 0,
    revenueChange: 0,
    pendingChange: 0,
    activeWaivers: 0,
    waiversStudents: 0,
    totalStaff: 0,
    collectionRate: 0,
  })
  const [recentActivity, setRecentActivity] = useState([])
  const [loading, setLoading] = useState(true)
  const [promoting, setPromoting] = useState(false)
  const [promotionMessage, setPromotionMessage] = useState('')
  const [timeRange, setTimeRange] = useState('30d')
  const [analyticsData, setAnalyticsData] = useState({
    feeTrends: [],
    paymentStatus: [],
    enrollment: [],
    defaulters: [],
    attendance: [],
  })

  const fetchStats = async () => {
    setLoading(true)
    try {
      const [dashRes, waiversRes, defaultersRes] = await Promise.all([
        dashboardApi.getStats({ time_range: timeRange }),
        financeApi.getWaiverPoliciesDashboard().catch(() => ({ data: { results: [] } })),
        financeApi.getDefaulters({ limit: 5 }).catch(() => ({ data: { results: [] } })),
      ])

      const dashData = dashRes.data
      const waiverPolicies = waiversRes.data.results || []
      const defaulters = defaultersRes.data.results || defaultersRes.data || []

      const totalStudentsInWaivers = new Set(
        waiverPolicies.reduce((acc, policy) => {
          return acc.concat(policy.student_count || 0)
        }, [])
      ).size || 0

      const totalExpected = (dashData.total_revenue || 0) + (dashData.pending_fees || 0)
      const collectionRate = totalExpected > 0 ? Math.round(((dashData.total_revenue || 0) / totalExpected) * 100) : 0

      setStats({
        totalStudents: dashData.total_students || 0,
        totalTeachers: dashData.total_teachers || 0,
        totalRevenue: dashData.total_revenue || 0,
        pendingFees: dashData.pending_fees || 0,
        studentsChange: dashData.students_change || 0,
        teachersChange: dashData.teachers_change || 0,
        revenueChange: dashData.revenue_change || 0,
        pendingChange: dashData.pending_change || 0,
        activeWaivers: waiverPolicies.length || 0,
        waiversStudents: waiverPolicies.reduce((sum, p) => sum + (p.student_count || 0), 0) || 0,
        totalStaff: (dashData.total_teachers || 0) + 3,
        collectionRate,
      })
      setRecentActivity(dashData.recent_activity || [])
      setAnalyticsData({
        feeTrends: dashData.fee_trends || [],
        paymentStatus: dashData.payment_status || [],
        enrollment: dashData.enrollment_by_grade || [],
        defaulters: defaulters.slice(0, 5),
        attendance: dashData.attendance || [],
      })
    } catch (err) {
      console.error('Failed to fetch stats:', err)
      setStats({
        totalStudents: 0,
        totalTeachers: 0,
        totalRevenue: 0,
        pendingFees: 0,
        studentsChange: 0,
        teachersChange: 0,
        revenueChange: 0,
        pendingChange: 0,
        activeWaivers: 0,
        waiversStudents: 0,
        totalStaff: 0,
        collectionRate: 0,
      })
      setRecentActivity([])
      setAnalyticsData({
        feeTrends: [],
        paymentStatus: [],
        enrollment: [],
        defaulters: [],
        attendance: [],
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
  }, [timeRange])

  const handlePromoteAllStudents = async () => {
    const confirmed = window.confirm(
      'Promote all active students to the next grade? Grade 9 students will be marked as graduated. This cannot be undone automatically.'
    )
    if (!confirmed) return

    setPromoting(true)
    setPromotionMessage('')
    try {
      const { data } = await studentsApi.promoteAllStudents()
      setPromotionMessage(
        `Promoted ${data.promoted_count}, graduated ${data.graduated_count}, skipped ${data.skipped_count}. PP1 remaining: ${data.pp1_remaining_count}.`
      )
      await fetchStats()
    } catch (err) {
      setPromotionMessage(err.response?.data?.detail || 'Promotion failed. Please try again.')
    } finally {
      setPromoting(false)
    }
  }

  const handleCollectFee = () => {
    navigate('/finance/payments')
  }

  const handleGenerateReport = () => {
    navigate('/finance/reports')
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8" />
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">Welcome back! Here's what's happening with your school today.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Data refreshed just now</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard
          title="Total Students"
          value={stats.totalStudents}
          icon={Users}
          trend={stats.studentsChange >= 0 ? 'up' : 'down'}
          trendValue={Math.abs(stats.studentsChange)}
          color="blue"
          onClick={() => navigate('/students')}
          subtitle="Click to view all students"
        />
        <StatCard
          title="Total Teachers"
          value={stats.totalTeachers}
          icon={BookOpen}
          trend={stats.teachersChange >= 0 ? 'up' : 'down'}
          trendValue={Math.abs(stats.teachersChange)}
          color="purple"
          onClick={() => navigate('/staff')}
          subtitle="Click to manage staff"
        />
        <StatCard
          title="Total Revenue"
          value={`KES ${parseFloat(stats.totalRevenue || 0).toLocaleString()}`}
          icon={DollarSign}
          trend={stats.revenueChange >= 0 ? 'up' : 'down'}
          trendValue={Math.abs(stats.revenueChange)}
          color="green"
          onClick={() => navigate('/finance')}
          subtitle="Click to view finances"
        />
        <StatCard
          title="Pending Fees"
          value={`KES ${parseFloat(stats.pendingFees || 0).toLocaleString()}`}
          icon={AlertTriangle}
          trend={stats.pendingChange >= 0 ? 'up' : 'down'}
          trendValue={Math.abs(stats.pendingChange)}
          color="orange"
          onClick={() => navigate('/finance/defaulters')}
          subtitle="Click to view defaulters"
        />
        <StatCard
          title="Collection Rate"
          value={`${stats.collectionRate}%`}
          icon={Receipt}
          color="cyan"
          onClick={() => navigate('/finance/payments')}
          subtitle="Click to record payments"
        />
        <StatCard
          title="Active Waivers"
          value={stats.activeWaivers}
          icon={FileText}
          color="emerald"
          onClick={() => navigate('/finance/waivers-dashboard')}
          subtitle="Click to manage waivers"
        />
      </div>

      {/* Analytics Section */}
      <AnalyticsSection
        analyticsData={analyticsData}
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
      />

      {/* Quick Actions + Todo + Events Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
          <div className="space-y-3">
            <button
              onClick={handlePromoteAllStudents}
              disabled={promoting}
              className="w-full px-4 py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors text-left disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <ArrowUpCircle size={18} />
              {promoting ? 'Promoting Students...' : 'Promote All Students to Next Grade'}
            </button>
            {promotionMessage && (
              <p className="text-sm text-gray-600 bg-gray-50 p-2 rounded-lg">{promotionMessage}</p>
            )}
            <button
              onClick={() => navigate('/students/new')}
              className="w-full px-4 py-3 bg-[var(--brand-primary)] text-white rounded-lg hover:bg-[var(--brand-primary-hover)] transition-colors text-left flex items-center gap-2"
            >
              <GraduationCap size={18} />
              Admit New Student
            </button>
            <button
              onClick={handleCollectFee}
              className="w-full px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-left flex items-center gap-2"
            >
              <CreditCard size={18} />
              Collect Fee Payment
            </button>
            <button
              onClick={handleGenerateReport}
              className="w-full px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-left flex items-center gap-2"
            >
              <BarChart3 size={18} />
              Generate Report
            </button>
            <button
              onClick={() => navigate('/communication/compose')}
              className="w-full px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-left flex items-center gap-2"
            >
              <CheckSquare size={18} />
              Send Announcement
            </button>
          </div>
        </Card>

        <TodoWidget />
        <UpcomingEvents />
      </div>

      {/* Recent Activity */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
          <button
            onClick={() => navigate('/communication/logs')}
            className="text-sm text-[var(--brand-primary)] hover:underline"
          >
            View all logs
          </button>
        </div>
        {recentActivity.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <CheckSquare size={32} className="mx-auto mb-2" />
            <p>No recent activity</p>
            <p className="text-xs mt-1">School events will appear here as they happen</p>
          </div>
        ) : (
          <div className="space-y-3">
            {recentActivity.map((item) => (
              <ActivityItem key={item.id} item={item} />
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}