import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Download, Flag, History, RefreshCw } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { Button, Card, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { LEVEL_COLORS, LevelBadge, Modal, downloadRowsAsCSV, termLabel } from './shared'

const LEVELS = ['EE', 'ME', 'AE', 'BE']

function SyncHistoryModal({ examId, onClose }) {
  const [rows, setRows] = useState([])
  useEffect(() => {
    academicsApi.getSyncHistory(examId).then(({ data }) => setRows(data))
  }, [examId])
  return (
    <Modal title="Sync History" onClose={onClose} footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-gray-100">{['Synced At', 'By', 'Created', 'Skipped'].map(h => <th key={h} className="px-3 py-2 text-left text-xs font-semibold uppercase text-gray-500">{h}</th>)}</tr></thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.id} className="border-b border-gray-50">
                <td className="px-3 py-2">{new Date(row.synced_at).toLocaleString()}</td>
                <td className="px-3 py-2">{row.synced_by_name || '-'}</td>
                <td className="px-3 py-2">{row.records_synced}</td>
                <td className="px-3 py-2">{row.records_skipped}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Modal>
  )
}

function StudentPanel({ student, subjects, results, onClose, onSaved }) {
  const [selected, setSelected] = useState(null)
  const [level, setLevel] = useState('')
  const [reason, setReason] = useState('')
  const save = async () => {
    if (!selected?.result_id) return
    await academicsApi.updateExamResult(selected.result_id, { cbc_level: level, is_overridden: true, override_reason: reason })
    onSaved()
  }
  return (
    <Modal title={student.name} onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Close</Button><Button disabled={!selected?.result_id} onClick={save}>Save Override</Button></>}>
      <div className="space-y-3">
        {subjects.map(subject => {
          const result = results[`${student.id}_${subject.id}`]
          return (
            <button
              key={subject.id}
              onClick={() => { setSelected(result); setLevel(result?.cbc_level || 'ME'); setReason(result?.override_reason || '') }}
              className="flex w-full items-center justify-between rounded-lg border border-gray-100 px-3 py-2 text-left text-sm hover:bg-gray-50"
            >
              <span><span className="font-medium text-gray-900">{subject.subject_name}</span><span className="block text-xs text-gray-500">{result ? `${result.marks}/${subject.total_marks}` : 'No marks'}</span></span>
              <LevelBadge level={result?.cbc_level} />
            </button>
          )
        })}
        {selected?.result_id && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select label="New Level" value={level} onChange={e => setLevel(e.target.value)}>
              {LEVELS.map(item => <option key={item} value={item}>{item}</option>)}
            </Select>
            <Input label="Reason" value={reason} onChange={e => setReason(e.target.value)} />
          </div>
        )}
      </div>
    </Modal>
  )
}

export default function ExamResultsPage() {
  const { examId } = useParams()
  const [sheet, setSheet] = useState(null)
  const [loading, setLoading] = useState(true)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [studentOpen, setStudentOpen] = useState(null)
  const [filterLevel, setFilterLevel] = useState('')
  const [overriddenOnly, setOverriddenOnly] = useState(false)
  const [sortSubject, setSortSubject] = useState('')
  const [message, setMessage] = useState('')

  const fetchSheet = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await academicsApi.getMarksSheet(examId)
      setSheet(data)
    } finally {
      setLoading(false)
    }
  }, [examId])

  useEffect(() => { fetchSheet() }, [fetchSheet])

  const visibleStudents = useMemo(() => {
    if (!sheet) return []
    let rows = [...sheet.students]
    if (filterLevel) {
      rows = rows.filter(student => sheet.exam_subjects.some(subject => sheet.results[`${student.id}_${subject.id}`]?.cbc_level === filterLevel))
    }
    if (overriddenOnly) {
      rows = rows.filter(student => sheet.exam_subjects.some(subject => sheet.results[`${student.id}_${subject.id}`]?.is_overridden))
    }
    if (sortSubject) {
      rows.sort((a, b) => Number(sheet.results[`${b.id}_${sortSubject}`]?.marks || -1) - Number(sheet.results[`${a.id}_${sortSubject}`]?.marks || -1))
    }
    return rows
  }, [sheet, filterLevel, overriddenOnly, sortSubject])

  const summary = useMemo(() => {
    if (!sheet) return []
    return sheet.exam_subjects.map(subject => {
      const values = sheet.students.map(student => sheet.results[`${student.id}_${subject.id}`]).filter(Boolean)
      const sum = values.reduce((total, result) => total + Number(result.marks || 0), 0)
      const counts = LEVELS.reduce((map, level) => ({ ...map, [level]: values.filter(result => result.cbc_level === level).length }), {})
      return { subject, average: values.length ? Math.round((sum / values.length) * 10) / 10 : 0, counts }
    })
  }, [sheet])

  const sync = async () => {
    const count = sheet?.students?.length || 0
    if (!window.confirm(`This will fill empty CBC grades for ${count} students. Manual CBC grades will not be overwritten.`)) return
    const { data } = await academicsApi.syncToCBC(examId)
    setMessage(data.message)
  }

  const exportCSV = () => {
    const rows = [['Student', 'Adm No', ...sheet.exam_subjects.map(subject => subject.subject_name)]]
    visibleStudents.forEach(student => rows.push([
      student.name,
      student.admission_number,
      ...sheet.exam_subjects.map(subject => {
        const result = sheet.results[`${student.id}_${subject.id}`]
        return result ? `${result.marks}/${subject.total_marks} ${result.percentage}% ${result.cbc_level}` : ''
      }),
    ]))
    downloadRowsAsCSV(`${sheet.exam.name}_results.csv`, rows)
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>
  if (!sheet) return <Card className="p-6 text-sm text-gray-500">Exam not found.</Card>

  return (
    <div className="space-y-5">
      <PageHeader
        title={`${sheet.exam.name} - ${sheet.exam.classroom_name} - ${termLabel(sheet.exam.term)}`}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={sync} className="gap-2"><RefreshCw size={16} /> Sync to CBC</Button>
            <Button variant="secondary" onClick={() => setHistoryOpen(true)} className="gap-2"><History size={16} /> Sync History</Button>
            <Button variant="secondary" onClick={exportCSV} className="gap-2"><Download size={16} /> Export CSV</Button>
            <Button variant="secondary" onClick={() => window.print()} className="gap-2"><Download size={16} /> Export PDF</Button>
          </div>
        }
      />
      {message && <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">{message}</div>}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {summary.map(row => (
          <Card key={row.subject.id} className="p-4">
            <div className="flex items-center justify-between">
              <p className="font-semibold text-gray-900">{row.subject.subject_name}</p>
              <p className="text-sm text-gray-500">Average {row.average}</p>
            </div>
            <div className="mt-3 grid grid-cols-4 gap-2">
              {LEVELS.map(level => (
                <div key={level}>
                  <div className="mb-1 flex justify-between text-xs"><span>{level}</span><span>{row.counts[level]}</span></div>
                  <div className="h-2 rounded bg-gray-100"><div className={`h-2 rounded ${LEVEL_COLORS[level].bg}`} style={{ width: `${sheet.students.length ? (row.counts[level] / sheet.students.length) * 100 : 0}%` }} /></div>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
      <Card className="p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <Select label="Sort by Subject Marks" value={sortSubject} onChange={e => setSortSubject(e.target.value)}>
          <option value="">Default order</option>
          {sheet.exam_subjects.map(subject => <option key={subject.id} value={subject.id}>{subject.subject_name}</option>)}
        </Select>
        <Select label="CBC Level" value={filterLevel} onChange={e => setFilterLevel(e.target.value)}>
          <option value="">All levels</option>
          {LEVELS.map(level => <option key={level} value={level}>{level}</option>)}
        </Select>
        <label className="flex items-end gap-2 pb-2 text-sm text-gray-700">
          <input type="checkbox" checked={overriddenOnly} onChange={e => setOverriddenOnly(e.target.checked)} />
          Overridden only
        </label>
      </Card>
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-max min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="sticky left-0 z-10 bg-white px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Student</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Adm No</th>
                {sheet.exam_subjects.map(subject => <th key={subject.id} className="min-w-[140px] px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">{subject.subject_name}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {visibleStudents.map(student => (
                <tr key={student.id} onClick={() => setStudentOpen(student)} className="cursor-pointer hover:bg-gray-50">
                  <td className="sticky left-0 bg-white px-4 py-3 font-medium text-gray-900">{student.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">{student.admission_number}</td>
                  {sheet.exam_subjects.map(subject => {
                    const result = sheet.results[`${student.id}_${subject.id}`]
                    return (
                      <td key={subject.id} className="px-4 py-3">
                        {result ? (
                          <div className="space-y-1">
                            <p className="font-semibold text-gray-900">{result.marks}/{subject.total_marks}</p>
                            <p className="text-xs text-gray-500">{Number(result.percentage).toFixed(1)}%</p>
                            <div className="flex items-center gap-1"><LevelBadge level={result.cbc_level} />{result.is_overridden && <Flag size={13} className="text-orange-600" />}</div>
                          </div>
                        ) : <span className="text-gray-400">-</span>}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      {historyOpen && <SyncHistoryModal examId={examId} onClose={() => setHistoryOpen(false)} />}
      {studentOpen && <StudentPanel student={studentOpen} subjects={sheet.exam_subjects} results={sheet.results} onClose={() => setStudentOpen(null)} onSaved={fetchSheet} />}
    </div>
  )
}
