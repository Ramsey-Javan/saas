import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  GraduationCap, Users, DollarSign, BookOpen,
  MessageSquare, LayoutDashboard, LogOut,
  Menu, ChevronRight, Settings, AlertCircle, FilePlus,
  CheckSquare, FileText, Calendar, ClipboardList, Award, Globe,
  Search, Command, Crown
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'
import { financeApi } from '@/api/finance'
import { studentsApi } from '@/api/students'
import NotificationBell from '@/components/layout/NotificationBell'
import TrialBanner from '@/components/layout/TrialBanner'
import CommandPalette from '@/components/command-palette/CommandPalette'
import { useCommandPalette } from '@/components/command-palette/useCommandPalette'

const SEARCH_ALLOWED_ROLES = ['admin', 'superadmin']

// Navigation items per role
const NAV_ITEMS = {
  admin: [
    { label: 'Dashboard', icon: LayoutDashboard, href: '/dashboard' },
    { label: 'Students', icon: Users, href: '/students' },
    { label: 'Staff', icon: Users, href: '/staff' },
    { label: 'Finance', icon: DollarSign, href: '/finance' },
    { label: 'Pending Cheques', icon: AlertCircle, href: '/finance/cheques', badgeKey: 'pendingCheques' },
    { label: 'Waivers Dashboard', icon: FilePlus, href: '/finance/waivers-dashboard' },
    { label: 'Academics', icon: GraduationCap, href: '/academics' },
    { label: 'Exams', icon: ClipboardList, href: '/academics/exams' },
    { label: 'National Exams', icon: Award, href: '/academics/national-exams' },
    { label: 'Communication', icon: MessageSquare, href: '/communication' },
    { label: 'Settings', icon: Settings, href: '/settings/school-profile' },
  ],
  superadmin: [
    { label: 'Platform', icon: Globe, href: '/platform' },
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

// Inserted right after "Students" in the teacher nav when applicable —
// not part of the static NAV_ITEMS.teacher array because its visibility
// depends on a runtime check (is this teacher homeroom for any class),
// not just their role.
const HOME_CLASS_ITEM = { label: 'Home Class', icon: Crown, href: '/teacher/home-class' }

function NavItem({ item, collapsed, badge }) {
  return (
    <NavLink
      to={item.href}
      end={item.href.split('/').length <= 2}
      className={({ isActive }) => cn(
        'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all group',
        isActive
          ? 'bg-[var(--brand-primary)] text-white'
          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
      )}
    >
      <item.icon size={18} className="flex-shrink-0" />
      {!collapsed && <span className="font-medium">{item.label}</span>}
      {!collapsed && badge > 0 && (
        <span className="ml-auto bg-red-100 text-red-700 text-xs font-semibold px-2 py-0.5 rounded-full">
          {badge}
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
  const [isHomeroomTeacher, setIsHomeroomTeacher] = useState(false)
  const { open: paletteOpen, setOpen: setPaletteOpen } = useCommandPalette()

  const canSearch = SEARCH_ALLOWED_ROLES.includes(user?.role)

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

  useEffect(() => {
    if (user?.role !== 'teacher') {
      setIsHomeroomTeacher(false)
      return
    }
    studentsApi.getClassrooms({ class_teacher: user.id })
      .then(r => {
        const list = r.data?.results || (Array.isArray(r.data) ? r.data : [])
        setIsHomeroomTeacher(list.length > 0)
      })
      .catch(() => setIsHomeroomTeacher(false))
  }, [user])

  // Force-close the palette if it's somehow open for a non-admin (e.g. a
  // role change mid-session via the Edit Staff role-change flow we built
  // earlier) — belt and suspenders alongside not rendering the trigger or
  // mounting the component below at all for non-admins.
  useEffect(() => {
    if (!canSearch && paletteOpen) {
      setPaletteOpen(false)
    }
  }, [canSearch, paletteOpen, setPaletteOpen])

  const baseNavItems = NAV_ITEMS[user?.role] || NAV_ITEMS.admin
  const navItems = (user?.role === 'teacher' && isHomeroomTeacher)
    ? (() => {
        const studentsIndex = baseNavItems.findIndex(item => item.href === '/students')
        if (studentsIndex === -1) return [...baseNavItems, HOME_CLASS_ITEM]
        const next = [...baseNavItems]
        next.splice(studentsIndex + 1, 0, HOME_CLASS_ITEM)
        return next
      })()
    : baseNavItems

  const schoolName = school?.name || 'School Management'

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
          style={{ backgroundColor: 'var(--brand-primary)' }}
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
          <NavItem
            key={item.href}
            item={item}
            collapsed={collapsed}
            badge={item.badgeKey === 'pendingCheques' ? pendingChequesCount : 0}
          />
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
      {/* Command Palette — admin/superadmin only. Not mounted at all for
          other roles, so there's no hidden data-fetching or keyboard
          shortcut surface for them even if someone tried to force it open. */}
      {canSearch && <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />}

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
        <TrialBanner />

        {/* Mobile top bar */}
        <header className="lg:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-gray-100">
          <button onClick={() => setMobileOpen(true)} className="p-1.5 rounded-lg hover:bg-gray-100">
            <Menu size={20} />
          </button>
          <span className="font-bold text-sm text-gray-900">{schoolName}</span>
          <NotificationBell />
        </header>

        {/* Desktop header with search */}
        <header className="hidden lg:flex items-center justify-between px-6 py-3 bg-white border-b border-gray-100">
          <div className="flex items-center gap-4 flex-1">
            {/* Global Search Trigger — admin/superadmin only */}
            {canSearch && (
              <button
                onClick={() => setPaletteOpen(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors w-full max-w-md"
                type="button"
              >
                <Search size={16} />
                <span className="flex-1 text-left">Search students, staff, pages...</span>
                <kbd className="hidden sm:inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-white border border-gray-200 text-xs text-gray-400 font-mono">
                  <Command size={10} />K
                </kbd>
              </button>
            )}
          </div>
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