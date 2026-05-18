import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, DollarSign, BookOpen, TrendingUp, TrendingDown, ArrowUpCircle, FileText } from 'lucide-react'
import { studentsApi } from '@/api/students'
import { dashboardApi } from '@/api/dashboard'
import { financeApi } from '@/api/finance'
import { Card, Spinner } from '@/components/ui'

function StatCard({ title, value, icon: Icon, trend, trendValue, color = 'blue', onClick }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
    orange: 'bg-orange-50 text-orange-600',
    emerald: 'bg-emerald-50 text-emerald-600',
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
      className={`p-6 ${onClick ? 'cursor-pointer transition-shadow hover:shadow-md focus-within:ring-2 focus-within:ring-blue-100' : ''}`}
      {...interactiveProps}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 mb-1">{title}</p>
          <h3 className="text-2xl font-bold text-gray-900">{value}</h3>
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
  })
  const [recentActivity, setRecentActivity] = useState([])
  const [loading, setLoading] = useState(true)
  const [promoting, setPromoting] = useState(false)
  const [promotionMessage, setPromotionMessage] = useState('')

  const fetchStats = async () => {
    try {
      const [dashRes, waiversRes] = await Promise.all([
        dashboardApi.getStats(),
        financeApi.getWaiverPoliciesDashboard().catch(() => ({ data: { results: [] } })),
      ])
      
      const dashData = dashRes.data
      const waiverPolicies = waiversRes.data.results || []
      
      // Count total students and policies
      const totalStudentsInWaivers = new Set(
        waiverPolicies.reduce((acc, policy) => {
          // This is approximate - would need better backend data
          return acc.concat(policy.student_count || 0)
        }, [])
      ).size || 0

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
      })
      setRecentActivity(dashData.recent_activity || [])
    } catch (err) {
      console.error('Failed to fetch stats:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
  }, [])

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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8" />
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">Welcome back! Here's what's happening with your school today.</p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
          <StatCard
            title="Total Students"
            value={stats.totalStudents}
            icon={Users}
            trend={stats.studentsChange >= 0 ? 'up' : 'down'}
            trendValue={Math.abs(stats.studentsChange)}
            color="blue"
            onClick={() => navigate('/students')}
          />
          <StatCard
            title="Total Teachers"
            value={stats.totalTeachers}
            icon={BookOpen}
            trend={stats.teachersChange >= 0 ? 'up' : 'down'}
            trendValue={Math.abs(stats.teachersChange)}
            color="purple"
          />
          <StatCard
            title="Total Revenue"
            value={`KES ${parseFloat(stats.totalRevenue || 0).toLocaleString()}`}
            icon={DollarSign}
            trend={stats.revenueChange >= 0 ? 'up' : 'down'}
            trendValue={Math.abs(stats.revenueChange)}
            color="green"
          />
          <StatCard
            title="Pending Fees"
            value={`KES ${parseFloat(stats.pendingFees || 0).toLocaleString()}`}
            icon={DollarSign}
            trend={stats.pendingChange >= 0 ? 'up' : 'down'}
            trendValue={Math.abs(stats.pendingChange)}
            color="orange"
          />
          <StatCard
            title="Active Waivers"
            value={stats.activeWaivers}
            icon={FileText}
            color="emerald"
            onClick={() => navigate('/finance/waivers-dashboard')}
          />
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                <p className="text-sm text-gray-600">{promotionMessage}</p>
              )}
              <button
                onClick={() => navigate('/students/new')}
                className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-left"
              >
                Admit New Student
              </button>
              <button className="w-full px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-left">
                Collect Fee Payment
              </button>
              <button className="w-full px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-left">
                Generate Report
              </button>
            </div>
          </Card>

          <Card className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h2>
            {recentActivity.length === 0 ? (
              <div className="space-y-3 text-sm text-gray-600">
                <p>No recent activity</p>
              </div>
            ) : (
              <div className="space-y-3 text-sm text-gray-600">
                {recentActivity.map((item, index) => (
                  <div key={`${item.type}-${index}`} className="flex justify-between gap-4">
                    <span>{item.description}</span>
                    <span className="text-xs text-gray-400">
                      {new Date(item.timestamp).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
    </div>
  )
}
