import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calendar, DollarSign, GraduationCap, Bell, ChevronRight, Plus, Trash2, X } from 'lucide-react'
import { Card, Button, Input, Select } from '@/components/ui'
import { dashboardApi } from '@/api/dashboard'

const TYPE_ICON = {
  fee: DollarSign,
  exam: GraduationCap,
  report_card: GraduationCap,
  event: Bell,
  meeting: Bell,
  holiday: Calendar,
  deadline: DollarSign,
  other: Calendar,
}

const CATEGORY_OPTIONS = [
  { value: 'event', label: 'School Event' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'holiday', label: 'Holiday / Closure' },
  { value: 'deadline', label: 'Deadline' },
  { value: 'other', label: 'Other' },
]

export default function UpcomingEvents() {
  const navigate = useNavigate()
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [addOpen, setAddOpen] = useState(false)
  const [form, setForm] = useState({ title: '', date: '', category: 'event' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    dashboardApi.getUpcomingEvents()
      .then(({ data }) => setEvents(data))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const getDaysUntil = (date) => {
    const diff = Math.ceil((new Date(date) - new Date(new Date().toDateString())) / (1000 * 60 * 60 * 24))
    if (diff === 0) return 'Today'
    if (diff === 1) return 'Tomorrow'
    if (diff < 0) return `${Math.abs(diff)} days ago`
    return `${diff} days`
  }

  const getUrgency = (date) => {
    const diff = Math.ceil((new Date(date) - new Date()) / (1000 * 60 * 60 * 24))
    if (diff <= 3) return 'text-red-600 font-semibold'
    if (diff <= 7) return 'text-yellow-600 font-medium'
    return 'text-gray-500'
  }

  const submitEvent = async (e) => {
    e.preventDefault()
    if (!form.title.trim() || !form.date) return
    setSaving(true)
    setError('')
    try {
      await dashboardApi.createSchoolEvent(form)
      setForm({ title: '', date: '', category: 'event' })
      setAddOpen(false)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add event.')
    } finally {
      setSaving(false)
    }
  }

  const removeEvent = async (id) => {
    // ids look like "manual-<pk>" for SchoolEvent rows, "fee-due-...",
    // "exam-...", "report-cards-..." for auto-derived ones. Only manual
    // events are deletable from here.
    const pk = id.startsWith('manual-') ? id.replace('manual-', '') : null
    if (!pk) return
    await dashboardApi.deleteSchoolEvent(pk)
    setEvents(prev => prev.filter(e => e.id !== id))
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-[var(--brand-primary-light)] flex items-center justify-center">
            <Calendar size={20} className="text-[var(--brand-primary)]" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Upcoming Events</h3>
            <p className="text-sm text-gray-500">Key dates and deadlines</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setAddOpen(v => !v)}
          className="flex items-center gap-1 rounded-lg border border-gray-200 px-2.5 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
        >
          {addOpen ? <X size={14} /> : <Plus size={14} />}
          {addOpen ? 'Cancel' : 'Add Event'}
        </button>
      </div>

      {addOpen && (
        <form onSubmit={submitEvent} className="mb-4 space-y-3 rounded-lg border border-gray-100 bg-gray-50 p-3">
          {error && <p className="text-xs text-red-600">{error}</p>}
          <Input
            placeholder="Event title, e.g. Parent-Teacher Meeting"
            value={form.title}
            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
          />
          <div className="flex gap-2">
            <Input
              type="date"
              value={form.date}
              onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
              className="flex-1"
            />
            <Select
              value={form.category}
              onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
              className="flex-1"
            >
              {CATEGORY_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </Select>
          </div>
          <Button type="submit" size="sm" loading={saving}>Add Event</Button>
        </form>
      )}

      {loading ? (
        <p className="py-6 text-center text-sm text-gray-400">Loading events...</p>
      ) : events.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-400">No upcoming events in the next 60 days.</p>
      ) : (
        <div className="space-y-3">
          {events.map((event) => {
            const Icon = TYPE_ICON[event.type] || Calendar
            const isManual = event.source === 'manual'
            return (
              <div
                key={event.id}
                onClick={() => event.action && navigate(event.action)}
                className={`flex items-center gap-4 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors group ${event.action ? 'cursor-pointer' : ''}`}
              >
                <div className={`h-10 w-10 rounded-lg flex items-center justify-center flex-shrink-0 ${event.color}`}>
                  <Icon size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 group-hover:text-[var(--brand-primary)]">{event.title}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {new Date(event.date).toLocaleDateString('en-KE', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                  </p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className={`text-sm ${getUrgency(event.date)}`}>{getDaysUntil(event.date)}</p>
                </div>
                {isManual ? (
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); removeEvent(event.id) }}
                    className="flex-shrink-0 p-1 text-gray-300 opacity-0 group-hover:opacity-100 hover:text-red-500 transition-all"
                  >
                    <Trash2 size={14} />
                  </button>
                ) : (
                  event.action && <ChevronRight size={16} className="text-gray-300 group-hover:text-[var(--brand-primary)] transition-colors flex-shrink-0" />
                )}
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}