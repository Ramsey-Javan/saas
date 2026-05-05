import { cn } from '@/lib/utils'

export default function Avatar({ name, photo, size = 'md', className = '' }) {
  const sizes = { sm: 'h-8 w-8 text-xs', md: 'h-10 w-10 text-sm', lg: 'h-12 w-12 text-base' }
  const initials = name?.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() || '?'
  
  return photo ? (
    <img src={photo} alt={name} className={cn('rounded-full object-cover', sizes[size], className)} />
  ) : (
    <div className={cn('rounded-full bg-gray-200 flex items-center justify-center font-medium text-gray-600', sizes[size], className)}>
      {initials}
    </div>
  )
}