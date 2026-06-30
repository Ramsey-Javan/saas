import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, X, User, Users, BookOpen, DollarSign, FileText,
  GraduationCap, LayoutDashboard, MessageSquare, Settings,
  ArrowRight, Loader2, AlertCircle, ChevronRight
} from 'lucide-react'
import { studentsApi } from '@/api/students'
import { cn } from '@/lib/utils'

const NAV_ACTIONS = [
  { id: 'nav-students', label: 'Students', icon: Users, href: '/students', keywords: 'student pupil learner' },
  { id: 'nav-staff', label: 'Staff', icon: User, href: '/staff', keywords: 'teacher employee personnel' },
  { id: 'nav-finance', label: 'Finance Dashboard', icon: DollarSign, href: '/finance', keywords: 'fee payment money' },
  { id: 'nav-payments', label: 'Payments', icon: DollarSign, href: '/finance/payments', keywords: 'collect fee payment' },
  { id: 'nav-defaulters', label: 'Defaulters', icon: AlertCircle, href: '/finance/defaulters', keywords: 'debt owed unpaid' },
  { id: 'nav-fee-structures', label: 'Fee Structures', icon: FileText, href: '/finance/structures', keywords: 'fee structure term' },
  { id: 'nav-waivers', label: 'Waivers Dashboard', icon: FileText, href: '/finance/waivers-dashboard', keywords: 'waiver discount' },
  { id: 'nav-academics', label: 'Academics', icon: BookOpen, href: '/academics', keywords: 'class grade subject' },
  { id: 'nav-exams', label: 'Exams', icon: GraduationCap, href: '/academics/exams', keywords: 'exam test assessment' },
  { id: 'nav-national-exams', label: 'National Exams', icon: GraduationCap, href: '/academics/national-exams', keywords: 'kcpe kcse knec' },
  { id: 'nav-communication', label: 'Communication', icon: MessageSquare, href: '/communication', keywords: 'message sms email' },
  { id: 'nav-settings', label: 'Settings', icon: Settings, href: '/settings/school-profile', keywords: 'config profile' },
  { id: 'nav-dashboard', label: 'Dashboard', icon: LayoutDashboard, href: '/dashboard', keywords: 'home overview' },
]

function HighlightMatch({ text, query }) {
  if (!query) return <>{text}</>
  const parts = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')})`, 'gi'))
  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === query.toLowerCase() ? (
          <mark key={i} className="bg-yellow-200 text-gray-900 rounded px-0.5">{part}</mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  )
}

export default function CommandPalette({ open, onOpenChange }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState({ students: [], staff: [], actions: [] })
  const [loading, setLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const searchTimeout = useRef(null)
  const containerRef = useRef(null)

  // Reset state when opening
  useEffect(() => {
    if (open) {
      setQuery('')
      setResults({ students: [], staff: [], actions: [] })
      setSelectedIndex(0)
      setLoading(false)
      // Focus input after animation
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open])

  const performSearch = useCallback(async (q) => {
    if (!q || q.length < 2) {
      setResults({ students: [], staff: [], actions: [] })
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const [studentsRes, staffRes] = await Promise.all([
        studentsApi.searchStudents(q).catch(() => ({ data: [] })),
        studentsApi.getStaff ? studentsApi.getStaff({ search: q }) : Promise.resolve({ data: [] }),
      ])

      const students = (studentsRes.data || []).slice(0, 5)
      const staff = (staffRes.data?.results || staffRes.data || []).slice(0, 5)

      const lowerQ = q.toLowerCase()
      const matchedActions = NAV_ACTIONS.filter(a =>
        a.label.toLowerCase().includes(lowerQ) ||
        a.keywords.toLowerCase().includes(lowerQ)
      ).slice(0, 5)

      setResults({ students, staff, actions: matchedActions })
      setSelectedIndex(0)
    } catch {
      setResults({ students: [], staff: [], actions: [] })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    searchTimeout.current = setTimeout(() => performSearch(query.trim()), 200)
    return () => clearTimeout(searchTimeout.current)
  }, [query, performSearch])

  const allItems = [
    ...results.students.map(s => ({ type: 'student', data: s })),
    ...results.staff.map(s => ({ type: 'staff', data: s })),
    ...results.actions.map(a => ({ type: 'action', data: a })),
  ]

  const handleSelect = (item) => {
    onOpenChange(false)
    setQuery('')
    if (item.type === 'student') {
      navigate(`/students/${item.data.id}`)
    } else if (item.type === 'staff') {
      navigate(`/staff/${item.data.id}`)
    } else if (item.type === 'action') {
      navigate(item.data.href)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(i => (i + 1) % Math.max(allItems.length, 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(i => (i - 1 + Math.max(allItems.length, 1)) % Math.max(allItems.length, 1))
    } else if (e.key === 'Enter' && allItems[selectedIndex]) {
      e.preventDefault()
      handleSelect(allItems[selectedIndex])
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onOpenChange(false)
    }
  }

  useEffect(() => {
    if (listRef.current && allItems.length > 0) {
      const el = listRef.current.children[selectedIndex]
      if (el) el.scrollIntoView({ block: 'nearest' })
    }
  }, [selectedIndex, allItems.length])

  const hasResults = allItems.length > 0
  const showEmpty = query.length >= 2 && !loading && !hasResults

  // Don't render anything if not open
  if (!open) return null

  return (
    <div 
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4"
      onKeyDown={handleKeyDown}
      ref={containerRef}
    >
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => onOpenChange(false)} />
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-4 border-b border-gray-100">
          <Search size={20} className="text-gray-400 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search students, staff, or pages..."
            className="flex-1 text-base bg-transparent outline-none placeholder:text-gray-400 text-gray-900"
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
          />
          {loading ? (
            <Loader2 size={18} className="animate-spin text-gray-400" />
          ) : query ? (
            <button onClick={() => { setQuery(''); inputRef.current?.focus() }} className="p-1 rounded hover:bg-gray-100" type="button">
              <X size={16} className="text-gray-400" />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-gray-100 border border-gray-200 text-xs text-gray-500 font-mono hover:bg-gray-200 transition-colors cursor-pointer select-none"
              title="Close search"
            >
              ESC
            </button>
          )}
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-[60vh] overflow-y-auto">
          {query.length < 2 && !loading && (
            <div className="px-4 py-8 text-center text-gray-400 text-sm">
              Type at least 2 characters to search...
              <div className="mt-3 flex flex-wrap justify-center gap-2">
                {['Fee defaulters', 'Grade 5', 'Admit student', 'Collect payment'].map(tag => (
                  <button
                    key={tag}
                    onClick={() => setQuery(tag)}
                    className="px-3 py-1.5 rounded-full bg-gray-50 text-gray-600 text-xs hover:bg-gray-100 transition-colors"
                    type="button"
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>
          )}

          {results.students.length > 0 && (
            <div className="py-2">
              <div className="px-4 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">Students</div>
              {results.students.map((student, idx) => {
                const globalIdx = idx
                const isSelected = globalIdx === selectedIndex
                return (
                  <button
                    key={student.id}
                    onClick={() => handleSelect({ type: 'student', data: student })}
                    className={cn(
                      'w-full flex items-center gap-3 px-4 py-3 text-left transition-colors',
                      isSelected ? 'bg-[var(--brand-primary-light)]' : 'hover:bg-gray-50'
                    )}
                    type="button"
                  >
                    <div className={cn(
                      'h-9 w-9 rounded-full flex items-center justify-center text-sm font-medium flex-shrink-0',
                      isSelected ? 'bg-[var(--brand-primary)] text-white' : 'bg-blue-50 text-blue-600'
                    )}>
                      {student.photo ? (
                        <img src={student.photo} alt="" className="h-9 w-9 rounded-full object-cover" />
                      ) : (
                        <User size={16} />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate">
                        <HighlightMatch text={student.get_full_name || `${student.first_name} ${student.last_name}`} query={query} />
                      </div>
                      <div className="text-xs text-gray-500 truncate">
                        {student.admission_number} · {student.classroom?.name || 'No class'}
                        {student.primary_guardian?.phone && ` · ${student.primary_guardian.phone}`}
                      </div>
                    </div>
                    <ArrowRight size={14} className={cn('text-gray-400 flex-shrink-0', isSelected && 'text-[var(--brand-primary)]')} />
                  </button>
                )
              })}
            </div>
          )}

          {results.staff.length > 0 && (
            <div className="py-2 border-t border-gray-50">
              <div className="px-4 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">Staff</div>
              {results.staff.map((staff, idx) => {
                const globalIdx = results.students.length + idx
                const isSelected = globalIdx === selectedIndex
                return (
                  <button
                    key={staff.id}
                    onClick={() => handleSelect({ type: 'staff', data: staff })}
                    className={cn(
                      'w-full flex items-center gap-3 px-4 py-3 text-left transition-colors',
                      isSelected ? 'bg-[var(--brand-primary-light)]' : 'hover:bg-gray-50'
                    )}
                    type="button"
                  >
                    <div className={cn(
                      'h-9 w-9 rounded-full flex items-center justify-center text-sm font-medium flex-shrink-0',
                      isSelected ? 'bg-[var(--brand-primary)] text-white' : 'bg-purple-50 text-purple-600'
                    )}>
                      <User size={16} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate">
                        <HighlightMatch text={staff.get_full_name || `${staff.first_name} ${staff.last_name}`} query={query} />
                      </div>
                      <div className="text-xs text-gray-500 truncate capitalize">
                        {staff.role} {staff.phone && `· ${staff.phone}`}
                      </div>
                    </div>
                    <ArrowRight size={14} className={cn('text-gray-400 flex-shrink-0', isSelected && 'text-[var(--brand-primary)]')} />
                  </button>
                )
              })}
            </div>
          )}

          {results.actions.length > 0 && (
            <div className="py-2 border-t border-gray-50">
              <div className="px-4 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">Pages & Actions</div>
              {results.actions.map((action, idx) => {
                const globalIdx = results.students.length + results.staff.length + idx
                const isSelected = globalIdx === selectedIndex
                const Icon = action.icon
                return (
                  <button
                    key={action.id}
                    onClick={() => handleSelect({ type: 'action', data: action })}
                    className={cn(
                      'w-full flex items-center gap-3 px-4 py-3 text-left transition-colors',
                      isSelected ? 'bg-[var(--brand-primary-light)]' : 'hover:bg-gray-50'
                    )}
                    type="button"
                  >
                    <div className={cn(
                      'h-9 w-9 rounded-lg flex items-center justify-center flex-shrink-0',
                      isSelected ? 'bg-[var(--brand-primary)] text-white' : 'bg-gray-100 text-gray-500'
                    )}>
                      <Icon size={16} />
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-medium text-gray-900">
                        <HighlightMatch text={action.label} query={query} />
                      </div>
                      <div className="text-xs text-gray-500">Jump to page</div>
                    </div>
                    <ChevronRight size={14} className={cn('text-gray-400 flex-shrink-0', isSelected && 'text-[var(--brand-primary)]')} />
                  </button>
                )
              })}
            </div>
          )}

          {showEmpty && (
            <div className="px-4 py-8 text-center">
              <Search size={32} className="mx-auto text-gray-300 mb-2" />
              <p className="text-sm text-gray-500">No results found for "{query}"</p>
              <p className="text-xs text-gray-400 mt-1">Try a different name, ID, or page name</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2.5 bg-gray-50 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1"><kbd className="px-1.5 py-0.5 rounded bg-white border border-gray-200 font-mono">↑</kbd><kbd className="px-1.5 py-0.5 rounded bg-white border border-gray-200 font-mono">↓</kbd> to navigate</span>
            <span className="flex items-center gap-1"><kbd className="px-1.5 py-0.5 rounded bg-white border border-gray-200 font-mono">↵</kbd> to select</span>
          </div>
          <span>{allItems.length} results</span>
        </div>
      </div>
    </div>
  )
}