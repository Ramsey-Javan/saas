import { useCallback, useEffect, useMemo, useState } from 'react'
import { Upload } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import { Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { Modal, TERMS, classroomLabel, listFromResponse, thisYear } from './shared'

function UploadModal({ classrooms, initial, onClose, onSaved }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ classroom: initial.classroom || '', term: initial.term || 'term1', academic_year: initial.academic_year || thisYear(), file: null, notes: '' })
  const submit = async (event) => {
    event.preventDefault()
    const data = new FormData()
    Object.entries(form).forEach(([key, value]) => {
      if (value !== null && value !== '') data.append(key, value)
    })
    setSaving(true)
    try {
      await academicsApi.uploadTimetable(data)
      onSaved()
      onClose()
    } finally {
      setSaving(false)
    }
  }
  return (
    <Modal title="Upload Timetable" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" form="timetable-form" loading={saving}>Upload</Button></>}>
      <form id="timetable-form" onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Select label="Classroom" value={form.classroom} onChange={e => setForm(f => ({ ...f, classroom: e.target.value }))} required>
            <option value="">Select class</option>
            {classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}
          </Select>
          <Select label="Term" value={form.term} onChange={e => setForm(f => ({ ...f, term: e.target.value }))}>
            {TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}
          </Select>
          <Input label="Academic Year" type="number" value={form.academic_year} onChange={e => setForm(f => ({ ...f, academic_year: e.target.value }))} />
        </div>
        <label className="flex min-h-32 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 text-sm text-gray-500">
          <Upload size={22} className="mb-2" />
          {form.file ? form.file.name : 'Drop or select a PDF timetable'}
          <input type="file" accept="application/pdf,.pdf" className="hidden" onChange={e => setForm(f => ({ ...f, file: e.target.files?.[0] || null }))} required />
        </label>
        <label className="block text-sm font-medium text-gray-700">
          Notes
          <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={3} className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[var(--brand-primary)] focus:ring-2 focus:ring-[var(--brand-primary-ring)]" />
        </label>
      </form>
    </Modal>
  )
}

export default function TimetablePage() {
  const isAdmin = useAuthStore(state => state.hasRole('admin', 'superadmin'))
  const [classrooms, setClassrooms] = useState([])
  const [timetables, setTimetables] = useState([])
  const [filters, setFilters] = useState({ classroom: '', term: 'term1', academic_year: thisYear() })
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)

  const fetchTimetables = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await academicsApi.getTimetables({
        classroom: filters.classroom || undefined,
        term: filters.term || undefined,
        academic_year: filters.academic_year || undefined,
      })
      setTimetables(listFromResponse(data))
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    studentsApi.getClassrooms().then(res => setClassrooms(listFromResponse(res.data)))
  }, [])
  useEffect(() => { fetchTimetables() }, [fetchTimetables])

  const timetable = useMemo(() => timetables[0], [timetables])

  return (
    <div className="space-y-6">
      <PageHeader title="Timetables" action={isAdmin && <Button onClick={() => setModalOpen(true)}>{timetable ? 'Replace Timetable' : 'Upload Timetable'}</Button>} />
      <Card className="p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <Select label="Classroom" value={filters.classroom} onChange={e => setFilters(f => ({ ...f, classroom: e.target.value }))}>
          <option value="">Select class</option>
          {classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}
        </Select>
        <Select label="Term" value={filters.term} onChange={e => setFilters(f => ({ ...f, term: e.target.value }))}>
          {TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}
        </Select>
        <Input label="Academic Year" type="number" value={filters.academic_year} onChange={e => setFilters(f => ({ ...f, academic_year: e.target.value }))} />
      </Card>
      <Card className="p-5">
        {loading ? <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div> : timetable ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-semibold text-gray-900">{timetable.classroom_name}</p>
                <p className="text-sm text-gray-500">Uploaded {timetable.uploaded_at ? new Date(timetable.uploaded_at).toLocaleString() : '—'} by {timetable.uploaded_by_name || '—'}</p>
              </div>
              <a href={timetable.file_url || timetable.file} target="_blank" rel="noreferrer">
                <Button variant="secondary">Download PDF</Button>
              </a>
            </div>
            <iframe title="Class timetable" src={timetable.file_url || timetable.file} className="h-[70vh] w-full rounded-lg border border-gray-100" />
          </div>
        ) : (
          <EmptyState
            icon={Upload}
            title="No timetable found"
            description="Upload a PDF timetable for the selected class and term."
            action={isAdmin && <Button onClick={() => setModalOpen(true)}>Upload Timetable</Button>}
          />
        )}
      </Card>
      {modalOpen && <UploadModal classrooms={classrooms} initial={filters} onClose={() => setModalOpen(false)} onSaved={fetchTimetables} />}
    </div>
  )
}
