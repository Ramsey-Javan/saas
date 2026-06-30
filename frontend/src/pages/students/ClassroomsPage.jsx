import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, School, Users } from 'lucide-react'
import { studentsApi } from '@/api/students'
import { Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from '@/components/ui'

const GRADE_LEVELS = [
  'PP1', 'PP2', 'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4',
  'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8', 'Grade 9',
]

const listFromResponse = (data) => data?.results || (Array.isArray(data) ? data : [])

const emptyForm = {
  name: '',
  grade_level: '',
  stream: '',
  academic_year: String(new Date().getFullYear()),
  capacity: 40,
}

export default function ClassroomsPage() {
  const navigate = useNavigate()
  const [classrooms, setClassrooms] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState(emptyForm)
  const [createSaving, setCreateSaving] = useState(false)
  const [createError, setCreateError] = useState('')

  const [editTarget, setEditTarget] = useState(null)
  const [editForm, setEditForm] = useState(emptyForm)
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState('')

  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteSaving, setDeleteSaving] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const load = () => {
    setLoading(true)
    setError('')
    studentsApi.getClassrooms()
      .then((r) => setClassrooms(listFromResponse(r.data)))
      .catch(() => setError('Failed to load classrooms.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const openCreate = () => {
    setCreateForm(emptyForm)
    setCreateError('')
    setCreateOpen(true)
  }

  const submitCreate = async (event) => {
    event.preventDefault()
    setCreateSaving(true)
    setCreateError('')
    try {
      await studentsApi.createClassroom({
        ...createForm,
        capacity: Number(createForm.capacity),
      })
      setCreateOpen(false)
      load()
    } catch (err) {
      const data = err.response?.data
      setCreateError(
        data?.non_field_errors?.[0] ||
        Object.values(data || {}).flat()[0] ||
        'Failed to create classroom. Check that this name/stream/year combination doesn\'t already exist.'
      )
    } finally {
      setCreateSaving(false)
    }
  }

  const openEdit = (classroom) => {
    setEditTarget(classroom)
    setEditForm({
      name: classroom.name,
      grade_level: classroom.grade_level || '',
      stream: classroom.stream || '',
      academic_year: classroom.academic_year,
      capacity: classroom.capacity,
    })
    setEditError('')
  }

  const submitEdit = async (event) => {
    event.preventDefault()
    setEditSaving(true)
    setEditError('')
    try {
      await studentsApi.updateClassroom(editTarget.id, {
        ...editForm,
        capacity: Number(editForm.capacity),
      })
      setEditTarget(null)
      load()
    } catch (err) {
      const data = err.response?.data
      setEditError(
        data?.non_field_errors?.[0] ||
        Object.values(data || {}).flat()[0] ||
        'Failed to update classroom. Check that this name/stream/year combination doesn\'t already exist.'
      )
    } finally {
      setEditSaving(false)
    }
  }

  const confirmDelete = async () => {
    setDeleteSaving(true)
    setDeleteError('')
    try {
      await studentsApi.deleteClassroom(deleteTarget.id)
      setDeleteTarget(null)
      load()
    } catch (err) {
      setDeleteError(err.response?.data?.detail || 'Failed to delete classroom.')
    } finally {
      setDeleteSaving(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Classrooms"
        description="Manage classes, streams, and capacity for this school"
        action={<Button onClick={openCreate}><Plus size={16} className="mr-2" />New Classroom</Button>}
      />

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      <Card className="overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-16"><Spinner /></div>
        ) : classrooms.length === 0 ? (
          <EmptyState
            icon={School}
            title="No classrooms yet"
            description="Create your first classroom, or one will be created automatically the first time you bulk-import students."
            action={<Button onClick={openCreate}><Plus size={14} /> New Classroom</Button>}
          />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Class</th>
                <th className="px-4 py-3">Grade Level</th>
                <th className="px-4 py-3">Academic Year</th>
                <th className="px-4 py-3">Students</th>
                <th className="px-4 py-3">Capacity</th>
                <th className="px-4 py-3">Class Teacher</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {classrooms.map((classroom) => (
                <tr key={classroom.id}>
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {classroom.name}{classroom.stream ? ` ${classroom.stream}` : ''}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{classroom.grade_level || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{classroom.academic_year}</td>
                  <td className="px-4 py-3 text-gray-600">
                    <span className="inline-flex items-center gap-1">
                      <Users size={14} className="text-gray-400" />
                      {classroom.student_count}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {classroom.student_count > classroom.capacity ? (
                      <span className="font-medium text-red-600">{classroom.capacity} (over capacity)</span>
                    ) : (
                      classroom.capacity
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{classroom.class_teacher_name || '—'}</td>
                  <td className="px-4 py-3 text-right space-x-3">
                    <button
                      type="button"
                      className="text-[var(--brand-primary)] hover:underline"
                      onClick={() => navigate(`/students?classroom=${classroom.id}`)}
                    >
                      View Students
                    </button>
                    <button
                      type="button"
                      className="text-[var(--brand-primary)] hover:underline"
                      onClick={() => openEdit(classroom)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="text-red-600 hover:underline"
                      onClick={() => { setDeleteTarget(classroom); setDeleteError('') }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <Card className="w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-900">New Classroom</h2>
            {createError && <p className="mt-3 text-sm text-red-600">{createError}</p>}
            <form onSubmit={submitCreate} className="mt-4 space-y-4">
              <Input
                label="Name (e.g. Grade 4)"
                value={createForm.name}
                onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
              <Select
                label="Grade Level"
                value={createForm.grade_level}
                onChange={(e) => setCreateForm((f) => ({ ...f, grade_level: e.target.value }))}
              >
                <option value="">Select grade...</option>
                {GRADE_LEVELS.map((g) => <option key={g} value={g}>{g}</option>)}
              </Select>
              <Input
                label="Stream (e.g. East, West — optional)"
                value={createForm.stream}
                onChange={(e) => setCreateForm((f) => ({ ...f, stream: e.target.value }))}
              />
              <Input
                label="Academic Year"
                value={createForm.academic_year}
                onChange={(e) => setCreateForm((f) => ({ ...f, academic_year: e.target.value }))}
                required
              />
              <Input
                label="Capacity"
                type="number"
                min={1}
                value={createForm.capacity}
                onChange={(e) => setCreateForm((f) => ({ ...f, capacity: e.target.value }))}
                required
              />
              <div className="flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
                <Button loading={createSaving}>Create</Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {editTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <Card className="w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-900">Edit Classroom</h2>
            <p className="mt-1 text-sm text-gray-500">
              {editTarget.student_count} student{editTarget.student_count !== 1 ? 's' : ''} currently in this class.
            </p>
            {editError && <p className="mt-3 text-sm text-red-600">{editError}</p>}
            <form onSubmit={submitEdit} className="mt-4 space-y-4">
              <Input
                label="Name"
                value={editForm.name}
                onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
              <Select
                label="Grade Level"
                value={editForm.grade_level}
                onChange={(e) => setEditForm((f) => ({ ...f, grade_level: e.target.value }))}
              >
                <option value="">Select grade...</option>
                {GRADE_LEVELS.map((g) => <option key={g} value={g}>{g}</option>)}
              </Select>
              <Input
                label="Stream"
                value={editForm.stream}
                onChange={(e) => setEditForm((f) => ({ ...f, stream: e.target.value }))}
              />
              <Input
                label="Academic Year"
                value={editForm.academic_year}
                onChange={(e) => setEditForm((f) => ({ ...f, academic_year: e.target.value }))}
                required
              />
              <Input
                label="Capacity"
                type="number"
                min={1}
                value={editForm.capacity}
                onChange={(e) => setEditForm((f) => ({ ...f, capacity: e.target.value }))}
                required
              />
              <div className="flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={() => setEditTarget(null)}>Cancel</Button>
                <Button loading={editSaving}>Save Changes</Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <Card className="w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-900">Delete Classroom</h2>
            {deleteTarget.student_count > 0 ? (
              <>
                <p className="mt-2 text-sm text-gray-600">
                  <strong>{deleteTarget.name}{deleteTarget.stream ? ` ${deleteTarget.stream}` : ''}</strong> still
                  has <strong>{deleteTarget.student_count}</strong> student{deleteTarget.student_count !== 1 ? 's' : ''} assigned.
                  Deleting it will leave those students with no class. Please transfer them to another classroom first.
                </p>
                <div className="mt-5 flex justify-end gap-2">
                  <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Close</Button>
                  <Button variant="secondary" onClick={() => navigate(`/students?classroom=${deleteTarget.id}`)}>
                    View Students
                  </Button>
                </div>
              </>
            ) : (
              <>
                <p className="mt-2 text-sm text-gray-600">
                  Delete <strong>{deleteTarget.name}{deleteTarget.stream ? ` ${deleteTarget.stream}` : ''}</strong>?
                  This cannot be undone.
                </p>
                {deleteError && <p className="mt-3 text-sm text-red-600">{deleteError}</p>}
                <div className="mt-5 flex justify-end gap-2">
                  <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
                  <Button variant="danger" loading={deleteSaving} onClick={confirmDelete}>Delete</Button>
                </div>
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}