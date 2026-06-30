import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { communicationApi } from '@/api/communication'
import { Button, Card, EmptyState, Spinner } from '@/components/ui'
import { EmptyTableRow } from '@/pages/academics/shared'
import { ChannelBadges, MessageStatusBadge, listFromResponse, recipientLabel } from './shared'

export default function ScheduledMessagesPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('upcoming')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    let params = {}
    if (tab === 'upcoming') params = { status: 'scheduled', is_recurring: false }
    else if (tab === 'recurring') params = { is_recurring: true }
    else params = { status: 'sent' }

    communicationApi.getAnnouncements(params).then(r => {
      setItems(listFromResponse(r.data))
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [tab])

  const handleCancel = async (id) => {
    await communicationApi.cancelAnnouncement(id)
    load()
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900">Scheduled Messages</h1>
        <p className="mt-1 text-sm text-gray-500">Manage upcoming, recurring, and past announcements</p>
      </div>

      <div className="mb-4 flex gap-2">
        {[
          { id: 'upcoming', label: 'Upcoming' },
          { id: 'recurring', label: 'Recurring' },
          { id: 'past', label: 'Past' },
        ].map(t => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`rounded-lg px-4 py-2 text-sm font-medium ${tab === t.id ? 'bg-[var(--brand-primary)] text-white' : 'bg-white border border-gray-200 text-gray-600'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <Card className="overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-16"><Spinner /></div>
        ) : items.length === 0 ? (
          <EmptyState title="No messages" description="Nothing scheduled in this category." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-100 bg-gray-50 text-left text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">Title</th>
                  {tab === 'recurring' ? (
                    <>
                      <th className="px-4 py-3">Frequency</th>
                      <th className="px-4 py-3">Next Run</th>
                    </>
                  ) : tab === 'past' ? (
                    <>
                      <th className="px-4 py-3">Sent At</th>
                      <th className="px-4 py-3">Delivered</th>
                      <th className="px-4 py-3">Failed</th>
                      <th className="px-4 py-3">Rate</th>
                    </>
                  ) : (
                    <>
                      <th className="px-4 py-3">Channels</th>
                      <th className="px-4 py-3">Recipients</th>
                      <th className="px-4 py-3">Scheduled For</th>
                      <th className="px-4 py-3">Status</th>
                    </>
                  )}
                  {tab !== 'past' && <th className="px-4 py-3">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map(a => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{a.title}</td>
                    {tab === 'recurring' ? (
                      <>
                        <td className="px-4 py-3 capitalize">{a.recurrence_rule?.frequency || '—'}</td>
                        <td className="px-4 py-3">{a.next_run_at ? new Date(a.next_run_at).toLocaleString() : '—'}</td>
                      </>
                    ) : tab === 'past' ? (
                      <>
                        <td className="px-4 py-3">{a.sent_at ? new Date(a.sent_at).toLocaleString() : '—'}</td>
                        <td className="px-4 py-3">{a.delivered_count}</td>
                        <td className="px-4 py-3">{a.failed_count}</td>
                        <td className="px-4 py-3">{a.delivery_rate}%</td>
                      </>
                    ) : (
                      <>
                        <td className="px-4 py-3"><ChannelBadges channels={a.channels} /></td>
                        <td className="px-4 py-3">{recipientLabel(a)}</td>
                        <td className="px-4 py-3">{a.scheduled_at ? new Date(a.scheduled_at).toLocaleString() : '—'}</td>
                        <td className="px-4 py-3"><MessageStatusBadge status={a.status} /></td>
                      </>
                    )}
                    {tab !== 'past' && (
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          {tab === 'upcoming' && (
                            <>
                              <Button size="sm" variant="secondary" onClick={() => navigate('/communication/compose')}>Edit</Button>
                              <Button size="sm" variant="danger" onClick={() => handleCancel(a.id)}>Cancel</Button>
                            </>
                          )}
                          {tab === 'recurring' && (
                            <>
                              <Button size="sm" variant="danger" onClick={() => handleCancel(a.id)}>Cancel</Button>
                            </>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
                {!items.length && <EmptyTableRow colSpan={7} message="No records" />}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
