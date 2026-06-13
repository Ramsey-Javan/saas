import { Badge } from '@/components/ui'

export const CHANNELS = [
  { id: 'sms', label: 'SMS', cost: 'KES 1.00/msg' },
  { id: 'whatsapp', label: 'WhatsApp', cost: 'KES 0.80/msg' },
  { id: 'email', label: 'Email', cost: 'Free' },
  { id: 'inapp', label: 'In-App', cost: 'Free' },
]

export const RECIPIENT_TYPES = [
  { value: 'class', label: 'Class' },
  { value: 'grade', label: 'Grade' },
  { value: 'school', label: 'School' },
  { value: 'individual', label: 'Individual' },
  { value: 'teachers', label: 'Teachers' },
  { value: 'staff', label: 'Staff' },
]

export const GRADE_LEVELS = [
  'PP1', 'PP2', 'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4',
  'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8', 'Grade 9',
]

export const TEMPLATE_CATEGORIES = [
  { value: 'fee', label: 'Fee Related' },
  { value: 'attendance', label: 'Attendance' },
  { value: 'academic', label: 'Academic' },
  { value: 'general', label: 'General' },
  { value: 'exam', label: 'Examination' },
]

export const TEMPLATE_VARIABLES = [
  'student_name', 'guardian_name', 'school_name', 'balance',
  'term', 'class_name', 'date', 'admission_number',
  'subject_name', 'attendance_percentage',
]

export const listFromResponse = (data) => data?.results || (Array.isArray(data) ? data : [])

export function formatRelativeTime(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

export function extractVariables(text) {
  const matches = text?.match(/\{\{(\w+)\}\}/g) || []
  return [...new Set(matches.map(m => m.replace(/\{\{|\}\}/g, '')))]
}

export function ChannelBadges({ channels }) {
  if (!channels?.length) return null
  const colors = {
    sms: 'bg-blue-100 text-blue-700',
    whatsapp: 'bg-green-100 text-green-700',
    email: 'bg-purple-100 text-purple-700',
    inapp: 'bg-orange-100 text-orange-700',
  }
  return (
    <div className="flex flex-wrap gap-1">
      {channels.map(ch => (
        <span key={ch} className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${colors[ch] || 'bg-gray-100 text-gray-700'}`}>
          {ch === 'inapp' ? 'In-App' : ch}
        </span>
      ))}
    </div>
  )
}

export function MessageStatusBadge({ status }) {
  const styles = {
    pending: 'bg-gray-100 text-gray-700',
    sent: 'bg-blue-100 text-blue-700',
    delivered: 'bg-green-100 text-green-700',
    read: 'bg-teal-100 text-teal-700',
    failed: 'bg-red-100 text-red-700',
    draft: 'bg-gray-100 text-gray-600',
    scheduled: 'bg-yellow-100 text-yellow-700',
    sending: 'bg-blue-100 text-blue-700',
    cancelled: 'bg-gray-100 text-gray-500',
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${styles[status] || styles.pending}`}>
      {status}
    </span>
  )
}

export function NotificationTypeIcon({ type }) {
  const config = {
    fee_reminder: { emoji: '💰', color: 'text-yellow-600 bg-yellow-50' },
    attendance: { emoji: '📋', color: 'text-red-600 bg-red-50' },
    report_card: { emoji: '📊', color: 'text-blue-600 bg-blue-50' },
    announcement: { emoji: '📢', color: 'text-purple-600 bg-purple-50' },
    exam: { emoji: '📝', color: 'text-orange-600 bg-orange-50' },
    system: { emoji: '⚙️', color: 'text-gray-600 bg-gray-50' },
  }
  const c = config[type] || config.system
  return (
    <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${c.color}`}>
      <span>{c.emoji}</span>
    </div>
  )
}

export function recipientLabel(announcement) {
  const type = announcement.recipient_type
  if (type === 'class') return announcement.recipient_class_name || 'Class'
  if (type === 'grade') return announcement.recipient_grade || 'Grade'
  if (type === 'individual') return 'Individual'
  if (type === 'school') return 'Entire School'
  if (type === 'teachers') return 'All Teachers'
  if (type === 'staff') return 'All Staff'
  return type
}
