import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  GraduationCap, Users, DollarSign, BookOpen,
  MessageSquare, LayoutDashboard, LogOut,
  Menu, ChevronRight, Settings, AlertCircle, FilePlus,
  CheckSquare, FileText, Calendar, ClipboardList, Award,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'
import { financeApi } from '@/api/finance'
import NotificationBell from '@/components/layout/NotificationBell'

// Navigation items per role
const NAV_ITEMS = {
  admin: [
    { label: 'Dashboard', icon: LayoutDashboard, href: '/dashboard' },
    { label: 'Students', icon: Users, href: '/students' },
    { label: 'Finance', icon: DollarSign, href: '/finance' },
    { label: 'Pending Cheques', icon: AlertCircle, href: '/finance/cheques', badgeKey: 'pendingCheques' },
    { label: 'Waivers Dashboard', icon: FilePlus, href: '/finance/waivers-dashboard' },
    { label: 'Academics', icon: GraduationCap, href: '/academics' },
    { label: 'Exams', icon: ClipboardList, href: '/academics/exams' },
    { label: 'National Exams', icon: Award, href: '/academics/national-exams' },
    { label: 'Communication', icon: MessageSquare, href: '/communication' },
    { label: 'Settings', icon: Settings, href: '/settings' },
  ],
  superadmin: [
    { label: 'Platform', icon: LayoutDashboard, href: '/platform' },
    { label: 'Schools', icon: GraduationCap, href: '/platform/schools' },
  ],
  teacher: [
    { label: 'Dashboard', icon: LayoutDashboard, href: '/teacher' },
    { label: 'Students', icon: Users, href: '/students' },
    { label: 'My Classes', icon: Users, href: '/teacher/classes' },
    { label: 'Grades', icon: BookOpen, href: '/academics/grades' },
    { label: 'Exams', icon: ClipboardList, href: '/academics/exams' },
    { label: 'Attendance', icon: CheckSquare, href: '/academics/attendance' },
    { label: 'Report Cards', icon: FileText, href: '/academics/report-cards' },
    { label: 'Timetable', icon: Calendar, href: '/academics/timetable' },
    { label: 'Messages', icon: MessageSquare, href: '/communication' },
  ],
  bursar: [
    { label: 'Finance', icon: LayoutDashboard, href: '/finance' },
    { label: 'Students', icon: Users, href: '/students' },
    { label: 'Payments', icon: DollarSign, href: '/finance/payments' },
    { label: 'Pending Cheques', icon: AlertCircle, href: '/finance/cheques', badgeKey: 'pendingCheques' },
    { label: 'Generate Invoices', icon: FilePlus, href: '/finance/invoices/generate' },
    { label: 'Defaulters', icon: AlertCircle, href: '/finance/defaulters' },
    { label: 'Fee Structures', icon: DollarSign, href: '/finance/structures' },
    { label: 'Waivers Dashboard', icon: FilePlus, href: '/finance/waivers-dashboard' },
    { label: 'Waiver Policies', icon: Settings, href: '/finance/waiver-policies' },
    { label: 'Reports', icon: BookOpen, href: '/finance/reports' },
  ],
  parent: [
    { label: 'My Children', icon: Users, href: '/parent' },
    { label: 'Fees', icon: DollarSign, href: '/parent/fees' },
  ],
}

function NavItem({ item, collapsed }) {
  return (
    <NavLink
      to={item.href}
      end={item.href.split('/').length <= 2}
      className={({ isActive }) => cn(
        'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all group',
        isActive
          ? 'bg-blue-600 text-white'
          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
      )}
    >
      <item.icon size={18} className="flex-shrink-0" />
      {!collapsed && <span className="font-medium">{item.label}</span>}
      {!collapsed && item.badge > 0 && (
        <span className="ml-auto bg-red-100 text-red-700 text-xs font-semibold px-2 py-0.5 rounded-full">
          {item.badge}
        </span>
      )}
    </NavLink>
  )
}

export default function AppShell({ children }) {
  const { user, school, logout } = useAuthStore()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [pendingChequesCount, setPendingChequesCount] = useState(0)

  useEffect(() => {
    if (!user || !['admin', 'superadmin', 'bursar'].includes(user.role)) {
      setPendingChequesCount(0)
      return
    }
    financeApi.getPayments({ payment_method: 'cheque', status: 'pending' }).then(res => {
      const data = res.data
      const count = data?.count ?? (data?.results ? data.results.length : (data?.length || 0))
      setPendingChequesCount(count)
    }).catch(() => setPendingChequesCount(0))
  }, [user])

  const navItems = (NAV_ITEMS[user?.role] || []).map(item => ({
    ...item,
    badge: item.badgeKey === 'pendingCheques' ? pendingChequesCount : 0,
  }))
  const schoolName = school?.name || 'School Management'
  const primaryColor = school?.primary_color || '#2563eb'

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-gray-100">
        <div
          className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: primaryColor }}
        >
          <GraduationCap size={16} className="text-white" />
        </div>
        {!collapsed && (
          <span className="font-bold text-gray-900 text-sm truncate">{schoolName}</span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavItem key={item.href} item={item} collapsed={collapsed} />
        ))}
      </nav>

      {/* User + logout */}
      <div className="p-3 border-t border-gray-100">
        {!collapsed && (
          <div className="px-3 py-2 mb-1">
            <p className="text-sm font-medium text-gray-900 truncate">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-red-50 hover:text-red-600 transition-all w-full"
        >
          <LogOut size={18} />
          {!collapsed && <span>Sign out</span>}
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">

      {/* Desktop sidebar */}
      <aside className={cn(
        'hidden lg:flex flex-col bg-white border-r border-gray-100 transition-all duration-200',
        collapsed ? 'w-16' : 'w-56'
      )}>
        <SidebarContent />
        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(v => !v)}
          className="absolute left-0 top-1/2 -translate-y-1/2 translate-x-[calc(var(--sidebar-w)-12px)] h-6 w-6 rounded-full bg-white border border-gray-200 flex items-center justify-center shadow-sm hover:bg-gray-50 z-10"
          style={{ '--sidebar-w': collapsed ? '64px' : '224px' }}
        >
          <ChevronRight size={12} className={cn('transition-transform', collapsed ? '' : 'rotate-180')} />
        </button>
      </aside>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/30" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-56 bg-white shadow-xl z-50">
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile top bar */}
        <header className="lg:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-gray-100">
          <button onClick={() => setMobileOpen(true)} className="p-1.5 rounded-lg hover:bg-gray-100">
            <Menu size={20} />
          </button>
          <span className="font-bold text-sm text-gray-900">{schoolName}</span>
          <NotificationBell />
        </header>

        {/* Desktop header */}
        <header className="hidden lg:flex items-center justify-end px-6 py-3 bg-white border-b border-gray-100">
          <NotificationBell />
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
