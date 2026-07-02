import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { toastBus } from '@/lib/toastBus'

const ToastContext = createContext(null)

const TOAST_STYLES = {
  success: {
    icon: CheckCircle,
    bg: 'bg-green-50 border-green-200',
    iconColor: 'text-green-600',
    textColor: 'text-green-800',
  },
  error: {
    icon: XCircle,
    bg: 'bg-red-50 border-red-200',
    iconColor: 'text-red-600',
    textColor: 'text-red-800',
  },
  warning: {
    icon: AlertTriangle,
    bg: 'bg-yellow-50 border-yellow-200',
    iconColor: 'text-yellow-600',
    textColor: 'text-yellow-800',
  },
  info: {
    icon: Info,
    bg: 'bg-blue-50 border-blue-200',
    iconColor: 'text-[var(--brand-primary)]',
    textColor: 'text-blue-800',
  },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id))
  }, [])

  const show = useCallback((message, type = 'info', duration = 4000) => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev, { id, message, type }])
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration)
    }
    return id
  }, [dismiss])

  useEffect(() => toastBus.subscribe((message, type) => show(message, type)), [show])

  const toast = {
    success: (message, duration) => show(message, 'success', duration),
    error: (message, duration) => show(message, 'error', duration ?? 6000),
    warning: (message, duration) => show(message, 'warning', duration),
    info: (message, duration) => show(message, 'info', duration),
    dismiss,
  }

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-full sm:w-auto">
        {toasts.map((toastItem) => {
          const style = TOAST_STYLES[toastItem.type]
          const Icon = style.icon
          return (
            <div
              key={toastItem.id}
              className={cn(
                'flex items-start gap-3 px-4 py-3 rounded-lg border shadow-sm animate-in slide-in-from-top-2',
                style.bg
              )}
              role="alert"
            >
              <Icon size={18} className={cn('flex-shrink-0 mt-0.5', style.iconColor)} />
              <p className={cn('text-sm flex-1', style.textColor)}>{toastItem.message}</p>
              <button
                onClick={() => dismiss(toastItem.id)}
                className="text-gray-400 hover:text-gray-600 flex-shrink-0"
                aria-label="Dismiss notification"
                type="button"
              >
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return ctx
}