import { Fragment, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { communicationApi } from '@/api/communication'
import { Button, Card, EmptyState, Select, Spinner } from '@/components/ui'
import { EmptyTableRow } from '@/pages/academics/shared'
import { MessageStatusBadge, listFromResponse } from './shared'

export default function MessageLogsPage() {
  const location = useLocation()
  const [logs, setLogs] = useState([])
  const [summary, setSummary] = useState({ total_messages: 0, by_status: [] })
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)
  const [filters, setFilters] = useState({
    channel: '',
    status: '',
    announcement: location.state?.announcementId || '',
  })

  const load = () => {
    setLoading(true)
    const params = {}
    if (filters.channel) params.channel = filters.channel
    if (filters.status) params.status = filters.status
    if (filters.announcement) params.announcement = filters.announcement

    Promise.all([
      communicationApi.getLogs(params),
      communicationApi.getLogSummary(),
    ]).then(([logsRes, summaryRes]) => {
      setLogs(listFromResponse(logsRes.data))
      setSummary(summaryRes.data)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filters.channel, filters.status, filters.announcement])

  const sent = (summary.by_status || []).find(s => s.status === 'sent')?.count || 0
  const delivered = (summary.by_status || []).find(s => s.status === 'delivered')?.count || 0
  const failed = (summary.by_status || []).find(s => s.status === 'failed')?.count || 0
  const rate = summary.total_messages
    ? Math.round(((sent + delivered) / summary.total_messages) * 100)
    : 0

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900">Message History</h1>
        <p className="mt-1 text-sm text-gray-500">Full audit trail of all sent messages</p>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          { label: 'Total', value: summary.total_messages },
          { label: 'Sent', value: sent },
          { label: 'Delivered', value: delivered },
          { label: 'Failed', value: failed },
          { label: 'Delivery Rate', value: `${rate}%` },
        ].map(s => (
          <Card key={s.label} className="p-4 text-center">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className="text-lg font-bold text-gray-900">{s.value}</p>
          </Card>
        ))}
      </div>

      <Card className="mb-4 flex flex-wrap gap-4 p-4">
        <Select label="Channel" value={filters.channel} onChange={e => setFilters(p => ({ ...p, channel: e.target.value }))}>
          <option value="">All channels</option>
          <option value="sms">SMS</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="email">Email</option>
          <option value="inapp">In-App</option>
        </Select>
        <Select label="Status" value={filters.status} onChange={e => setFilters(p => ({ ...p, status: e.target.value }))}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="sent">Sent</option>
          <option value="delivered">Delivered</option>
          <option value="read">Read</option>
          <option value="failed">Failed</option>
        </Select>
      </Card>

      <Card className="overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-16"><Spinner /></div>
        ) : logs.length === 0 ? (
          <EmptyState title="No message logs" description="Messages will appear here once sent." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-100 bg-gray-50 text-left text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">Recipient</th>
                  <th className="px-4 py-3">Channel</th>
                  <th className="px-4 py-3">Message</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Sent At</th>
                  <th className="px-4 py-3">Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {logs.map(log => (
                  <Fragment key={log.id}>
                    <tr
                      className="cursor-pointer hover:bg-gray-50"
                      onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900">{log.recipient_name || '—'}</p>
                        <p className="text-xs text-gray-400">{log.recipient_phone || log.recipient_email}</p>
                      </td>
                      <td className="px-4 py-3 capitalize">{log.channel === 'inapp' ? 'In-App' : log.channel}</td>
                      <td className="max-w-xs truncate px-4 py-3 text-gray-600">{log.message_body}</td>
                      <td className="px-4 py-3">
                        <span title={log.failure_reason || ''}>
                          <MessageStatusBadge status={log.status} />
                        </span>
                      </td>
                      <td className="px-4 py-3">{log.sent_at ? new Date(log.sent_at).toLocaleString() : '—'}</td>
                      <td className="px-4 py-3">{log.provider_cost || '—'}</td>
                    </tr>
                    {expanded === log.id && (
                      <tr>
                        <td colSpan={6} className="bg-gray-50 px-4 py-4">
                          <p className="mb-2 text-xs font-medium uppercase text-gray-500">Full Message</p>
                          <p className="whitespace-pre-wrap text-sm text-gray-700">{log.message_body}</p>
                          <div className="mt-3 flex flex-wrap gap-4 text-xs text-gray-500">
                            {log.sent_at && <span>Sent: {new Date(log.sent_at).toLocaleString()}</span>}
                            {log.delivered_at && <span>Delivered: {new Date(log.delivered_at).toLocaleString()}</span>}
                            {log.read_at && <span>Read: {new Date(log.read_at).toLocaleString()}</span>}
                            {log.failure_reason && <span className="text-red-600">Error: {log.failure_reason}</span>}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {!logs.length && <EmptyTableRow colSpan={6} message="No logs found" />}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
