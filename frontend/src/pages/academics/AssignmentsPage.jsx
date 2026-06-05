import { useCallback, useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import api from '@/api/client'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { Button, Card, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { EmptyTableRow, Modal, TERMS, classroomLabel, listFromResponse, thisYear } from './shared'

function AssignmentModal({ classrooms, subjects, teachers, onClose, onSaved }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ classroom: '', subject: '', teacher: '', term: 'term1', academic_year: thisYear() })

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      await academicsApi.createAssignment(form)
      onSaved()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Assign Subject to Class"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="assignment-form" loading={saving}>Assign</Button>
        </>
      }
    >
      <form id="assignment-form" onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Select label="Classroom" value={form.classroom} onChange={e => setForm(f => ({ ...f, classroom: e.target.value }))} required>
          <option value="">Select class</option>
          {classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)} ({c.academic_year})</option>)}
        </Select>
        <Select label="Subject" value={form.subject} onChange={e => setForm(f => ({ ...f, subject: e.target.value }))} required>
          <option value="">Select subject</option>
          {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
        <Select label="Teacher" value={form.teacher} onChange={e => setForm(f => ({ ...f, teacher: e.target.value }))} required>
          <option value="">Select teacher</option>
          {teachers.map(t => <option key={t.id} value={t.id}>{[t.first_name, t.last_name].filter(Boolean).join(' ') || t.email}</option>)}
        </Select>
        <Select label="Term" value={form.term} onChange={e => setForm(f => ({ ...f, term: e.target.value }))}>
          {TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}
        </Select>
        <Input label="Academic Year" type="number" value={form.academic_year} onChange={e => setForm(f => ({ ...f, academic_year: e.target.value }))} required />
      </form>
    </Modal>
  )
}

export default function AssignmentsPage() {
  const [assignments, setAssignments] = useState([])
  const [classrooms, setClassrooms] = useState([])
  const [subjects, setSubjects] = useState([])
  const [teachers, setTeachers] = useState([])
  const [filters, setFilters] = useState({ academic_year: thisYear(), term: '', classroom: '' })
  const [editingTeacher, setEditingTeacher] = useState({})
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)

  const fetchAssignments = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await academicsApi.getAssignments({
        academic_year: filters.academic_year || undefined,
        term: filters.term || undefined,
        classroom: filters.classroom || undefined,
      })
      setAssignments(listFromResponse(data))
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    Promise.all([
      studentsApi.getClassrooms(),
      academicsApi.getSubjects(),
      api.get('/auth/users/', { params: { role: 'teacher' } }),
    ]).then(([classroomRes, subjectRes, teacherRes]) => {
      setClassrooms(listFromResponse(classroomRes.data))
      setSubjects(listFromResponse(subjectRes.data))
      setTeachers(listFromResponse(teacherRes.data).filter(user => user.role === 'teacher'))
    })
  }, [])

  useEffect(() => { fetchAssignments() }, [fetchAssignments])

  const changeTeacher = async (assignment) => {
    const teacher = editingTeacher[assignment.id]
    if (!teacher) return
    await academicsApi.updateAssignment(assignment.id, { teacher })
    setEditingTeacher(current => ({ ...current, [assignment.id]: '' }))
    fetchAssignments()
  }

  const remove = async (assignment) => {
    if (!window.confirm(`Remove ${assignment.subject_name} from ${assignment.classroom_name}?`)) return
    await academicsApi.deleteAssignment(assignment.id)
    fetchAssignments()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Class Subject Assignments"
        action={<Button onClick={() => setModalOpen(true)} className="gap-2"><Plus size={16} /> Assign Subject to Class</Button>}
      />

      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Input label="Academic Year" type="number" value={filters.academic_year} onChange={e => setFilters(f => ({ ...f, academic_year: e.target.value }))} />
          <Select label="Term" value={filters.term} onChange={e => setFilters(f => ({ ...f, term: e.target.value }))}>
            <option value="">All terms</option>
            {TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}
          </Select>
          <Select label="Classroom" value={filters.classroom} onChange={e => setFilters(f => ({ ...f, classroom: e.target.value }))}>
            <option value="">All classes</option>
            {classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}
          </Select>
        </div>
      </Card>

      <Card>
        {loading ? <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  {['Classroom', 'Subject', 'Teacher', 'Term', 'Year', 'Actions'].map(header => (
                    <th key={header} className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {assignments.length === 0 ? <EmptyTableRow colSpan={6} message="No assignments found." /> : assignments.map(assignment => (
                  <tr key={assignment.id}>
                    <td className="px-4 py-3 font-medium text-gray-900">{assignment.classroom_name}</td>
                    <td className="px-4 py-3 text-gray-700">{assignment.subject_name}</td>
                    <td className="px-4 py-3">
                      <div className="flex min-w-52 gap-2">
                        <Select
                          value={editingTeacher[assignment.id] || ''}
                          onChange={e => setEditingTeacher(current => ({ ...current, [assignment.id]: e.target.value }))}
                        >
                          <option value="">{assignment.teacher_name || 'Unassigned'}</option>
                          {teachers.map(t => <option key={t.id} value={t.id}>{[t.first_name, t.last_name].filter(Boolean).join(' ') || t.email}</option>)}
                        </Select>
                        <Button size="sm" variant="secondary" disabled={!editingTeacher[assignment.id]} onClick={() => changeTeacher(assignment)}>Change</Button>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{assignment.term}</td>
                    <td className="px-4 py-3 text-gray-600">{assignment.academic_year}</td>
                    <td className="px-4 py-3">
                      <Button size="sm" variant="danger" onClick={() => remove(assignment)} className="gap-1"><Trash2 size={14} /> Remove</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {modalOpen && (
        <AssignmentModal
          classrooms={classrooms}
          subjects={subjects}
          teachers={teachers}
          onClose={() => setModalOpen(false)}
          onSaved={fetchAssignments}
        />
      )}
    </div>
  )
}
