import { Button, Input, Select } from '@/components/ui'

const DAYS = [
  { value: 1, label: 'Monday' },
  { value: 2, label: 'Tuesday' },
  { value: 3, label: 'Wednesday' },
  { value: 4, label: 'Thursday' },
  { value: 5, label: 'Friday' },
  { value: 6, label: 'Saturday' },
  { value: 7, label: 'Sunday' },
]

const ROOM_TYPES = [
  { value: 'classroom', label: 'Classroom' },
  { value: 'lab', label: 'Lab' },
  { value: 'hall', label: 'Hall' },
  { value: 'library', label: 'Library' },
  { value: 'field', label: 'Field' },
  { value: 'other', label: 'Other' },
]

const TIME_PREFERENCES = [
  { value: 'none', label: 'No preference' },
  { value: 'prefer_morning', label: 'Prefer morning (soft)' },
  { value: 'strong_morning', label: 'Strongly prefer morning' },
  { value: 'prefer_afternoon', label: 'Prefer afternoon (soft)' },
]

// "HH:MM:SS" -> "HH:MM" for compact display.
const shortTime = (t) => (t || '').slice(0, 5)

export default function RuleModal({
  draft,
  ruleModalKey,
  subjects,
  templates,
  periods,
  onClose,
  onSave,
  setRuleDrafts,
  saving = false,
  error = '',
}) {
  if (!draft) return null

  const subject = subjects.find((s) => s.id === draft.subject)
  const bandLabel = draft.stream ? `${draft.grade_band} ${draft.stream}` : draft.grade_band

  // Multiple bell schedule templates can exist (e.g. Primary vs Junior Secondary),
  // so periods sharing the same day/order across templates need distinguishing —
  // but only when there's actually more than one template in play, to avoid the
  // redundant "Master Monday P1" noise that made every checkbox unreadable before.
  const templateIds = new Set(periods.map((p) => p.schedule_template))
  const showTemplateName = templateIds.size > 1

  const nonBreakPeriods = periods.filter((p) => !p.is_break)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <h3 className="mb-4 text-lg font-semibold text-gray-900">
          {subject?.name || 'Subject'} — {bandLabel}
        </h3>

        {error && (
          <p className="mb-4 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Periods per week</label>
            <Input
              type="number"
              min={0}
              max={20}
              value={draft.periods_per_week}
              onChange={(e) =>
                setRuleDrafts((prev) => ({
                  ...prev,
                  [ruleModalKey]: { ...prev[ruleModalKey], periods_per_week: parseInt(e.target.value) || 0 },
                }))
              }
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Requires Room</label>
            <Select
              value={draft.requires_room_type || ''}
              onChange={(e) =>
                setRuleDrafts((prev) => ({
                  ...prev,
                  [ruleModalKey]: { ...prev[ruleModalKey], requires_room_type: e.target.value || null },
                }))
              }
            >
              <option value="">None (home classroom)</option>
              {ROOM_TYPES.filter((t) => t.value !== 'classroom').map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Time Preference</label>
            <Select
              value={draft.time_preference || 'none'}
              onChange={(e) =>
                setRuleDrafts((prev) => ({
                  ...prev,
                  [ruleModalKey]: { ...prev[ruleModalKey], time_preference: e.target.value },
                }))
              }
            >
              {TIME_PREFERENCES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </Select>
            <p className="mt-1 text-xs text-gray-400">
              A soft nudge for the generator — it will still use an afternoon/morning slot rather than fail to schedule this subject.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300"
                checked={draft.requires_double}
                onChange={(e) =>
                  setRuleDrafts((prev) => ({
                    ...prev,
                    [ruleModalKey]: { ...prev[ruleModalKey], requires_double: e.target.checked },
                  }))
                }
              />
              Requires double lesson
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300"
                checked={draft.is_hard_excluded}
                onChange={(e) =>
                  setRuleDrafts((prev) => ({
                    ...prev,
                    [ruleModalKey]: { ...prev[ruleModalKey], is_hard_excluded: e.target.checked },
                  }))
                }
              />
              Hard excluded periods
            </label>
          </div>
        </div>

        {nonBreakPeriods.length > 0 && (
          <div className="mt-4">
            <label className="mb-2 block text-sm font-medium text-gray-700">Excluded Periods</label>
            <div className="max-h-72 space-y-3 overflow-y-auto rounded-md border border-gray-100 p-3">
              {DAYS.map((day) => {
                const dayPeriods = nonBreakPeriods
                  .filter((p) => p.day_of_week === day.value)
                  .sort((a, b) => a.order - b.order)
                if (dayPeriods.length === 0) return null
                return (
                  <div key={day.value}>
                    <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                      {day.label}
                    </p>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                      {dayPeriods.map((p) => {
                        const template = templates.find((t) => t.id === p.schedule_template)
                        const timeLabel = `${shortTime(p.start_time)}–${shortTime(p.end_time)}`
                        const fullLabel = showTemplateName
                          ? `${template?.name || ''} · ${day.label} P${p.order} · ${timeLabel}`
                          : `${day.label} P${p.order} · ${timeLabel}`
                        const checked = draft.excluded_periods.includes(p.id)
                        return (
                          <label
                            key={p.id}
                            title={fullLabel}
                            className="flex cursor-pointer items-center gap-2 rounded-md border border-gray-100 p-2 text-sm text-gray-700 hover:bg-gray-50"
                          >
                            <input
                              type="checkbox"
                              className="h-4 w-4 shrink-0 rounded border-gray-300"
                              checked={checked}
                              onChange={(e) => {
                                const next = e.target.checked
                                  ? [...draft.excluded_periods, p.id]
                                  : draft.excluded_periods.filter((id) => id !== p.id)
                                setRuleDrafts((prev) => ({
                                  ...prev,
                                  [ruleModalKey]: { ...prev[ruleModalKey], excluded_periods: next },
                                }))
                              }}
                            />
                            <span className="truncate">
                              P{p.order}{showTemplateName ? ` (${template?.name || ''})` : ''} · {timeLabel}
                            </span>
                          </label>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={onSave} loading={saving}>Save Rule</Button>
        </div>
      </div>
    </div>
  )
}