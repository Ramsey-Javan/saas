import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { academicsApi } from '@/api/academics'
import { staffApi } from '@/api/staff'
import { useAuthStore } from '@/store/authStore'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Input from '@/components/ui/Input'
import PageHeader from '@/components/ui/PageHeader'
import Select from '@/components/ui/Select'
import Spinner from '@/components/ui/Spinner'

const jobTitles = ['teacher', 'bursar', 'cook', 'cleaner', 'security', 'driver', 'librarian', 'accountant', 'nurse', 'groundskeeper', 'other']
const loginRoles = ['teacher', 'bursar', 'admin', 'support_staff']

export default function EditStaffPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user: currentUser } = useAuthStore()

  const [staff, setStaff] = useState(null)
  const [subjects, setSubjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [form, setForm] = useState(null)

  // Role change is handled separately from the main form — it's a more
  // sensitive operation (changes what the person can access immediately),
  // so it gets its own explicit "Update Role" button and confirmation
  // rather than silently riding along with the rest of the save.
  const [roleDraft, setRoleDraft] = useState('')
  const [roleSaving, setRoleSaving] = useState(false)
  const [roleError, setRoleError] = useState('')
  const [roleConfirmOpen, setRoleConfirmOpen] = useState(false)

  const isOwnProfile = staff?.user_email && currentUser?.email && staff.user_email === currentUser.email

  useEffect(() => {
    Promise.all([
      staffApi.getStaffMember(id),
      academicsApi.getSubjects({ is_active: true }),
    ]).then(([staffRes, subjectsRes]) => {
      const profile = staffRes.data
      setStaff(profile)
      setSubjects(subjectsRes.data.results || subjectsRes.data)
      setForm({
        first_name: profile.first_name || '',
        last_name: profile.last_name || '',
        phone: profile.phone || '',
        email: profile.email || '',
        id_number: profile.id_number || '',
        job_title: profile.job_title,
        qualifications: profile.qualifications || '',
        start_date: profile.start_date || '',
        subjects_qualified: profile.subjects_qualified || [],
      })
      setRoleDraft(profile.user_role || '')
    }).finally(() => setLoading(false))
  }, [id])

  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }))

  const wasTeacher = staff?.job_title === 'teacher'
  const losingTeacherJobTitle = useMemo(
    () => wasTeacher && form && form.job_title !== 'teacher',
    [wasTeacher, form]
  )

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setWarning('')
    try {
      const { data } = await staffApi.updateStaff(id, form)
      if (data.warning) {
        setWarning(data.warning)
      }
      setStaff(data)
      if (!data.warning) {
        navigate(`/staff/${id}`, { state: { message: 'Staff details updated.' } })
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        Object.values(err.response?.data || {}).flat()[0] ||
        'Failed to update staff member.'
      )
    } finally {
      setSaving(false)
    }
  }

  const submitRoleChange = async () => {
    setRoleSaving(true)
    setRoleError('')
    try {
      const { data } = await staffApi.changeStaffRole(id, roleDraft)
      setRoleConfirmOpen(false)
      if (data.warning) {
        setWarning(data.warning)
      }
      setStaff(data.staff)
    } catch (err) {
      setRoleError(err.response?.data?.error || 'Failed to change role.')
    } finally {
      setRoleSaving(false)
    }
  }

  if (loading || !form) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title={`Edit ${staff.full_name}`}
        action={<Button variant="secondary" onClick={() => navigate(`/staff/${id}`)}>Cancel</Button>}
      />

      {error && <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
      {warning && <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">{warning}</p>}

      <form onSubmit={submit} className="space-y-6">
        <Card className="p-6">
          <h2 className="mb-4 text-sm font-semibold text-gray-900">Personal Info</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <Input label="First name" value={form.first_name} onChange={(e) => set('first_name', e.target.value)} required />
            <Input label="Last name" value={form.last_name} onChange={(e) => set('last_name', e.target.value)} required />
            <Input label="Phone" value={form.phone} onChange={(e) => set('phone', e.target.value)} required />
            <Input label="Email" type="email" value={form.email} onChange={(e) => set('email', e.target.value)} />
            <Input label="ID number" value={form.id_number} onChange={(e) => set('id_number', e.target.value)} />
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="mb-4 text-sm font-semibold text-gray-900">Employment Details</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <Select label="Job title" value={form.job_title} onChange={(e) => set('job_title', e.target.value)}>
              {jobTitles.map((title) => <option key={title} value={title}>{title.replace('_', ' ')}</option>)}
            </Select>
            <Input label="Start date" type="date" value={form.start_date} onChange={(e) => set('start_date', e.target.value)} required />
          </div>
          {losingTeacherJobTitle && (
            <p className="mt-3 text-xs text-amber-700">
              Changing job title away from Teacher won't automatically remove any class teacher
              assignment — you'll get a chance to review that after saving.
            </p>
          )}
          <label className="mt-4 block text-sm font-medium text-gray-700">Qualifications</label>
          <textarea
            value={form.qualifications}
            onChange={(e) => set('qualifications', e.target.value)}
            className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            rows={3}
          />
          {form.job_title === 'teacher' && (
            <div className="mt-4 grid gap-2 md:grid-cols-3">
              {subjects.map((subject) => (
                <label key={subject.id} className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={form.subjects_qualified.includes(subject.id)}
                    onChange={(e) => set(
                      'subjects_qualified',
                      e.target.checked
                        ? [...form.subjects_qualified, subject.id]
                        : form.subjects_qualified.filter((sid) => sid !== subject.id)
                    )}
                  />
                  {subject.name}
                </label>
              ))}
            </div>
          )}
        </Card>

        <div className="flex gap-3">
          <Button type="button" variant="secondary" onClick={() => navigate(`/staff/${id}`)}>Cancel</Button>
          <Button loading={saving}>Save Changes</Button>
        </div>
      </form>

      {staff.has_login && (
        <Card className="mt-6 p-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">Login Role</h2>
          {isOwnProfile ? (
            <p className="text-sm text-gray-500">You cannot change your own role.</p>
          ) : (
            <>
              <p className="mb-3 text-sm text-gray-500">
                Current role: <span className="font-medium text-gray-700">{staff.user_role?.replace('_', ' ')}</span>
              </p>
              {roleError && <p className="mb-3 text-sm text-red-600">{roleError}</p>}
              <div className="flex items-end gap-2">
                <div className="w-48">
                  <Select label="New role" value={roleDraft} onChange={(e) => setRoleDraft(e.target.value)}>
                    {loginRoles.map((r) => <option key={r} value={r}>{r.replace('_', ' ')}</option>)}
                  </Select>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={roleDraft === staff.user_role}
                  onClick={() => setRoleConfirmOpen(true)}
                >
                  Update Role
                </Button>
              </div>
            </>
          )}
        </Card>
      )}

      {roleConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <Card className="w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-900">Confirm Role Change</h2>
            <p className="mt-2 text-sm text-gray-600">
              Change {staff.full_name}'s role from <strong>{staff.user_role?.replace('_', ' ')}</strong> to{' '}
              <strong>{roleDraft.replace('_', ' ')}</strong>? This takes effect immediately and changes what
              they can access.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setRoleConfirmOpen(false)}>Cancel</Button>
              <Button type="button" loading={roleSaving} onClick={submitRoleChange}>Confirm</Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}