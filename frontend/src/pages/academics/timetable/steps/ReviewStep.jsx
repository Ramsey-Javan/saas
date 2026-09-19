import { useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, ChevronDown, ChevronUp, CheckCircle2, XCircle } from 'lucide-react'
import { Button, Card } from '@/components/ui'
import { timetablingApi } from '@/api/timetabling'

const TERM_LABELS = { term1: 'Term 1', term2: 'Term 2', term3: 'Term 3' }
const PAGE_SIZE = 10

const CODE_LABELS = {
  missing_teacher_assignment: 'Missing teacher assignments',
  missing_subject_rule: 'Missing subject rules',
  missing_room: 'Missing rooms',
  teacher_oversubscribed: 'Teachers assigned more periods than they have',
  oversubscribed_schedule: 'Classes needing more periods than scheduled',
  missing_schedule_template: 'Classes missing a bell schedule',
}

function labelForCode(code) {
  return CODE_LABELS[code] || code.replace(/_/g, ' ')
}

// Groups a flat error/warning list by `code`. For missing_teacher_assignment
// specifically, also sub-groups by classroom so "Grade 7 West" shows once
// with all its missing subjects listed together, instead of one line per
// subject.
function groupItems(items) {
  const byCode = {}
  for (const item of items) {
    const code = item.code || 'other'
    if (!byCode[code]) byCode[code] = []
    byCode[code].push(item)
  }

  return Object.entries(byCode).map(([code, codeItems]) => {
    if (code === 'missing_teacher_assignment') {
      const byClassroom = {}
      for (const item of codeItems) {
        const key = item.classroom_name || 'Unknown class'
        if (!byClassroom[key]) byClassroom[key] = []
        byClassroom[key].push(item.subject_name || 'Unknown subject')
      }
      return {
        code,
        label: labelForCode(code),
        count: codeItems.length,
        rows: Object.entries(byClassroom).map(([classroomName, subjectNames]) => ({
          key: classroomName,
          text: `${classroomName} — ${subjectNames.join(', ')}`,
        })),
      }
    }
    return {
      code,
      label: labelForCode(code),
      count: codeItems.length,
      rows: codeItems.map((item, i) => ({
        key: `${code}-${i}`,
        text: item.message,
      })),
    }
  })
}

function IssueGroup({ group, tone, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  // Rows are paginated independently per group: a group with 40 missing
  // assignments renders 10 at a time, not all 40.
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  // Re-running the check produces new rows — collapse back to the first page
  // so stale expansion state doesn't linger across checks.
  useEffect(() => {
    setVisibleCount(PAGE_SIZE)
  }, [group.rows.length])

  const visibleRows = group.rows.slice(0, visibleCount)
  const hiddenCount = group.rows.length - visibleRows.length

  const toneClasses = tone === 'error'
    ? { border: 'border-red-100', bg: 'bg-red-50', text: 'text-red-700', badge: 'bg-red-100 text-red-700' }
    : { border: 'border-amber-100', bg: 'bg-amber-50', text: 'text-amber-800', badge: 'bg-amber-100 text-amber-800' }

  return (
    <div className={`overflow-hidden rounded-md border ${toneClasses.border}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium ${toneClasses.bg} ${toneClasses.text}`}
      >
        <span className="flex items-center gap-2">
          {group.label}
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${toneClasses.badge}`}>
            {group.count}
          </span>
        </span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <>
          <div className="divide-y divide-white/60">
            {visibleRows.map((row) => (
              <div key={row.key} className={`px-3 py-2 text-sm ${toneClasses.text}`}>
                {row.text}
              </div>
            ))}
          </div>
          {(hiddenCount > 0 || visibleCount > PAGE_SIZE) && (
            <div className={`flex flex-wrap gap-2 border-t px-3 py-2 ${toneClasses.border}`}>
              {hiddenCount > 0 && (
                <button
                  type="button"
                  onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
                  className={`inline-flex items-center gap-1 text-xs font-medium underline underline-offset-2 ${toneClasses.text}`}
                >
                  <ChevronDown size={12} /> Show more ({hiddenCount} remaining)
                </button>
              )}
              {hiddenCount > PAGE_SIZE && (
                <button
                  type="button"
                  onClick={() => setVisibleCount(group.rows.length)}
                  className={`text-xs font-medium underline underline-offset-2 ${toneClasses.text}`}
                >
                  Show all {group.rows.length}
                </button>
              )}
              {visibleCount > PAGE_SIZE && (
                <button
                  type="button"
                  onClick={() => setVisibleCount(PAGE_SIZE)}
                  className={`inline-flex items-center gap-1 text-xs font-medium underline underline-offset-2 ${toneClasses.text}`}
                >
                  <ChevronUp size={12} /> Show less
                </button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function ReviewStep({ readiness, setReadiness, term, academicYear, onBack, onComplete }) {
  const [saving, setSaving] = useState(false)

  const runReadiness = async () => {
    setSaving(true)
    try {
      const { data } = await timetablingApi.getReadiness({ term, academic_year: academicYear })
      setReadiness(data)
    } finally {
      setSaving(false)
    }
  }

  const errorGroups = useMemo(
    () => (readiness?.errors?.length ? groupItems(readiness.errors) : []),
    [readiness],
  )
  const warningGroups = useMemo(
    () => (readiness?.warnings?.length ? groupItems(readiness.warnings) : []),
    [readiness],
  )

  const errorCount = readiness?.errors?.length || 0
  const warningCount = readiness?.warnings?.length || 0

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-gray-900">Readiness Check</h3>
            <p className="text-xs text-gray-400">
              For {TERM_LABELS[term] || 'this term'} {academicYear}
            </p>
          </div>
          <Button size="sm" variant="secondary" onClick={runReadiness} loading={saving}>
            Run Check
          </Button>
        </div>

        {!readiness && (
          <p className="text-sm text-gray-500">Click "Run Check" to verify your timetable is ready to generate.</p>
        )}

        {readiness && (
          <div className="space-y-4">
            {readiness.ready ? (
              <div className="flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-700">
                <CheckCircle2 size={18} />
                <span className="font-medium">Ready to generate!</span>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                <span className="flex items-center gap-2">
                  <XCircle size={18} />
                  <span className="font-medium">Please fix the issues below before generating.</span>
                </span>
                <span className="flex shrink-0 gap-2 text-xs font-semibold">
                  <span className="rounded-full bg-red-100 px-2 py-0.5 text-red-700">{errorCount} errors</span>
                  {warningCount > 0 && (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-800">{warningCount} warnings</span>
                  )}
                </span>
              </div>
            )}

            {errorGroups.length > 0 && (
              <div className="space-y-2">
                {errorGroups.map((group) => (
                  <IssueGroup
                    key={group.code}
                    group={group}
                    tone="error"
                    defaultOpen={group.count <= 5}
                  />
                ))}
              </div>
            )}

            {warningGroups.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Warnings</p>
                {warningGroups.map((group) => (
                  <IssueGroup
                    key={group.code}
                    group={group}
                    tone="warning"
                    defaultOpen={group.count <= 5}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </Card>

      <div className="flex justify-between">
        <Button variant="secondary" onClick={onBack}>
          <ChevronLeft size={16} className="mr-1" /> Back
        </Button>
        <Button
          onClick={onComplete}
          disabled={!readiness?.ready}
          className={!readiness?.ready ? 'opacity-50 cursor-not-allowed' : ''}
        >
          Finish & Open Timetable <ChevronRight size={16} className="ml-1" />
        </Button>
      </div>
    </div>
  )
}
