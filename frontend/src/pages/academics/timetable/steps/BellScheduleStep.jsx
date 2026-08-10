import { useMemo, useState } from 'react'
import { ChevronRight, Copy, Plus, Save, Trash2 } from 'lucide-react'
import { Button, Card, Input, Select } from '@/components/ui'
import { timetablingApi } from '@/api/timetabling'

const DAYS = [
  { value: 1, label: 'Monday' },
  { value: 2, label: 'Tuesday' },
  { value: 3, label: 'Wednesday' },
  { value: 4, label: 'Thursday' },
  { value: 5, label: 'Friday' },
  { value: 6, label: 'Saturday' },
  { value: 7, label: 'Sunday' },
]

const dayLabel = (value) => DAYS.find((d) => d.value === value)?.label || `Day ${value}`

// "HH:MM:SS" / "HH:MM" -> minutes since midnight, for comparing start/end times.
function toMinutes(t) {
  if (!t) return null
  const [h, m] = t.split(':').map(Number)
  if (Number.isNaN(h) || Number.isNaN(m)) return null
  return h * 60 + m
}

export default function BellScheduleStep({ templates, periods, setTemplates, setPeriods, onNext }) {
  const [templateName, setTemplateName] = useState('')
  const [periodRows, setPeriodRows] = useState([])
  const [saving, setSaving] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState(null)
  const [saveError, setSaveError] = useState('')

  const [copyPanelOpen, setCopyPanelOpen] = useState(false)
  const [copySourceDay, setCopySourceDay] = useState(1)
  const [copyTargetDays, setCopyTargetDays] = useState([])

  const daysInUse = useMemo(
    () => Array.from(new Set(periodRows.map((r) => r.day_of_week))).sort((a, b) => a - b),
    [periodRows]
  )

  // Display rows grouped/sorted by day then order, without changing the underlying
  // periodRows array indices — updatePeriodRow/removePeriodRow still address rows
  // by their real index in periodRows, so editing after a copy only ever touches
  // that one row.
  const sortedIndices = useMemo(
    () =>
      periodRows
        .map((_, i) => i)
        .sort((a, b) => {
          const rowA = periodRows[a]
          const rowB = periodRows[b]
          return rowA.day_of_week - rowB.day_of_week || rowA.order - rowB.order
        }),
    [periodRows]
  )

  const addPeriodRow = () => {
    const lastDay = periodRows.length ? periodRows[periodRows.length - 1].day_of_week : 1
    const sameDayCount = periodRows.filter((r) => r.day_of_week === lastDay).length
    setPeriodRows((prev) => [
      ...prev,
      { day_of_week: lastDay, order: sameDayCount + 1, start_time: '08:00', end_time: '08:40', is_break: false },
    ])
  }

  const updatePeriodRow = (idx, field, value) => {
    setPeriodRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r)))
  }

  const removePeriodRow = (idx) => {
    setPeriodRows((prev) => prev.filter((_, i) => i !== idx))
  }

  const toggleCopyTargetDay = (day) => {
    setCopyTargetDays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]))
  }

  const applyCopy = () => {
    const sourceRows = periodRows.filter((r) => r.day_of_week === copySourceDay)
    if (sourceRows.length === 0 || copyTargetDays.length === 0) return
    setPeriodRows((prev) => {
      const kept = prev.filter((r) => !copyTargetDays.includes(r.day_of_week))
      const copies = copyTargetDays.flatMap((day) => {
        const targetIdByOrder = new Map()
        prev.forEach((r) => {
          if (r.day_of_week === day && r.id != null) {
            targetIdByOrder.set(r.order, r.id)
          }
        })
        return sourceRows.map(({ id, ...row }) => ({
          ...row,
          day_of_week: day,
          id: targetIdByOrder.get(row.order) || undefined,
        }))
      })
      return [...kept, ...copies]
    })
    setCopyPanelOpen(false)
    setCopyTargetDays([])
  }

  // Catches the specific mistake of an end time typed before the start time
  // (e.g. 02:00 PM start with 02:40 AM end) — this silently produces a negative
  // duration for the solver, so it's worth stopping at save time rather than
  // letting it through and failing confusingly later.
  const findInvalidRow = () => {
    for (let i = 0; i < periodRows.length; i += 1) {
      const row = periodRows[i]
      const start = toMinutes(row.start_time)
      const end = toMinutes(row.end_time)
      if (start !== null && end !== null && end <= start) {
        return { index: i, row }
      }
    }
    return null
  }

  const saveTemplate = async () => {
    if (!templateName.trim() || periodRows.length === 0) return
    const invalid = findInvalidRow()
    if (invalid) {
      setSaveError(`${dayLabel(invalid.row.day_of_week)} P${invalid.row.order}: end time (${invalid.row.end_time}) must be after start time (${invalid.row.start_time}).`)
      return
    }
    setSaveError('')
    setSaving(true)
    try {
      const { data: temp } = await timetablingApi.createScheduleTemplate({ name: templateName.trim() })
      const createdPeriods = await Promise.all(
        periodRows.map((p) =>
          timetablingApi.createPeriod({
            schedule_template: temp.id,
            day_of_week: p.day_of_week,
            order: p.order,
            start_time: p.start_time,
            end_time: p.end_time,
            is_break: p.is_break,
          }).then((r) => r.data)
        )
      )
      setTemplateName('')
      setPeriodRows([])
      setPeriods((prev) => [...prev, ...createdPeriods])
      const { data: freshTemps } = await timetablingApi.getScheduleTemplates({})
      setTemplates(freshTemps.results || freshTemps)
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to save schedule.'
      setSaveError(msg)
    } finally {
      setSaving(false)
    }
  }

  const startEditTemplate = async (template) => {
    setEditingTemplate(template)
    setTemplateName(template.name)
    setSaveError('')
    try {
      const { data } = await timetablingApi.getPeriods({ schedule_template: template.id })
      const templatePeriods = Array.isArray(data) ? data : (data.results || [])
      setPeriodRows(
        templatePeriods.map((p) => ({
          id: p.id,
          day_of_week: p.day_of_week,
          order: p.order,
          start_time: p.start_time,
          end_time: p.end_time,
          is_break: p.is_break,
        }))
      )
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to load periods for editing.'
      setSaveError(msg)
    }
  }

  const updateTemplate = async () => {
    if (!editingTemplate || !templateName.trim()) return
    const invalid = findInvalidRow()
    if (invalid) {
      setSaveError(
        `${dayLabel(invalid.row.day_of_week)} P${invalid.row.order}: end time (${invalid.row.end_time}) must be after start time (${invalid.row.start_time}).`
      )
      return
    }
    setSaveError('')
    setSaving(true)
    try {
      await timetablingApi.updateScheduleTemplate(editingTemplate.id, {
        name: templateName.trim(),
      })

      const { data: updatedPeriods } = await timetablingApi.bulkUpdatePeriods({
        schedule_template: editingTemplate.id,
        periods: periodRows.map((p) => ({
          id: p.id || undefined,
          day_of_week: p.day_of_week,
          order: p.order,
          start_time: p.start_time,
          end_time: p.end_time,
          is_break: p.is_break,
        })),
      })

      setEditingTemplate(null)
      setTemplateName('')
      setPeriodRows([])

      // Replace every period for this template in global state with the
      // authoritative full list the backend just returned.
      setPeriods((prev) => {
        const others = prev.filter((p) => p.schedule_template !== editingTemplate.id)
        const fresh = Array.isArray(updatedPeriods) ? updatedPeriods : (updatedPeriods.results || [])
        return [...others, ...fresh]
      })

      const { data: freshTemps } = await timetablingApi.getScheduleTemplates({})
      setTemplates(freshTemps.results || freshTemps)
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        JSON.stringify(err?.response?.data) ||
        err?.message ||
        'Failed to update schedule. Please try again.'
      setSaveError(msg)
    } finally {
      setSaving(false)
    }
  }

  const deleteTemplate = async (id) => {
    if (!window.confirm('Delete this schedule and all its periods?')) return
    try {
      await timetablingApi.deleteScheduleTemplate(id)
      setTemplates((prev) => prev.filter((t) => t.id !== id))
      setPeriods((prev) => prev.filter((p) => p.schedule_template !== id))
      if (editingTemplate?.id === id) {
        setEditingTemplate(null)
        setTemplateName('')
        setPeriodRows([])
      }
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to delete schedule.'
      setSaveError(msg)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <h3 className="mb-4 text-base font-semibold text-gray-900">
          {editingTemplate ? 'Edit Bell Schedule' : 'Create a Bell Schedule'}
        </h3>
        <div className="mb-4">
          <Input
            label="Schedule Name (e.g. Primary, Junior Secondary)"
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            placeholder="Primary School Schedule"
          />
        </div>

        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm font-medium text-gray-700">Periods</span>
          <div className="flex gap-2">
            {daysInUse.length > 0 && (
              <Button size="sm" variant="secondary" onClick={() => setCopyPanelOpen((open) => !open)}>
                <Copy size={14} className="mr-1" /> Copy periods to other days
              </Button>
            )}
            <Button size="sm" variant="secondary" onClick={addPeriodRow}>
              <Plus size={14} className="mr-1" /> Add Period
            </Button>
          </div>
        </div>

        {copyPanelOpen && (
          <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 p-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Copy from</label>
                <Select value={copySourceDay} onChange={(e) => setCopySourceDay(parseInt(e.target.value))}>
                  {daysInUse.map((day) => (
                    <option key={day} value={day}>{dayLabel(day)}</option>
                  ))}
                </Select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Copy to</label>
                <div className="flex flex-wrap gap-2">
                  {DAYS.filter((d) => d.value !== copySourceDay).map((d) => (
                    <label
                      key={d.value}
                      className="flex cursor-pointer items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2 py-1 text-sm text-gray-700"
                    >
                      <input
                        type="checkbox"
                        className="h-3.5 w-3.5 rounded border-gray-300"
                        checked={copyTargetDays.includes(d.value)}
                        onChange={() => toggleCopyTargetDay(d.value)}
                      />
                      {d.label}
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <p className="mt-3 text-xs text-gray-500">
              Copies become independent rows you can edit or delete afterward — e.g. remove a period from
              just Thursday without affecting Monday or any other day. Copying to a day that already has
              periods replaces them.
            </p>
            <div className="mt-3 flex gap-2">
              <Button size="sm" onClick={applyCopy} disabled={copyTargetDays.length === 0}>Apply</Button>
              <Button size="sm" variant="secondary" onClick={() => { setCopyPanelOpen(false); setCopyTargetDays([]) }}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {periodRows.length === 0 && (
          <p className="rounded-lg border border-dashed border-gray-200 py-6 text-center text-sm text-gray-400">
            No periods added yet. Click "Add Period" to start.
          </p>
        )}

        {saveError && (
          <p className="mb-3 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
            {saveError}
          </p>
        )}

        {sortedIndices.map((idx) => {
          const row = periodRows[idx]
          return (
            <div key={idx} className="mb-2 grid grid-cols-12 items-end gap-2">
              <div className="col-span-3">
                <Select
                  label={idx === sortedIndices[0] ? 'Day' : ''}
                  value={row.day_of_week}
                  onChange={(e) => updatePeriodRow(idx, 'day_of_week', parseInt(e.target.value))}
                >
                  {DAYS.map((d) => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </Select>
              </div>
              <div className="col-span-2">
                <Input label={idx === sortedIndices[0] ? 'Order' : ''} type="number" min={1} value={row.order} onChange={(e) => updatePeriodRow(idx, 'order', parseInt(e.target.value) || 1)} />
              </div>
              <div className="col-span-2">
                <Input label={idx === sortedIndices[0] ? 'Start' : ''} type="time" value={row.start_time} onChange={(e) => updatePeriodRow(idx, 'start_time', e.target.value)} />
              </div>
              <div className="col-span-2">
                <Input label={idx === sortedIndices[0] ? 'End' : ''} type="time" value={row.end_time} onChange={(e) => updatePeriodRow(idx, 'end_time', e.target.value)} />
              </div>
              <div className="col-span-2 flex items-center pb-2">
                <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" className="h-4 w-4 rounded border-gray-300" checked={row.is_break} onChange={(e) => updatePeriodRow(idx, 'is_break', e.target.checked)} />
                  Break
                </label>
              </div>
              <div className="col-span-1 pb-2">
                <button onClick={() => removePeriodRow(idx)} className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600">
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          )
        })}

        <div className="mt-4 flex gap-2">
          {editingTemplate ? (
            <>
              <Button onClick={updateTemplate} loading={saving} disabled={!templateName.trim() || periodRows.length === 0}>
                <Save size={16} className="mr-1" /> Update Schedule
              </Button>
              <Button variant="secondary" onClick={() => { setEditingTemplate(null); setTemplateName(''); setPeriodRows([]); setSaveError('') }}>
                Cancel
              </Button>
            </>
          ) : (
            <Button onClick={saveTemplate} loading={saving} disabled={!templateName.trim() || periodRows.length === 0}>
              <Save size={16} className="mr-1" /> Save Schedule
            </Button>
          )}
        </div>
      </Card>

      {templates.length > 0 && (
        <Card className="p-5">
          <h3 className="mb-3 text-base font-semibold text-gray-900">Saved Schedules</h3>
          <div className="space-y-3">
            {templates.map((t) => (
              <div key={t.id} className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-4 py-3">
                <div>
                  <p className="font-medium text-gray-900">{t.name}</p>
                  <p className="text-xs text-gray-500">
                    {periods.filter((p) => p.schedule_template === t.id).length} periods configured
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => startEditTemplate(t)}>Edit</Button>
                  <button onClick={() => deleteTemplate(t.id)} className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600">
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="flex justify-end">
        <Button onClick={onNext} disabled={templates.length === 0}>
          Next: Rooms <ChevronRight size={16} className="ml-1" />
        </Button>
      </div>
    </div>
  )
}