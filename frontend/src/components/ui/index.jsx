import { cn } from '@/lib/utils'

export { default as Badge } from './Badge'
export { default as Avatar } from './Avatar'
export { default as Spinner } from './Spinner'
export { default as EmptyState } from './EmptyState'
export { default as PageHeader } from './PageHeader'
export { default as Card } from './Card'
export { default as Input } from './Input'
export { default as Select } from './Select'
export { default as Button } from './Button'

export function Skeleton({ className }) {
	return (
		<div className={cn('animate-pulse bg-gray-200 rounded', className)} />
	)
}

export function TableSkeleton({ rows = 5, columns = 5 }) {
	return (
		<div className="divide-y divide-gray-50">
			{Array.from({ length: rows }).map((_, rowIndex) => (
				<div key={rowIndex} className="flex items-center gap-4 px-4 py-3">
					{Array.from({ length: columns }).map((_, columnIndex) => (
						<Skeleton
							key={columnIndex}
							className={cn('h-4', columnIndex === 0 ? 'w-32' : 'w-20')}
						/>
					))}
				</div>
			))}
		</div>
	)
}

export function CardSkeleton() {
	return (
		<div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
			<Skeleton className="h-4 w-1/3" />
			<Skeleton className="h-8 w-1/2" />
			<Skeleton className="h-3 w-2/3" />
		</div>
	)
}