import { X } from 'lucide-react'
import { Badge, Button, Card } from '@/components/ui'

export const TERMS = [
  { value: 'term1', label: 'Term 1' },
  { value: 'term2', label: 'Term 2' },
  { value: 'term3', label: 'Term 3' },
]

export const LEVEL_COLORS = {
  EE: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200', hex: '#16a34a' },
  ME: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', hex: '#2563eb' },
  AE: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200', hex: '#ea580c' },
  BE: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', hex: '#dc2626' },
}

export const ATTENDANCE_STATUS = {
  P: { label: 'Present', className: 'bg-green-100 text-green-700 border-green-200' },
  A: { label: 'Absent', className: 'bg-red-100 text-red-700 border-red-200' },
  L: { label: 'Late', className: 'bg-yellow-100 text-yellow-700 border-yellow-200' },
  E: { label: 'Excused', className: 'bg-gray-100 text-gray-700 border-gray-200' },
}

export const listFromResponse = (data) => data?.results || (Array.isArray(data) ? data : [])
export const countFromResponse = (data) => data?.count ?? listFromResponse(data).length
export const thisYear = () => new Date().getFullYear()
export const todayISO = () => new Date().toISOString().slice(0, 10)
export const termLabel = (term) => TERMS.find(t => t.value === term)?.label || term || 'Term'
export const classroomLabel = (classroom) => (
  classroom ? `${classroom.name || classroom.classroom_name || ''}${classroom.stream ? ` ${classroom.stream}` : ''}`.trim() : ''
)
export const userName = (user) => [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.email || user?.username || 'Teacher'

export function Modal({ title, children, onClose, footer }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700">
            <X size={18} />
          </button>
        </div>
        <div className="p-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-gray-100 px-5 py-4">{footer}</div>}
      </div>
    </div>
  )
}

export function StatCard({ icon: Icon, label, value, tone = 'blue' }) {
  const tones = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    orange: 'bg-orange-50 text-orange-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
  }
  return (
    <Card className="p-4 flex items-center gap-4">
      {Icon && <div className={`rounded-lg p-3 ${tones[tone] || tones.blue}`}><Icon size={20} /></div>}
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-xl font-bold text-gray-900">{value}</p>
      </div>
    </Card>
  )
}

export function LevelBadge({ level }) {
  if (!level) return <Badge label="Empty" variant="default" />
  const color = LEVEL_COLORS[level]
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${color?.bg || 'bg-gray-100'} ${color?.text || 'text-gray-700'}`}>
      {level}
    </span>
  )
}

export function StatusBadge({ status }) {
  const variant = status === 'published' || status === 'active' ? 'active' : status === 'draft' ? 'pending' : status
  return <Badge label={status || 'draft'} variant={variant} className="capitalize" />
}

export function EmptyTableRow({ colSpan, message }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-8 text-center text-sm text-gray-400">{message}</td>
    </tr>
  )
}

export function openBlobInNewTab(blob, type = 'application/pdf') {
  const url = window.URL.createObjectURL(new Blob([blob], { type }))
  window.open(url, '_blank', 'noopener,noreferrer')
  setTimeout(() => window.URL.revokeObjectURL(url), 60000)
}

export function downloadTextFile(filename, text, type = 'text/csv;charset=utf-8;') {
  const url = window.URL.createObjectURL(new Blob([text], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
}

export function downloadRowsAsCSV(filename, rows) {
  const csv = rows.map(row => row.map(cell => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',')).join('\n')
  downloadTextFile(filename, csv)
}

export function FormActions({ saving, onCancel, submitLabel = 'Save' }) {
  return (
    <>
      <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
      <Button type="submit" loading={saving}>{submitLabel}</Button>
    </>
  )
}
