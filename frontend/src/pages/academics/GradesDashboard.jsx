import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, Upload } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import { Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { Modal, TERMS, classroomLabel, downloadTextFile, listFromResponse, thisYear } from './shared'

function ImportGradesModal({ classrooms, onClose }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ classroom: '', term: 'term1', academic_year: thisYear(), file: null })
  const [message, setMessage] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    const data = new FormData()
    data.append('file', form.file)
    data.append('classroom', form.classroom)
    data.append('term', form.term)
    data.append('academic_year', form.academic_year)
    setSaving(true)
    try {
      const res = await academicsApi.importGradesCSV(data)
      setMessage(`${res.data.created || 0} created, ${res.data.updated || 0} updated, ${(res.data.errors || []).length} errors`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Import Grades CSV"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Close</Button>
          <Button type="submit" form="import-grades-form" loading={saving}>Import CSV</Button>
        </>
      }
    >
      <form id="import-grades-form" onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Select label="Classroom" value={form.classroom} onChange={e => setForm(f => ({ ...f, classroom: e.target.value }))} required>
          <option value="">Select class</option>
          {classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}
        </Select>
        <Select label="Term" value={form.term} onChange={e => setForm(f => ({ ...f, term: e.target.value }))}>
          {TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}
        </Select>
        <Input label="Academic Year" type="number" value={form.academic_year} onChange={e => setForm(f => ({ ...f, academic_year: e.target.value }))} required />
        <Input label="CSV File" type="file" accept=".csv,text/csv" onChange={e => setForm(f => ({ ...f, file: e.target.files?.[0] || null }))} required />
      </form>
      {message && <div className="mt-4 rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div>}
    </Modal>
  )
}

export default function GradesDashboard() {
  const navigate = useNavigate()
  const user = useAuthStore(state => state.user)
  const isAdmin = ['admin', 'superadmin'].includes(user?.role)
  const [assignments, setAssignments] = useState([])
  const [classrooms, setClassrooms] = useState([])
  const [filters, setFilters] = useState({ term: 'term1', academic_year: thisYear(), classroom: '' })
  const [loading, setLoading] = useState(true)
  const [importOpen, setImportOpen] = useState(false)

  useEffect(() => {
    const assignmentCall = isAdmin ? academicsApi.getAssignments({ academic_year: filters.academic_year, term: filters.term }) : academicsApi.getMyClasses()
    Promise.all([assignmentCall, studentsApi.getClassrooms()]).then(([assignRes, classroomRes]) => {
      setAssignments(listFromResponse(assignRes.data))
      setClassrooms(listFromResponse(classroomRes.data))
    }).finally(() => setLoading(false))
  }, [isAdmin, filters.academic_year, filters.term])

  const grouped = useMemo(() => {
    const map = new Map()
    assignments
      .filter(a => !filters.classroom || String(a.classroom) === String(filters.classroom))
      .forEach(a => {
        const row = map.get(a.classroom) || { id: a.classroom, name: a.classroom_name, subjects: [] }
        row.subjects.push(a)
        map.set(a.classroom, row)
      })
    return [...map.values()]
  }, [assignments, filters.classroom])

  const downloadTemplate = async () => {
    if (!filters.classroom) return
    const { data } = await studentsApi.getStudents({ classroom: filters.classroom, status: 'active' })
    const rows = listFromResponse(data)
    const csv = ['admission_number,outcome_id,level,remarks', ...rows.map(s => `${s.admission_number},,,`)].join('\n')
    downloadTextFile('grades_template.csv', csv)
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  return (
    <div className="space-y-6">
      <PageHeader
        title="Grade Entry"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setImportOpen(true)} className="gap-2"><Upload size={16} /> Import CSV</Button>
            <Button variant="secondary" disabled={!filters.classroom} onClick={downloadTemplate} className="gap-2"><Download size={16} /> Download CSV Template</Button>
          </div>
        }
      />

      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Select label="Term" value={filters.term} onChange={e => setFilters(f => ({ ...f, term: e.target.value }))}>
            {TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}
          </Select>
          <Input label="Academic Year" type="number" value={filters.academic_year} onChange={e => setFilters(f => ({ ...f, academic_year: e.target.value }))} />
          <Select label="Classroom" value={filters.classroom} onChange={e => setFilters(f => ({ ...f, classroom: e.target.value }))}>
            <option value="">All classes</option>
            {classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}
          </Select>
        </div>
      </Card>

      {grouped.length === 0 ? (
        <Card><EmptyState title="No assigned classes found" description="Assignments appear here after subjects are assigned to classes." /></Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {grouped.map(group => (
            <Card key={group.id} className="p-5">
              <p className="text-lg font-semibold text-gray-900">{group.name}</p>
              <p className="mt-1 text-sm text-gray-500">{filters.term} {filters.academic_year}</p>
              <div className="mt-4 space-y-2">
                {group.subjects.map(subject => (
                  <button
                    key={subject.id}
                    onClick={() => navigate(`/academics/grades/${group.id}/${subject.subject}?term=${filters.term}&year=${filters.academic_year}`)}
                    className="flex w-full items-center justify-between rounded-lg border border-gray-100 px-3 py-2 text-left text-sm hover:bg-gray-50"
                  >
                    <span className="font-medium text-gray-900">{subject.subject_name}</span>
                    <span className="text-xs text-blue-600">Open</span>
                  </button>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {importOpen && <ImportGradesModal classrooms={classrooms} onClose={() => setImportOpen(false)} />}
    </div>
  )
}
