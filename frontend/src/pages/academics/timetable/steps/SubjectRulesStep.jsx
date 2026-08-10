import React, { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, Save } from 'lucide-react'
import { Button, Card } from '@/components/ui'
import { timetablingApi } from '@/api/timetabling'
import RuleModal from '../components/RuleModal'

const PHASE_ORDER = ['pp', 'lower_primary', 'upper_primary', 'jss', 'sss', 'all']
const PHASE_LABELS = {
  pp: 'Pre-Primary',
  lower_primary: 'Lower Primary (Grade 1-3)',
  upper_primary: 'Upper Primary (Grade 4-6)',
  jss: 'Junior Secondary (Grade 7-9)',
  sss: 'Senior Secondary',
  all: 'All Levels',
}

const PHASE_GRADES = {
  pp: [],
  lower_primary: ['Grade 1', 'Grade 2', 'Grade 3'],
  upper_primary: ['Grade 4', 'Grade 5', 'Grade 6'],
  jss: ['Grade 7', 'Grade 8', 'Grade 9'],
  sss: ['Grade 10', 'Grade 11', 'Grade 12'],
  all: [],
}

function defaultPeriods(subjectName) {
  const name = (subjectName || '').toLowerCase()
  const core = ['math', 'english', 'kiswahili', 'science', 'biology', 'chemistry', 'physics']
  if (core.some((c) => name.includes(c))) return 5
  return 3
}

function sortGrades(grades) {
  return [...grades].sort((a, b) => {
    const na = parseInt(a.replace(/\D/g, '')) || 0
    const nb = parseInt(b.replace(/\D/g, '')) || 0
    return na - nb
  })
}

function extractErrorMessage(err, fallback) {
  const data = err?.response?.data
  if (!data) return err?.message || fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const firstValue = Object.values(data)[0]
  if (Array.isArray(firstValue)) return firstValue[0]
  if (typeof firstValue === 'string') return firstValue
  return fallback
}

// A "column" is a specific grade, optionally narrowed to one stream. Grades where
// every classroom shares a blank stream get a single whole-grade column, matching
// the previous behaviour. Grades with real streams (e.g. West/East) get one column
// per stream, so a rule can target "Grade 3 West" specifically.
function buildColumns(classrooms) {
  const streamsByGrade = new Map()
  classrooms.forEach((c) => {
    if (!c.grade_level) return
    if (!streamsByGrade.has(c.grade_level)) streamsByGrade.set(c.grade_level, new Set())
    streamsByGrade.get(c.grade_level).add(c.stream || '')
  })

  const columns = []
  sortGrades(Array.from(streamsByGrade.keys())).forEach((grade) => {
    const streams = Array.from(streamsByGrade.get(grade))
    const realStreams = streams.filter(Boolean).sort()
    if (realStreams.length > 0) {
      realStreams.forEach((stream) => {
        columns.push({ grade_band: grade, stream, label: `${grade} ${stream}` })
      })
    } else {
      columns.push({ grade_band: grade, stream: '', label: grade })
    }
  })
  return columns
}

// Buckets a grade string into a curriculum phase. Used to place a subject in the
// right section of the grid based on the grades it actually applies to, rather
// than trusting the (sometimes stale/unset) curriculum_phase field on its own.
function phaseForGrade(grade) {
  if (!grade) return 'all'
  if (grade.startsWith('PP')) return 'pp'
  const n = parseInt(grade.replace(/\D/g, '')) || 0
  if (n >= 1 && n <= 3) return 'lower_primary'
  if (n >= 4 && n <= 6) return 'upper_primary'
  if (n >= 7 && n <= 9) return 'jss'
  if (n >= 10) return 'sss'
  return 'all'
}

export default function SubjectRulesStep({
  subjects,
  classrooms,
  templates,
  periods,
  subjectRules,
  setSubjectRules,
  onBack,
  onNext,
}) {
  const [saving, setSaving] = useState(false)
  const [ruleModalOpen, setRuleModalOpen] = useState(false)
  const [ruleModalKey, setRuleModalKey] = useState(null)
  const [ruleError, setRuleError] = useState('')
  const [pageError, setPageError] = useState('')

  const columns = useMemo(() => buildColumns(classrooms), [classrooms])

  // Prefer the explicit grade_levels list (set per-subject in the Curriculum admin
  // page, e.g. Computer Studies -> ["Grade 7", "Grade 8", "Grade 9"]) since it's
  // far more precise than the 5-bucket curriculum_phase. Only fall back to the
  // phase bucket for subjects that were never given an explicit grade_levels list,
  // so nothing regresses for subjects that only ever relied on curriculum_phase.
  const isCellApplicable = (subject, gradeBand) => {
    if (Array.isArray(subject.grade_levels) && subject.grade_levels.length > 0) {
      return subject.grade_levels.includes(gradeBand)
    }
    const phase = subject.curriculum_phase || 'all'
    if (phase === 'all') return true
    const allowed = PHASE_GRADES[phase] || []
    return allowed.includes(gradeBand)
  }

  // A subject only earns a row in the grid if at least one of this school's actual
  // columns applies to it. Without this, a PP-only subject at a school with no
  // PP1/PP2 classrooms would render as a row of nothing but gray dashes forever.
  const visibleSubjects = useMemo(
    () => subjects.filter((sub) => columns.some((col) => isCellApplicable(sub, col.grade_band))),
    [subjects, columns]
  )

  // CRITICAL: only ever build a draft — and therefore only ever submit a rule —
  // for a (subject, column) pair that is actually applicable.
  const [ruleDrafts, setRuleDrafts] = useState(() => {
    const drafts = {}
    visibleSubjects.forEach((sub) => {
      columns.forEach((col) => {
        if (!isCellApplicable(sub, col.grade_band)) return
        const key = `${sub.id}-${col.grade_band}-${col.stream}`
        const existing = subjectRules.find((r) => {
          const rid = typeof r.subject === 'object' ? r.subject.id : r.subject
          return rid === sub.id && r.grade_band === col.grade_band && (r.stream || '') === col.stream
        })
        drafts[key] = {
          subject: sub.id,
          grade_band: col.grade_band,
          stream: col.stream,
          periods_per_week: existing ? existing.periods_per_week : defaultPeriods(sub.name),
          requires_double: existing ? existing.requires_double : false,
          requires_room_type: existing ? existing.requires_room_type || '' : '',
          excluded_periods: existing ? existing.excluded_periods || [] : [],
          is_hard_excluded: existing ? existing.is_hard_excluded : true,
          time_preference: existing ? (existing.time_preference || 'none') : 'none',
          is_active: true,
          _existingId: existing ? existing.id : null,
        }
      })
    })
    return drafts
  })

  // Groups by the phase implied by each subject's own grade_levels (falling back
  // to curriculum_phase only when grade_levels is empty), so a subject actually
  // lands under the section it applies to instead of wherever a stale phase field
  // happens to point.
  const groupedSubjects = useMemo(() => {
    const groups = {}
    PHASE_ORDER.forEach((p) => (groups[p] = []))
    visibleSubjects.forEach((sub) => {
      const phase = Array.isArray(sub.grade_levels) && sub.grade_levels.length > 0
        ? phaseForGrade(sub.grade_levels[0])
        : (sub.curriculum_phase || 'all')
      const target = groups[phase] || groups.all
      target.push(sub)
    })
    return groups
  }, [visibleSubjects])

  const openRuleModal = (subjectId, gradeBand, stream) => {
    setRuleError('')
    setRuleModalKey(`${subjectId}-${gradeBand}-${stream}`)
    setRuleModalOpen(true)
  }

  // Returns true on success, false on failure — the caller uses this to decide
  // whether to close the modal. On failure the modal stays open with the error
  // message visible instead of silently vanishing.
  const saveRuleDraft = async (key) => {
    const draft = ruleDrafts[key]
    if (!draft) return false
    setSaving(true)
    setRuleError('')
    try {
      const payload = {
        subject: draft.subject,
        grade_band: draft.grade_band,
        stream: draft.stream || '',
        periods_per_week: parseInt(draft.periods_per_week) || 0,
        requires_double: draft.requires_double,
        requires_room_type: draft.requires_room_type || null,
        excluded_periods: draft.excluded_periods,
        is_hard_excluded: draft.is_hard_excluded,
        time_preference: draft.time_preference || 'none',
        is_active: true,
      }
      if (draft._existingId) {
        await timetablingApi.updateSubjectRule(draft._existingId, payload)
      } else {
        await timetablingApi.createSubjectRule(payload)
      }
      const { data } = await timetablingApi.getSubjectRules({})
      const rules = data.results || data
      setSubjectRules(rules)
      setRuleDrafts((prev) => {
        const next = { ...prev }
        const updated = rules.find((r) => {
          const rid = typeof r.subject === 'object' ? r.subject.id : r.subject
          return rid === draft.subject && r.grade_band === draft.grade_band && (r.stream || '') === (draft.stream || '')
        })
        if (updated) next[key]._existingId = updated.id
        return next
      })
      return true
    } catch (err) {
      setRuleError(extractErrorMessage(err, 'Failed to save this rule. Please try again.'))
      return false
    } finally {
      setSaving(false)
    }
  }

  // Submits every current draft — which, thanks to the fix above, only ever
  // contains applicable (subject, column) pairs.
  const saveAllRules = async () => {
    setSaving(true)
    setPageError('')
    try {
      const payload = Object.values(ruleDrafts).map((draft) => ({
        subject: draft.subject,
        grade_band: draft.grade_band,
        stream: draft.stream || '',
        periods_per_week: parseInt(draft.periods_per_week) || 0,
        requires_double: draft.requires_double,
        requires_room_type: draft.requires_room_type || null,
        excluded_periods: draft.excluded_periods,
        is_hard_excluded: draft.is_hard_excluded,
        time_preference: draft.time_preference || 'none',
        is_active: true,
      }))
      await timetablingApi.bulkUpsertSubjectRules(payload)
      const { data } = await timetablingApi.getSubjectRules({})
      const rules = data.results || data
      setSubjectRules(rules)
      setRuleDrafts((prev) => {
        const next = { ...prev }
        Object.keys(next).forEach((key) => {
          const draft = next[key]
          const updated = rules.find((r) => {
            const rid = typeof r.subject === 'object' ? r.subject.id : r.subject
            return rid === draft.subject && r.grade_band === draft.grade_band && (r.stream || '') === (draft.stream || '')
          })
          if (updated) next[key]._existingId = updated.id
        })
        return next
      })
    } catch (err) {
      setPageError(extractErrorMessage(err, 'Failed to save all rules. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  const currentRuleDraft = ruleModalKey ? ruleDrafts[ruleModalKey] : null

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-gray-900">Subject Rules</h3>
            <p className="text-sm text-gray-500">
              Set periods per week for each subject and grade (split by stream where your school has streams).
              Gray cells = not applicable for this subject. Subjects with no applicable classes at this school are hidden.
            </p>
          </div>
          <Button size="sm" onClick={saveAllRules} loading={saving}>
            <Save size={14} className="mr-1" /> Save All
          </Button>
        </div>

        {pageError && (
          <p className="mb-4 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
            {pageError}
          </p>
        )}

        {visibleSubjects.length === 0 || columns.length === 0 ? (
          <p className="text-sm text-red-600">
            You need subjects and classrooms with grade levels before configuring rules.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="sticky left-0 z-10 min-w-[200px] border-r border-gray-100 bg-white px-2 py-2 text-left font-medium text-gray-700">
                    Subject
                  </th>
                  {columns.map((col) => (
                    <th key={`${col.grade_band}-${col.stream}`} className="px-2 py-2 text-center font-medium text-gray-700 whitespace-nowrap">
                      {col.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {PHASE_ORDER.map((phase) => {
                  const phaseSubs = groupedSubjects[phase] || []
                  if (phaseSubs.length === 0) return null
                  return (
                    <React.Fragment key={phase}>
                      <tr>
                        <td colSpan={columns.length + 1} className="sticky left-0 z-10 bg-gray-50 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
                          {PHASE_LABELS[phase]}
                        </td>
                      </tr>
                      {phaseSubs.map((sub) => (
                        <tr key={sub.id} className="divide-y divide-gray-100">
                          <td className="sticky left-0 z-10 border-r border-gray-100 bg-white px-2 py-2 font-medium text-gray-900">
                            {sub.name}
                          </td>
                          {columns.map((col) => {
                            const key = `${sub.id}-${col.grade_band}-${col.stream}`
                            const draft = ruleDrafts[key]
                            const applicable = isCellApplicable(sub, col.grade_band)
                            return (
                              <td key={`${col.grade_band}-${col.stream}`} className="px-2 py-2 text-center">
                                {applicable ? (
                                  <button
                                    onClick={() => openRuleModal(sub.id, col.grade_band, col.stream)}
                                    className={`inline-flex h-8 w-16 items-center justify-center rounded-md border text-sm font-medium transition-colors ${
                                      draft?.periods_per_week > 0
                                        ? 'border-teal-200 bg-teal-50 text-teal-800 hover:bg-teal-100'
                                        : 'border-gray-200 bg-white text-gray-400 hover:bg-gray-50'
                                    }`}
                                  >
                                    {draft?.periods_per_week || 0}
                                  </button>
                                ) : (
                                  <span className="inline-flex h-8 w-16 items-center justify-center rounded-md border border-gray-100 bg-gray-100 text-gray-300 text-sm">
                                    —
                                  </span>
                                )}
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {ruleModalOpen && currentRuleDraft && (
        <RuleModal
          draft={currentRuleDraft}
          ruleModalKey={ruleModalKey}
          subjects={subjects}
          templates={templates}
          periods={periods}
          saving={saving}
          error={ruleError}
          onClose={() => setRuleModalOpen(false)}
          onSave={async () => {
            const ok = await saveRuleDraft(ruleModalKey)
            if (ok) setRuleModalOpen(false)
          }}
          setRuleDrafts={setRuleDrafts}
        />
      )}

      <div className="flex justify-between">
        <Button variant="secondary" onClick={onBack}>
          <ChevronLeft size={16} className="mr-1" /> Back
        </Button>
        <Button onClick={onNext}>
          Next: Teachers <ChevronRight size={16} className="ml-1" />
        </Button>
      </div>
    </div>
  )
}