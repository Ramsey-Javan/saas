import { cn } from '@/lib/utils'

export default function Badge({ label, variant = 'default', className = '', ...props }) {
  const variants = {
    default: 'bg-gray-100 text-gray-700',
    active: 'bg-green-100 text-green-700',
    transferred: 'bg-blue-100 text-blue-700',
    graduated: 'bg-emerald-100 text-emerald-700',
    dropped: 'bg-red-100 text-red-700',
    inactive: 'bg-red-100 text-red-700',
    withdrawn: 'bg-red-100 text-red-700',
    pending: 'bg-yellow-100 text-yellow-700',
    M: 'bg-blue-100 text-blue-700',
    F: 'bg-pink-100 text-pink-700',
  }
  return (
    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', variants[variant] || variants.default, className)} {...props}>
      {label}
    </span>
  )
}
