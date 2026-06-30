import { cn } from '@/lib/utils'

export default function Spinner({ className = '', ...props }) {
  return (
    <svg className={cn('animate-spin text-[var(--brand-primary)]', className)} viewBox="0 0 24 24" {...props}>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  )
}
