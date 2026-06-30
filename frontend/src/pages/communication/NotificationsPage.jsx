import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { communicationApi } from '@/api/communication'
import { Button, Card, EmptyState, Select, Spinner } from '@/components/ui'
import { formatRelativeTime, listFromResponse, NotificationTypeIcon } from './shared'

export default function NotificationsPage() {
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [typeFilter, setTypeFilter] = useState('')
  const [readFilter, setReadFilter] = useState('')

  const load = () => {
    setLoading(true)
    const params = {}
    if (typeFilter) params.type = typeFilter
    if (readFilter !== '') params.is_read = readFilter
    communicationApi.getNotifications(params).then(r => {
      setNotifications(listFromResponse(r.data))
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [typeFilter, readFilter])

  const handleMarkAll = async () => {
    await communicationApi.markAllRead()
    load()
  }

  const handleClick = async (n) => {
    if (!n.is_read) {
      await communicationApi.markRead([n.id])
    }
    if (n.action_url) navigate(n.action_url)
    else load()
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Notifications</h1>
          <p className="mt-1 text-sm text-gray-500">Your notification center</p>
        </div>
        <Button variant="secondary" onClick={handleMarkAll}>Mark all read</Button>
      </div>

      <Card className="mb-4 flex flex-wrap gap-4 p-4">
        <Select label="Type" value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
          <option value="">All types</option>
          <option value="fee_reminder">Fee Reminder</option>
          <option value="attendance">Attendance</option>
          <option value="report_card">Report Card</option>
          <option value="announcement">Announcement</option>
          <option value="exam">Examination</option>
          <option value="system">System</option>
        </Select>
        <Select label="Status" value={readFilter} onChange={e => setReadFilter(e.target.value)}>
          <option value="">All</option>
          <option value="false">Unread</option>
          <option value="true">Read</option>
        </Select>
      </Card>

      {loading ? (
        <div className="flex justify-center py-16"><Spinner /></div>
      ) : notifications.length === 0 ? (
        <EmptyState title="You're all caught up ✓" description="No notifications to show." />
      ) : (
        <div className="space-y-2">
          {notifications.map(n => (
            <button
              key={n.id}
              type="button"
              onClick={() => handleClick(n)}
              className={`flex w-full items-start gap-4 rounded-lg border p-4 text-left transition-colors ${
                n.is_read ? 'border-gray-100 bg-white' : 'border-[var(--brand-primary-ring)] bg-[var(--brand-primary-light)]'
              }`}
            >
              <NotificationTypeIcon type={n.type} />
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-medium text-gray-900">{n.title}</p>
                  <span className="shrink-0 text-xs text-gray-400">{formatRelativeTime(n.created_at)}</span>
                </div>
                <p className="mt-1 text-sm text-gray-600">{n.body}</p>
                {n.action_url && (
                  <Link to={n.action_url} className="mt-2 inline-block text-xs text-[var(--brand-primary)] hover:underline" onClick={e => e.stopPropagation()}>
                    View details →
                  </Link>
                )}
              </div>
              {!n.is_read && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[var(--brand-primary)]" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
