import { useEffect, useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronUp, XCircle } from 'lucide-react'
import { Button } from '@/components/ui'

const PAGE_SIZE = 10

/**
 * Paginated, tabbed renderer for the readiness payload returned by
 * timetablingApi.getReadiness(): { ready, errors: [{message}], warnings: [{message}] }.
 *
 * - Errors and warnings get their own tabs (hidden when one side is empty,
 *   so a fully-ready school never sees pointless tabs).
 * - Only PAGE_SIZE items render at a time, with Show more / Show all /
 *   Show less — readiness for a big school can easily be hundreds of lines
 *   (e.g. one error per unassigned subject per classroom).
 * - The visible count resets whenever the underlying errors/warnings change
 *   (re-running the check, switching term/year) so you always start at the top.
 */
export default function ReadinessList({ errors = [], warnings = [], showTabs = true }) {
  const errorCount = errors.length
  const warningCount = warnings.length

  const [activeTab, setActiveTab] = useState('errors')
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  // If only one category has items, land on that tab.
  const effectiveTab = errorCount > 0 && warningCount > 0
    ? activeTab
    : errorCount > 0
      ? 'errors'
      : 'warnings'

  const items = effectiveTab === 'errors' ? errors : warnings

  useEffect(() => {
    setVisibleCount(PAGE_SIZE)
  }, [errors, warnings])

  if (errorCount === 0 && warningCount === 0) return null

  const visibleItems = items.slice(0, visibleCount)
  const hiddenCount = items.length - visibleItems.length

  return (
    <div className="space-y-2">
      {showTabs && errorCount > 0 && warningCount > 0 && (
        <div className="flex overflow-hidden rounded-md border border-gray-200 text-sm">
          <button
            type="button"
            onClick={() => {
              setActiveTab('errors')
              setVisibleCount(PAGE_SIZE)
            }}
            className={`flex flex-1 items-center justify-center gap-1.5 px-3 py-1.5 font-medium ${
              effectiveTab === 'errors'
                ? 'bg-red-600 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            <XCircle size={14} /> Errors ({errorCount})
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveTab('warnings')
              setVisibleCount(PAGE_SIZE)
            }}
            className={`flex flex-1 items-center justify-center gap-1.5 border-l border-gray-200 px-3 py-1.5 font-medium ${
              effectiveTab === 'warnings'
                ? 'bg-amber-500 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            <AlertTriangle size={14} /> Warnings ({warningCount})
          </button>
        </div>
      )}

      <div className="space-y-2 text-sm">
        {visibleItems.map((item, index) => (
          effectiveTab === 'errors' ? (
            <p key={`e-${index}`} className="text-red-700">{item.message}</p>
          ) : (
            <p key={`w-${index}`} className="text-amber-700">{item.message}</p>
          )
        ))}
      </div>

      {(hiddenCount > 0 || visibleCount > PAGE_SIZE) && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {hiddenCount > 0 && (
            <Button size="sm" variant="secondary" onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}>
              <ChevronDown size={14} className="mr-1" />
              Show more ({hiddenCount} remaining)
            </Button>
          )}
          {hiddenCount > PAGE_SIZE && (
            <Button size="sm" variant="secondary" onClick={() => setVisibleCount(items.length)}>
              Show all {items.length}
            </Button>
          )}
          {visibleCount > PAGE_SIZE && (
            <Button size="sm" variant="secondary" onClick={() => setVisibleCount(PAGE_SIZE)}>
              <ChevronUp size={14} className="mr-1" />
              Show less
            </Button>
          )}
        </div>
      )}
    </div>
  )
}