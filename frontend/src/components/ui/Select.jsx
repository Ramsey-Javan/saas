import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

const Select = forwardRef(function Select({ label, error, className = '', children, ...props }, ref) {
  return (
    <div>
      {label && <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>}
      <select
        ref={ref}
        className={cn(
          'w-full px-3 py-2 rounded-lg border border-gray-200 text-sm outline-none focus:ring-2 focus:ring-[var(--brand-primary-ring)] focus:border-[var(--brand-primary)] bg-white',
          error && 'border-red-300 focus:ring-red-200',
          className
        )}
        {...props}
      >
        {children}
      </select>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
})

export default Select
