import { useEffect, useState } from 'react'
import { staffApi } from '@/api/staff'
import Button from '@/components/ui/Button'

export default function DeactivateStaffModal({ staff, onClose, onDone }) {
  const [assignments, setAssignments] = useState(null)
  const [teachers, setTeachers] = useState([])
  const [reassignTo, setReassignTo] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    staffApi.getAssignments(staff.id).then(({ data }) => setAssignments(data))
    staffApi.getStaff({ job_title: 'teacher', is_active: true }).then(({ data }) => {
      const rows = data.results || data
      setTeachers(rows.filter((item) => item.id !== staff.id && item.has_login && item.user))
    })
  }, [staff.id])

  const submit = async (withReassign) => {
    setSaving(true)
    setError('')
    try {
      await staffApi.deactivateStaff(staff.id, {
        reassign_to: withReassign && reassignTo ? Number(reassignTo) : null,
      })
      onDone()
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to deactivate staff member.')
      setSaving(false)
    }
  }

  const total = assignments?.total_count || 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-gray-900">Deactivate {staff.full_name}?</h2>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        {!assignments ? (
          <p className="mt-3 text-sm text-gray-500">Checking assignments...</p>
        ) : total === 0 ? (
          <p className="mt-3 text-sm text-gray-600">This cannot be undone.</p>
        ) : (
          <div className="mt-4 space-y-3 text-sm">
            <p className="font-medium text-gray-800">{total} current assignment{total === 1 ? '' : 's'} found.</p>
            {assignments.class_subject_assignments.length > 0 && (
              <div>
                <p className="font-medium text-gray-700">
                  Class Subject Assignments ({assignments.class_subject_assignments.length})
                </p>
                <ul className="mt-1 space-y-1 text-gray-600">
                  {assignments.class_subject_assignments.map((item) => (
                    <li key={`a-${item.id}`}>{item.classroom}: {item.subject}</li>
                  ))}
                </ul>
              </div>
            )}
            {assignments.class_teacher_roles.length > 0 && (
              <div>
                <p className="font-medium text-gray-700">Class Teacher Roles</p>
                <ul className="mt-1 space-y-1 text-gray-600">
                  {assignments.class_teacher_roles.map((item) => (
                    <li key={`c-${item.id}`}>Class teacher of {item.classroom}</li>
                  ))}
                </ul>
              </div>
            )}
            {assignments.exam_subjects.length > 0 && (
              <div>
                <p className="font-medium text-gray-700">
                  Exam Subjects ({assignments.exam_subjects.length})
                </p>
                <ul className="mt-1 space-y-1 text-gray-600">
                  {assignments.exam_subjects.map((item) => (
                    <li key={`e-${item.id}`}>{item.exam}: {item.subject}</li>
                  ))}
                </ul>
              </div>
            )}
            <label className="block text-sm font-medium text-gray-700">Reassign all of these to</label>
            <select
              value={reassignTo}
              onChange={(event) => setReassignTo(event.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            >
              <option value="">Select a teacher</option>
              {teachers.map((teacher) => (
                <option key={teacher.id} value={teacher.user}>{teacher.full_name}</option>
              ))}
            </select>
            {!reassignTo && (
              <p className="text-amber-700">
                Assignments will be left unassigned. You&apos;ll need to manually update them later.
              </p>
            )}
          </div>
        )}
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          {total > 0 && !reassignTo && (
            <Button variant="secondary" loading={saving} onClick={() => submit(false)}>
              Deactivate Without Reassigning
            </Button>
          )}
          <Button
            variant="danger"
            loading={saving}
            onClick={() => submit(total > 0 && Boolean(reassignTo))}
          >
            {total > 0 && reassignTo ? 'Deactivate & Reassign' : 'Deactivate'}
          </Button>
        </div>
      </div>
    </div>
  )
}
