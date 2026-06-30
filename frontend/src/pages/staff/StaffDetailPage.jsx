import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { staffApi } from '@/api/staff'
import { studentsApi } from '@/api/students'
import DeactivateStaffModal from '@/components/staff/DeactivateStaffModal'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Input from '@/components/ui/Input'
import PageHeader from '@/components/ui/PageHeader'
import Select from '@/components/ui/Select'
import Spinner from '@/components/ui/Spinner'

const listFromResponse = (data) => data?.results || (Array.isArray(data) ? data : [])

export default function StaffDetailPage() {
  const { id } = useParams()
  const [staff, setStaff] = useState(null)
  const [pendingInvite, setPendingInvite] = useState(null)
  const [deactivateOpen, setDeactivateOpen] = useState(false)
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteForm, setInviteForm] = useState({ email: '', role: 'teacher' })
  const [inviteError, setInviteError] = useState('')
  const [inviteSaving, setInviteSaving] = useState(false)

  // Class teacher (homeroom) assignment state
  const [assignedClassrooms, setAssignedClassrooms] = useState([])
  const [allClassrooms, setAllClassrooms] = useState([])
  const [classroomsLoading, setClassroomsLoading] = useState(false)
  const [selectedClassroomToAdd, setSelectedClassroomToAdd] = useState('')
  const [classTeacherError, setClassTeacherError] = useState('')
  const [classTeacherSaving, setClassTeacherSaving] = useState(false)

  const load = async () => {
    const [{ data: profile }, { data: invites }] = await Promise.all([
      staffApi.getStaffMember(id),
      staffApi.getInvites({ staff_profile: id, status: 'pending' }),
    ])
    setStaff(profile)
    const rows = invites.results || invites
    setPendingInvite(rows[0] || null)
    setInviteForm({ email: profile.email || '', role: 'teacher' })
  }

  useEffect(() => { load() }, [id])

  const loadClassrooms = async (userId) => {
    setClassroomsLoading(true)
    try {
      const [assignedRes, allRes] = await Promise.all([
        studentsApi.getClassrooms({ class_teacher: userId }),
        studentsApi.getClassrooms({ is_active: true }),
      ])
      setAssignedClassrooms(listFromResponse(assignedRes.data))
      setAllClassrooms(listFromResponse(allRes.data))
    } catch (err) {
      console.error('Failed to load classrooms:', err)
    } finally {
      setClassroomsLoading(false)
    }
  }

  // staff.user is the CustomUser id (the FK that Classroom.class_teacher
  // actually points to) — staff.id is the StaffProfile id, which is a
  // different primary key and must not be used here.
  useEffect(() => {
    if (staff?.job_title === 'teacher' && staff.user) {
      loadClassrooms(staff.user)
    }
  }, [staff?.job_title, staff?.user])

  const sendInvite = async (event) => {
    event.preventDefault()
    setInviteSaving(true)
    setInviteError('')
    try {
      await staffApi.sendInvite(id, inviteForm)
      setInviteOpen(false)
      load()
    } catch (error) {
      setInviteError(error.response?.data?.error || 'Failed to send invite.')
    } finally {
      setInviteSaving(false)
    }
  }

  const resendInvite = async () => {
    await staffApi.resendInvite(pendingInvite.id)
    load()
  }

  const cancelInvite = async () => {
    await staffApi.cancelInvite(pendingInvite.id)
    load()
  }

  const handleAssignClassroom = async () => {
    if (!selectedClassroomToAdd || !staff.user) return
    setClassTeacherSaving(true)
    setClassTeacherError('')
    try {
      await studentsApi.assignClassTeacher(selectedClassroomToAdd, staff.user)
      setSelectedClassroomToAdd('')
      await loadClassrooms(staff.user)
    } catch (err) {
      setClassTeacherError(err.response?.data?.detail || 'Failed to assign classroom.')
    } finally {
      setClassTeacherSaving(false)
    }
  }

  const handleUnassignClassroom = async (classroomId) => {
    setClassTeacherSaving(true)
    setClassTeacherError('')
    try {
      await studentsApi.unassignClassTeacher(classroomId)
      await loadClassrooms(staff.user)
    } catch (err) {
      setClassTeacherError(err.response?.data?.detail || 'Failed to remove classroom.')
    } finally {
      setClassTeacherSaving(false)
    }
  }

  if (!staff) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    )
  }

  const assignedIds = new Set(assignedClassrooms.map((c) => c.id))
  const availableToAdd = allClassrooms.filter((c) => !assignedIds.has(c.id))

  return (
    <div>
      <PageHeader
        title={staff.full_name}
        description={`${staff.employee_number} · ${staff.job_title.replace('_', ' ')}`}
        action={(
          <div className="flex gap-2">
            <Link to={`/staff/${id}/edit`}><Button variant="secondary">Edit</Button></Link>
            <Link to="/staff"><Button variant="secondary">Back to Staff</Button></Link>
          </div>
        )}
      />
      <div className="mb-4 flex items-center gap-2">
        <Badge label={staff.job_title.replace('_', ' ')} variant="default" />
        <Badge
          label={staff.employment_status.replace('_', ' ')}
          variant={staff.employment_status === 'active' ? 'active' : 'default'}
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">Personal Info</h2>
          <p className="text-sm text-gray-600">Phone: {staff.phone}</p>
          <p className="text-sm text-gray-600">Email: {staff.email || '-'}</p>
          <p className="text-sm text-gray-600">ID number: {staff.id_number || '-'}</p>
        </Card>
        <Card className="p-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">Employment</h2>
          <p className="text-sm text-gray-600">Department: {staff.department}</p>
          <p className="text-sm text-gray-600">Employee number: {staff.employee_number}</p>
          <p className="text-sm text-gray-600">Start date: {staff.start_date}</p>
          {staff.qualifications && (
            <p className="mt-2 text-sm text-gray-600">Qualifications: {staff.qualifications}</p>
          )}
        </Card>
        {staff.job_title === 'teacher' && (
          <Card className="p-6">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Subjects Qualified</h2>
            <div className="flex flex-wrap gap-2">
              {staff.subjects_qualified_names.length
                ? staff.subjects_qualified_names.map((name) => (
                  <span key={name} className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-700">{name}</span>
                ))
                : <span className="text-sm text-gray-500">None listed</span>}
            </div>
          </Card>
        )}
        {staff.job_title === 'teacher' && (
          <Card className="p-6">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Class Teacher (Homeroom)</h2>
            {!staff.has_login ? (
              <p className="text-sm text-gray-500">
                This staff member needs a login account before they can be assigned as a class teacher.
              </p>
            ) : classroomsLoading ? (
              <Spinner />
            ) : (
              <>
                {classTeacherError && (
                  <p className="mb-3 text-sm text-red-600">{classTeacherError}</p>
                )}
                {assignedClassrooms.length === 0 ? (
                  <p className="text-sm text-gray-500">Not assigned as homeroom teacher for any class.</p>
                ) : (
                  <div className="mb-4 flex flex-wrap gap-2">
                    {assignedClassrooms.map((classroom) => (
                      <span
                        key={classroom.id}
                        className="flex items-center gap-2 rounded-full bg-[var(--brand-primary-light)] px-3 py-1 text-xs text-[var(--brand-primary)]"
                      >
                        {classroom.name}{classroom.stream ? ` ${classroom.stream}` : ''} ({classroom.academic_year})
                        <button
                          type="button"
                          onClick={() => handleUnassignClassroom(classroom.id)}
                          disabled={classTeacherSaving}
                          className="text-[var(--brand-primary)] hover:text-red-600"
                          aria-label={`Remove ${classroom.name} assignment`}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <Select
                      label="Assign as class teacher for"
                      value={selectedClassroomToAdd}
                      onChange={(e) => setSelectedClassroomToAdd(e.target.value)}
                    >
                      <option value="">Select classroom...</option>
                      {availableToAdd.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}{c.stream ? ` ${c.stream}` : ''} ({c.academic_year})
                          {c.class_teacher_name ? ` — currently: ${c.class_teacher_name}` : ''}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <Button
                    onClick={handleAssignClassroom}
                    loading={classTeacherSaving}
                    disabled={!selectedClassroomToAdd}
                  >
                    Assign
                  </Button>
                </div>
              </>
            )}
          </Card>
        )}
        <Card className="p-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">Account Status</h2>
          {staff.has_login ? (
            <>
              <p className="text-sm text-gray-600">Role: {staff.user_role?.replace('_', ' ')}</p>
              <p className="text-sm text-gray-600">Email: {staff.user_email}</p>
            </>
          ) : pendingInvite ? (
            <>
              <p className="text-sm text-gray-600">Invite pending for {pendingInvite.email}</p>
              <p className="text-sm text-gray-500">Expires: {new Date(pendingInvite.expires_at).toLocaleDateString()}</p>
              <div className="mt-4 flex gap-2">
                <Button variant="secondary" onClick={resendInvite}>Resend Invite</Button>
                <Button variant="secondary" onClick={cancelInvite}>Cancel Invite</Button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-gray-600">No system access</p>
              <Button className="mt-4" onClick={() => setInviteOpen(true)}>Send Invite Now</Button>
            </>
          )}
        </Card>
      </div>
      {staff.employment_status !== 'terminated' && (
        <Button variant="danger" className="mt-6" onClick={() => setDeactivateOpen(true)}>
          Deactivate Staff Member
        </Button>
      )}
      {deactivateOpen && (
        <DeactivateStaffModal
          staff={staff}
          onClose={() => setDeactivateOpen(false)}
          onDone={() => { setDeactivateOpen(false); load() }}
        />
      )}
      {inviteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <Card className="w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-900">Send Invite</h2>
            <p className="mt-1 text-sm text-gray-500">An email will be sent to set up their account and password.</p>
            {inviteError && <p className="mt-3 text-sm text-red-600">{inviteError}</p>}
            <form onSubmit={sendInvite} className="mt-4 space-y-4">
              <Input
                label="Email"
                type="email"
                value={inviteForm.email}
                onChange={(e) => setInviteForm((f) => ({ ...f, email: e.target.value }))}
                required
              />
              <Select
                label="Role"
                value={inviteForm.role}
                onChange={(e) => setInviteForm((f) => ({ ...f, role: e.target.value }))}
              >
                {['teacher', 'bursar', 'admin', 'support_staff'].map((role) => (
                  <option key={role} value={role}>{role.replace('_', ' ')}</option>
                ))}
              </Select>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={() => setInviteOpen(false)}>Cancel</Button>
                <Button loading={inviteSaving}>Send Invite</Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  )
}