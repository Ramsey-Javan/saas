import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Download, Upload, RefreshCw } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { Button, Card, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { LEVEL_COLORS, LevelBadge, Modal, downloadRowsAsCSV, termLabel } from './shared'

const LEVELS = ['EE', 'ME', 'AE', 'BE']

function computeLevel(marks, total) {
  if (!total || marks === '') return ''
  const pct = (Number(marks) / Number(total)) * 100
  if (pct >= 75) return 'EE'
  if (pct >= 50) return 'ME'
  if (pct >= 30) return 'AE'
  return 'BE'
}

function ImportModal({ examId, onClose, onDone }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState([])
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  const loadFile = async (nextFile) => {
    setFile(nextFile)
    if (!nextFile) {
      setPreview([])
      return
    }
    const text = await nextFile.text()
    setPreview(text.split(/\r?\n/).slice(0, 6).filter(Boolean))
  }

  const submit = async (event) => {
    event.preventDefault()
    const data = new FormData()
    data.append('file', file)
    data.append('exam_setup', examId)
    setSaving(true)
    try {
      const res = await academicsApi.importResultsCSV(data)
      setMessage(`${res.data.created || 0} created, ${res.data.updated || 0} updated, ${(res.data.errors || []).length} errors`)
      onDone()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Import Exam Marks" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Close</Button><Button type="submit" form="exam-import-form" loading={saving}>Confirm Import</Button></>}>
      <form id="exam-import-form" onSubmit={submit} className="space-y-4">
        <Input label="CSV File" type="file" accept=".csv,text/csv" onChange={e => loadFile(e.target.files?.[0] || null)} required />
        {preview.length > 0 && (
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-3 font-mono text-xs text-gray-700">
            {preview.map((line, index) => <div key={`${line}-${index}`}>{line}</div>)}
          </div>
        )}
        {message && <div className="rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div>}
      </form>
    </Modal>
  )
}

function MarksCell({ student, subject, value, dirty, onSave }) {
  const [open, setOpen] = useState(false)
  const [marks, setMarks] = useState(value?.marks || '')
  const [level, setLevel] = useState(value?.cbc_level || '')
  const [overridden, setOverridden] = useState(value?.is_overridden || false)
  const [reason, setReason] = useState(value?.override_reason || '')
  const color = LEVEL_COLORS[value?.cbc_level]

  useEffect(() => {
    setMarks(value?.marks || '')
    setLevel(value?.cbc_level || '')
    setOverridden(value?.is_overridden || false)
    setReason(value?.override_reason || '')
  }, [value])

  const changeMarks = (next) => {
    setMarks(next)
    if (!overridden) setLevel(computeLevel(next, subject.total_marks))
  }

  return (
    <td className="min-w-[116px] border-r border-b border-gray-100 p-1 align-top">
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className={`h-16 w-full rounded border px-2 text-left text-xs ${color?.bg || 'bg-gray-50'} ${color?.border || 'border-gray-100'} ${dirty ? 'ring-2 ring-[var(--brand-primary-ring)]' : ''}`}
        >
          <span className="block font-semibold text-gray-900">{value?.marks ? `${value.marks}/${subject.total_marks}` : '-'}</span>
          <span className="mt-1 block"><LevelBadge level={value?.cbc_level} /></span>
        </button>
      ) : (
        <div className="w-52 rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
          <p className="mb-2 text-xs font-semibold text-gray-700">{student.name}</p>
          <Input type="number" min="0" max={subject.total_marks} value={marks} onChange={e => changeMarks(e.target.value)} />
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Select value={level} onChange={e => { setLevel(e.target.value); setOverridden(true) }}>
              {LEVELS.map(item => <option key={item} value={item}>{item}</option>)}
            </Select>
            <label className="flex items-center gap-2 text-xs text-gray-600">
              <input type="checkbox" checked={overridden} onChange={e => setOverridden(e.target.checked)} />
              Override
            </label>
          </div>
          {overridden && <Input className="mt-2" placeholder="Override reason" value={reason} onChange={e => setReason(e.target.value)} />}
          <div className="mt-3 flex justify-end gap-2">
            <Button size="sm" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={() => { onSave({ marks, cbc_level: level, is_overridden: overridden, override_reason: reason }); setOpen(false) }}>Save</Button>
          </div>
        </div>
      )}
    </td>
  )
}

export default function ExamMarksSheetPage() {
  const { examId } = useParams()
  const [sheet, setSheet] = useState(null)
  const [dirty, setDirty] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [progress, setProgress] = useState('')
  const [message, setMessage] = useState('')
  const [importOpen, setImportOpen] = useState(false)

  const fetchSheet = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await academicsApi.getMarksSheet(examId)
      setSheet(data)
      setDirty({})
    } finally {
      setLoading(false)
    }
  }, [examId])

  useEffect(() => { fetchSheet() }, [fetchSheet])

  const results = useMemo(() => ({ ...(sheet?.results || {}), ...dirty }), [sheet, dirty])

  const saveCell = (studentId, examSubjectId, value) => {
    const subject = sheet.exam_subjects.find(item => item.id === examSubjectId)
    const marks = Number(value.marks)
    if (Number.isNaN(marks) || marks < 0 || marks > subject.total_marks) return
    setDirty(current => ({
      ...current,
      [`${studentId}_${examSubjectId}`]: {
        ...(current[`${studentId}_${examSubjectId}`] || {}),
        marks,
        cbc_level: value.cbc_level || computeLevel(marks, subject.total_marks),
        is_overridden: value.is_overridden,
        override_reason: value.override_reason || '',
      },
    }))
  }

  const fillColumn = (examSubjectId) => {
    const subject = sheet.exam_subjects.find(item => item.id === examSubjectId)
    const mark = window.prompt(`Enter marks out of ${subject.total_marks}`)
    if (mark === null || mark === '') return
    const numeric = Number(mark)
    if (Number.isNaN(numeric) || numeric < 0 || numeric > subject.total_marks) return
    setDirty(current => {
      const next = { ...current }
      sheet.students.forEach(student => {
        const key = `${student.id}_${examSubjectId}`
        if (!results[key]?.marks) {
          next[key] = { marks: numeric, cbc_level: computeLevel(numeric, subject.total_marks), is_overridden: false, override_reason: '' }
        }
      })
      return next
    })
  }

  const saveAll = async () => {
    const entries = Object.entries(dirty)
    if (entries.length === 0) return
    const bySubject = entries.reduce((map, [key, value]) => {
      const [studentId, examSubjectId] = key.split('_')
      const list = map.get(examSubjectId) || []
      list.push({ student_id: Number(studentId), ...value })
      map.set(examSubjectId, list)
      return map
    }, new Map())
    setSaving(true)
    setMessage('')
    try {
      let index = 1
      let total = 0
      for (const [exam_subject, subjectResults] of bySubject.entries()) {
        setProgress(`Saving ${index} of ${bySubject.size} subjects...`)
        const res = await academicsApi.bulkEnterResults({ exam_subject: Number(exam_subject), results: subjectResults })
        total += res.data.total || 0
        index += 1
      }
      setMessage(`${total} marks saved`)
      await fetchSheet()
    } finally {
      setProgress('')
      setSaving(false)
    }
  }

  // Updated: include 'name' column after admission_number, auto-populated from student records
  const downloadTemplate = () => {
    const headers = ['admission_number', 'name', ...sheet.exam_subjects.map(s => s.subject_code)]
    const rows = [headers]
    sheet.students.forEach(student => {
      rows.push([student.admission_number, student.name, ...sheet.exam_subjects.map(() => '')])
    })
    downloadRowsAsCSV(`${sheet.exam.name}_marks_template.csv`, rows)
  }

  const sync = async () => {
    const { data } = await academicsApi.syncToCBC(examId)
    setMessage(data.message)
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>
  if (!sheet) return <Card className="p-6 text-sm text-gray-500">Exam not found.</Card>

  const hasSubjects = sheet.exam_subjects.length > 0

  return (
    <div className="space-y-4">
      <PageHeader
        title={`${sheet.exam.name} - ${sheet.exam.classroom_name} - ${termLabel(sheet.exam.term)} ${sheet.exam.academic_year}`}
        action={
          hasSubjects ? (
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={() => setImportOpen(true)} className="gap-2"><Upload size={16} /> Import CSV</Button>
              <Button variant="secondary" onClick={downloadTemplate} className="gap-2"><Download size={16} /> Download Template</Button>
              <Button variant="secondary" onClick={sync} className="gap-2"><RefreshCw size={16} /> Sync to CBC</Button>
              <Button onClick={saveAll} loading={saving} className={Object.keys(dirty).length ? 'ring-2 ring-[var(--brand-primary-ring)]' : ''}>Save All</Button>
            </div>
          ) : (
            <span className="text-sm text-gray-500">No subjects assigned</span>
          )
        }
      />
      {(message || progress) && <div className="rounded-lg bg-blue-50 px-4 py-3 text-sm text-blue-700">{progress || message}</div>}

      {hasSubjects ? (
        <Card className="overflow-hidden">
          <div className="max-h-[72vh] overflow-auto">
            <table className="w-max min-w-full border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-white">
                <tr>
                  <th className="sticky left-0 z-20 min-w-[240px] border-r border-b border-gray-100 bg-white px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Student</th>
                  {sheet.exam_subjects.map(subject => (
                    <th key={subject.id} className="min-w-[116px] border-r border-b border-gray-100 px-2 py-2 text-center">
                      <button onClick={() => fillColumn(subject.id)} className="text-xs font-semibold text-gray-800 hover:text-[var(--brand-primary)]">
                        {subject.subject_name}
                        <span className="block font-normal text-gray-500">/{subject.total_marks}</span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sheet.students.map(student => (
                  <tr key={student.id}>
                    <td className="sticky left-0 z-10 border-r border-b border-gray-100 bg-white px-4 py-2">
                      <p className="font-medium text-gray-900">{student.name}</p>
                      <p className="text-xs text-gray-500">{student.admission_number}</p>
                    </td>
                    {sheet.exam_subjects.map(subject => {
                      const key = `${student.id}_${subject.id}`
                      return <MarksCell key={key} student={student} subject={subject} value={results[key]} dirty={!!dirty[key]} onSave={value => saveCell(student.id, subject.id, value)} />
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <Card className="p-8 text-center">
          <p className="text-lg font-medium text-gray-900">No exam subjects assigned</p>
          <p className="mt-2 text-sm text-gray-500">
            There are no subjects configured or assigned for this exam.
            If you are a teacher, please contact an administrator to assign you to exam subjects.
          </p>
        </Card>
      )}

      {importOpen && <ImportModal examId={examId} onClose={() => setImportOpen(false)} onDone={fetchSheet} />}
    </div>
  )
}