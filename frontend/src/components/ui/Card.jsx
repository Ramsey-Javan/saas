import { cn } from '@/lib/utils'

export default function Card({ children, className = '', ...props }) {
  return (
    <div className={cn('bg-white rounded-xl border border-gray-100 shadow-sm', className)} {...props}>
      {children}
    </div>
  )
}