import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { communicationApi } from '@/api/communication'
import { formatRelativeTime, listFromResponse, NotificationTypeIcon } from '@/pages/communication/shared'

export default function NotificationBell() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(false)
  const panelRef = useRef(null)

  const fetchUnreadCount = () => {
    communicationApi.getUnreadCount()
      .then(r => setUnreadCount(r.data?.count || 0))
      .catch(() => setUnreadCount(0))
  }

  const fetchNotifications = () => {
    setLoading(true)
    communicationApi.getNotifications({ page_size: 15 })
      .then(r => setNotifications(listFromResponse(r.data)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchUnreadCount()
    const interval = setInterval(fetchUnreadCount, 60000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (open) fetchNotifications()
  }, [open])

  useEffect(() => {
    const handleClick = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const handleMarkAll = async (e) => {
    e.stopPropagation()
    await communicationApi.markAllRead()
    fetchUnreadCount()
    fetchNotifications()
  }

  const handleNotificationClick = async (n) => {
    if (!n.is_read) {
      await communicationApi.markRead([n.id])
      fetchUnreadCount()
    }
    setOpen(false)
    if (n.action_url) navigate(n.action_url)
  }

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="relative rounded-lg p-2 text-gray-600 hover:bg-gray-100"
        aria-label="Notifications"
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-80 rounded-xl border border-gray-100 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
            <h3 className="font-semibold text-gray-900">Notifications</h3>
            {unreadCount > 0 && (
              <button type="button" onClick={handleMarkAll} className="text-xs text-[var(--brand-primary)] hover:underline">
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <p className="px-4 py-8 text-center text-sm text-gray-400">Loading…</p>
            ) : notifications.length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-gray-500">You&apos;re all caught up ✓</p>
            ) : (
              notifications.map(n => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleNotificationClick(n)}
                  className={`flex w-full items-start gap-3 border-b border-gray-50 px-4 py-3 text-left hover:bg-gray-50 ${
                    !n.is_read ? 'bg-[var(--brand-primary-light)]' : ''
                  }`}
                >
                  <NotificationTypeIcon type={n.type} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-gray-900">{n.title}</p>
                    <p className="truncate text-xs text-gray-500">{n.body}</p>
                    <p className="mt-0.5 text-xs text-gray-400">{formatRelativeTime(n.created_at)}</p>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="border-t border-gray-100 px-4 py-2">
            <Link
              to="/communication/notifications"
              onClick={() => setOpen(false)}
              className="block text-center text-xs text-[var(--brand-primary)] hover:underline"
            >
              View all notifications
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
