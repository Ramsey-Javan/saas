import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MessageSquare, CheckCircle, XCircle, Bell, Plus } from 'lucide-react'
import { communicationApi } from '@/api/communication'
import { Button, Card, Spinner, EmptyState } from '@/components/ui'
import { StatCard } from '@/pages/academics/shared'
import {
  ChannelBadges, formatRelativeTime, listFromResponse, recipientLabel,
} from './shared'

export default function CommunicationDashboard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState({ total_messages: 0, by_channel: [], by_status: [] })
  const [announcements, setAnnouncements] = useState([])
  const [scheduled, setScheduled] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    Promise.all([
      communicationApi.getLogSummary(),
      communicationApi.getAnnouncements({ ordering: '-created_at', page_size: 10 }),
      communicationApi.getAnnouncements({ status: 'scheduled', page_size: 5 }),
      communicationApi.getUnreadCount(),
    ]).then(([summaryRes, recentRes, scheduledRes, unreadRes]) => {
      setSummary(summaryRes.data)
      setAnnouncements(listFromResponse(recentRes.data).filter(a => ['sent', 'sending'].includes(a.status)))
      setScheduled(listFromResponse(scheduledRes.data))
      setUnreadCount(unreadRes.data?.count || 0)
    }).catch(console.error).finally(() => setLoading(false))
  }, [])

  const delivered = (summary.by_status || []).find(s => s.status === 'delivered')?.count
    || (summary.by_status || []).find(s => s.status === 'sent')?.count || 0
  const failed = (summary.by_status || []).find(s => s.status === 'failed')?.count || 0

  const handleCancel = async (id) => {
    await communicationApi.cancelAnnouncement(id)
    setScheduled(prev => prev.filter(a => a.id !== id))
  }

  if (loading) {
    return <div className="flex justify-center py-20"><Spinner /></div>
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Communication</h1>
          <p className="mt-1 text-sm text-gray-500">Messages, announcements, and notifications</p>
        </div>
        <Button onClick={() => navigate('/communication/compose')}>
          <Plus size={16} className="mr-1" /> New Message
        </Button>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={MessageSquare} label="Messages Sent" value={summary.total_messages} tone="blue" />
        <StatCard icon={CheckCircle} label="Delivered" value={delivered} tone="green" />
        <StatCard icon={XCircle} label="Failed" value={failed} tone="red" />
        <StatCard icon={Bell} label="Unread Notifications" value={unreadCount} tone="purple" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Recent Announcements</h2>
            <Button variant="secondary" size="sm" onClick={() => navigate('/communication/logs')}>View logs</Button>
          </div>
          {announcements.length === 0 ? (
            <EmptyState title="No announcements yet" description="Send your first message to get started." />
          ) : (
            <div className="space-y-3">
              {announcements.slice(0, 10).map(a => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => navigate('/communication/logs', { state: { announcementId: a.id } })}
                  className="w-full rounded-lg border border-gray-100 p-3 text-left hover:bg-gray-50"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium text-gray-900">{a.title}</p>
                    <span className="text-xs text-gray-400">{formatRelativeTime(a.sent_at || a.created_at)}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <ChannelBadges channels={a.channels} />
                    <span className="text-xs text-gray-500">{recipientLabel(a)}</span>
                    {a.delivery_rate != null && (
                      <span className="text-xs font-medium text-green-600">{a.delivery_rate}% delivered</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </Card>

        <div className="space-y-6">
          <Card className="p-5">
            <h2 className="mb-4 font-semibold text-gray-900">Channel Breakdown</h2>
            {(summary.by_channel || []).length === 0 ? (
              <p className="text-sm text-gray-400">No messages sent yet</p>
            ) : (
              <div className="space-y-3">
                {summary.by_channel.map(row => {
                  const pct = summary.total_messages
                    ? Math.round((row.count / summary.total_messages) * 100)
                    : 0
                  return (
                    <div key={row.channel}>
                      <div className="mb-1 flex justify-between text-sm">
                        <span className="capitalize text-gray-700">{row.channel === 'inapp' ? 'In-App' : row.channel}</span>
                        <span className="font-medium text-gray-900">{row.count}</span>
                      </div>
                      <div className="h-2 rounded-full bg-gray-100">
                        <div className="h-2 rounded-full bg-blue-600" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>

          <Card className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">Scheduled Messages</h2>
              <Button variant="secondary" size="sm" onClick={() => navigate('/communication/scheduled')}>View all</Button>
            </div>
            {scheduled.length === 0 ? (
              <p className="text-sm text-gray-400">No upcoming scheduled messages</p>
            ) : (
              <div className="space-y-3">
                {scheduled.map(a => (
                  <div key={a.id} className="flex items-center justify-between rounded-lg border border-gray-100 p-3">
                    <div>
                      <p className="font-medium text-gray-900">{a.title}</p>
                      <p className="text-xs text-gray-500">
                        {a.scheduled_at ? new Date(a.scheduled_at).toLocaleString() : 'Recurring'} · {recipientLabel(a)}
                      </p>
                    </div>
                    <Button variant="secondary" size="sm" onClick={() => handleCancel(a.id)}>Cancel</Button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
