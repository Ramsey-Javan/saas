import { cn } from '@/lib/utils'
import { Loader2 } from 'lucide-react'

export default function Button({ children, variant = 'primary', size = 'md', loading = false, className = '', ...props }) {
  const variants = {
    primary: 'bg-[var(--brand-primary)] text-white hover:bg-[var(--brand-primary-hover)]',
    secondary: 'bg-gray-100 text-gray-700 hover:bg-gray-200',
    danger: 'bg-red-600 text-white hover:bg-red-700',
  }
  const sizes = { sm: 'px-3 py-1.5 text-xs', md: 'px-4 py-2 text-sm', lg: 'px-6 py-3 text-base' }
  
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center font-medium rounded-lg transition-all disabled:opacity-60 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <Loader2 className="animate-spin mr-2" size={16} />}
      {children}
    </button>
  )
}
