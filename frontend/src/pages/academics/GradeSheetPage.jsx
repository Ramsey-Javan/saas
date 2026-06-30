import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Upload, Download } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { Button, Card, PageHeader, Spinner } from '@/components/ui'
import { LEVEL_COLORS, Modal, termLabel, thisYear, downloadRowsAsCSV } from './shared'

const LEVELS = ['EE', 'ME', 'AE', 'BE']

function GradeCell({ value, dirty, onChange }) {
  const [open, setOpen] = useState(false)
  const color = LEVEL_COLORS[value]
  return (
    <td className="relative min-w-[76px] border-r border-b border-gray-100 p-1">
      <button
        onClick={() => setOpen(v => !v)}
        className={`h-9 w-full rounded border text-xs font-semibold ${color?.bg || 'bg-gray-50'} ${color?.text || 'text-gray-400'} ${dirty ? 'ring-2 ring-[var(--brand-primary-ring)]' : ''}`}
      >
        {value || '—'}
      </button>
      {open && (
        <div className="absolute left-1 top-10 z-20 flex rounded-lg border border-gray-200 bg-white p-1 shadow-lg">
          {LEVELS.map(level => (
            <button key={level} onClick={() => { onChange(level); setOpen(false) }} className={`rounded px-2 py-1 text-xs font-semibold ${LEVEL_COLORS[level].bg} ${LEVEL_COLORS[level].text}`}>
              {level}
            </button>
          ))}
          <button onClick={() => { onChange(''); setOpen(false) }} className="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100">Clear</button>
        </div>
      )}
    </td>
  )
}

function ImportModal({ classroomId, onClose, onDone }) {
  const [file, setFile] = useState(null)
  const [saving, setSaving] = useState(false)
  const [search] = useSearchParams()
  const term = search.get('term') || 'term1'
  const year = search.get('year') || thisYear()

  const submit = async (event) => {
    event.preventDefault()
    const data = new FormData()
    data.append('file', file)
    data.append('classroom', classroomId)
    data.append('term', term)
    data.append('academic_year', year)
    setSaving(true)
    try {
      await academicsApi.importGradesCSV(data)
      onDone()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Import Grades CSV"
      onClose={onClose}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" form="sheet-import-form" loading={saving}>Import</Button></>}
    >
      <form id="sheet-import-form" onSubmit={submit}>
        <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" type="file" accept=".csv,text/csv" onChange={e => setFile(e.target.files?.[0] || null)} required />
      </form>
    </Modal>
  )
}

export default function GradeSheetPage() {
  const { classroomId, subjectId } = useParams()
  const [search] = useSearchParams()
  const term = search.get('term') || 'term1'
  const year = search.get('year') || thisYear()
  const [sheet, setSheet] = useState({ students: [], outcomes: [], grades: {} })
  const [classroom, setClassroom] = useState(null)
  const [subject, setSubject] = useState(null)
  const [attendance, setAttendance] = useState({})
  const [dirty, setDirty] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [importOpen, setImportOpen] = useState(false)

  const fetchSheet = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      // Fetch grade sheet first - this is the critical data
      const sheetRes = await academicsApi.getGradeSheet({ classroom: classroomId, subject: subjectId, term, academic_year: year })
      setSheet(sheetRes.data)

      // Fetch supplementary data independently - failures here shouldn't break the page
      try {
        const classroomRes = await studentsApi.getClassroom(classroomId)
        setClassroom(classroomRes.data)
      } catch (err) {
        console.warn('Failed to load classroom details:', err)
        // Don't block - we can still show the grade sheet
      }

      try {
        const subjectRes = await academicsApi.getSubject(subjectId)
        setSubject(subjectRes.data)
      } catch (err) {
        console.warn('Failed to load subject details:', err)
      }

      try {
        const attendanceRes = await academicsApi.getClassAttendanceSummary({ classroom: classroomId, term, academic_year: year })
        setAttendance(Object.fromEntries((attendanceRes.data || []).map(row => [row.student_id, row.percentage || 0])))
      } catch (err) {
        console.warn('Failed to load attendance:', err)
      }

      setDirty({})
    } catch (err) {
      console.error('Failed to load grade sheet:', err)
      setError(err?.response?.data?.error || err?.response?.data?.detail || err?.message || 'Failed to load grade sheet. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [classroomId, subjectId, term, year])

  useEffect(() => { fetchSheet() }, [fetchSheet])

  const groupedHeaders = useMemo(() => {
    const strands = []
    sheet.outcomes.forEach(outcome => {
      let strand = strands.find(row => row.name === outcome.strand)
      if (!strand) {
        strand = { name: outcome.strand, count: 0, subs: [] }
        strands.push(strand)
      }
      strand.count += 1
      let sub = strand.subs.find(row => row.name === outcome.sub_strand)
      if (!sub) {
        sub = { name: outcome.sub_strand, count: 0 }
        strand.subs.push(sub)
      }
      sub.count += 1
    })
    return strands
  }, [sheet.outcomes])

  const changeCell = (studentId, outcomeId, level) => {
    const key = `${studentId}_${outcomeId}`
    setSheet(current => ({
      ...current,
      grades: { ...current.grades, [key]: { ...(current.grades[key] || {}), level } },
    }))
    setDirty(current => ({ ...current, [key]: { student_id: studentId, outcomeId, level } }))
  }

  const saveAll = async () => {
    const entries = Object.values(dirty)
    if (entries.length === 0) return
    setSaving(true)
    setMessage('')
    try {
      const byOutcome = entries.reduce((map, entry) => {
        const list = map.get(entry.outcomeId) || []
        if (entry.level) list.push({ student_id: entry.student_id, level: entry.level, remarks: '' })
        map.set(entry.outcomeId, list)
        return map
      }, new Map())
      for (const [learning_outcome, grades] of byOutcome.entries()) {
        if (grades.length > 0) await academicsApi.bulkGrade({ learning_outcome, term, academic_year: Number(year), grades })
      }
      setDirty({})
      setMessage('Grades saved successfully')
    } catch (err) {
      setMessage(err?.response?.data?.detail || err?.message || 'Failed to save grades')
    } finally {
      setSaving(false)
    }
  }

  // Updated: CSV template with admission_number, name, and all outcome columns
  const downloadTemplate = () => {
    const headers = ['admission_number', 'name', ...sheet.outcomes.map(o => `outcome_${o.id}`), 'remarks']
    const rows = [headers]
    sheet.students.forEach(student => {
      rows.push([student.admission_number, student.name, ...sheet.outcomes.map(() => ''), ''])
    })
    downloadRowsAsCSV(`${subject?.name || 'subject'}_${classroom?.name || 'class'}_${term}_${year}_grades_template.csv`, rows)
  }

  // Updated: CSV export with admission_number, name, and filled grades
  const exportCSV = () => {
    const headers = ['admission_number', 'name', ...sheet.outcomes.map(o => `outcome_${o.id}`), 'remarks']
    const rows = [headers]
    sheet.students.forEach(student => {
      const gradeCells = sheet.outcomes.map(outcome => {
        const grade = sheet.grades?.[`${student.id}_${outcome.id}`]
        return grade?.level || ''
      })
      rows.push([student.admission_number, student.name, ...gradeCells, ''])
    })
    downloadRowsAsCSV(`${subject?.name || 'subject'}_${classroom?.name || 'class'}_${term}_${year}_grades.csv`, rows)
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  if (error) {
    return (
      <div className="space-y-4">
        <PageHeader title={`${subject?.name || 'Subject'} - ${classroom?.name || 'Class'} - ${termLabel(term)} ${year}`} />
        <Card className="p-8 text-center">
          <p className="text-lg font-medium text-red-600">Error loading grade sheet</p>
          <p className="mt-2 text-sm text-gray-500">{error}</p>
          <Button className="mt-4" onClick={fetchSheet}>Retry</Button>
        </Card>
      </div>
    )
  }

  const hasData = sheet.students.length > 0 && sheet.outcomes.length > 0

  return (
    <div className="space-y-4">
      <PageHeader
        title={`${subject?.name || 'Subject'} - ${classroom?.name || 'Class'} - ${termLabel(term)} ${year}`}
        action={
          hasData ? (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setImportOpen(true)} className="gap-2"><Upload size={16} /> Import CSV</Button>
              <Button variant="secondary" onClick={downloadTemplate} className="gap-2"><Download size={16} /> Template</Button>
              <Button variant="secondary" onClick={exportCSV} className="gap-2"><Download size={16} /> Export CSV</Button>
              <Button onClick={saveAll} loading={saving} className={Object.keys(dirty).length ? 'ring-2 ring-[var(--brand-primary-ring)]' : ''}>Save All</Button>
            </div>
          ) : (
            <span className="text-sm text-gray-500">No data available</span>
          )
        }
      />

      {message && <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">{message}</div>}

      {hasData ? (
        <Card className="overflow-hidden">
          <div className="max-h-[72vh] overflow-auto">
            <table className="w-max min-w-full border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-white">
                <tr>
                  <th rowSpan={3} className="sticky left-0 z-20 min-w-[220px] border-r border-b border-gray-100 bg-white px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Student</th>
                  {groupedHeaders.map(strand => <th key={strand.name} colSpan={strand.count} className="border-r border-b border-gray-100 px-3 py-2 text-center text-xs font-semibold text-gray-700">{strand.name}</th>)}
                </tr>
                <tr>
                  {groupedHeaders.flatMap(strand => strand.subs.map(sub => <th key={`${strand.name}-${sub.name}`} colSpan={sub.count} className="border-r border-b border-gray-100 px-3 py-2 text-center text-xs font-medium text-gray-500">{sub.name}</th>))}
                </tr>
                <tr>
                  {sheet.outcomes.map(outcome => (
                    <th key={outcome.id} title={outcome.description} className="min-w-[76px] max-w-[76px] border-r border-b border-gray-100 px-2 py-2 text-center text-[11px] font-medium text-gray-500">
                      LO {outcome.id}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sheet.students.map(student => (
                  <tr key={student.id}>
                    <td className="sticky left-0 z-10 border-r border-b border-gray-100 bg-white px-4 py-2">
                      <p className="font-medium text-gray-900">{student.name}</p>
                      <p className="text-xs text-gray-500">{student.admission_number} · Attendance {attendance[student.id] ?? 0}%</p>
                    </td>
                    {sheet.outcomes.map(outcome => {
                      const key = `${student.id}_${outcome.id}`
                      return (
                        <GradeCell
                          key={key}
                          value={sheet.grades?.[key]?.level || ''}
                          dirty={!!dirty[key]}
                          onChange={(level) => changeCell(student.id, outcome.id, level)}
                        />
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <Card className="p-8 text-center">
          {sheet.students.length === 0 && sheet.outcomes.length === 0 ? (
            <>
              <p className="text-lg font-medium text-gray-900">No students or learning outcomes found</p>
              <p className="mt-2 text-sm text-gray-500">
                There are no active students in this classroom or no learning outcomes configured for this subject.
                Please ensure the CBC curriculum has been loaded and students are enrolled in this class.
              </p>
            </>
          ) : sheet.students.length === 0 ? (
            <>
              <p className="text-lg font-medium text-gray-900">No students found</p>
              <p className="mt-2 text-sm text-gray-500">
                There are no active students in this classroom.
              </p>
            </>
          ) : (
            <>
              <p className="text-lg font-medium text-gray-900">No learning outcomes found</p>
              <p className="mt-2 text-sm text-gray-500">
                There are no learning outcomes configured for this subject.
                Please ensure the CBC curriculum has been loaded for this subject.
              </p>
            </>
          )}
        </Card>
      )}

      {importOpen && <ImportModal classroomId={classroomId} onClose={() => setImportOpen(false)} onDone={fetchSheet} />}
    </div>
  )
}