import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { academicsApi } from '@/api/academics'
import { staffApi } from '@/api/staff'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Input from '@/components/ui/Input'
import PageHeader from '@/components/ui/PageHeader'
import Select from '@/components/ui/Select'

const jobTitles = ['teacher', 'bursar', 'cook', 'cleaner', 'security', 'driver', 'librarian', 'accountant', 'nurse', 'groundskeeper', 'other']

export default function AddStaffPage() {
  const navigate = useNavigate()
  const [subjects, setSubjects] = useState([])
  const [created, setCreated] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    first_name: '', last_name: '', phone: '', email: '', id_number: '',
    job_title: 'teacher', start_date: new Date().toISOString().slice(0, 10),
    qualifications: '', subjects_qualified: [], onboarding_method: 'direct',
    role: 'teacher', temp_password: '',
  })

  useEffect(() => {
    academicsApi.getSubjects({ is_active: true }).then(({ data }) => setSubjects(data.results || data))
  }, [])

  const generatedPassword = useMemo(() => Math.random().toString(36).slice(2, 10) + 'A1!', [])
  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }))

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = { ...form }
      if (payload.onboarding_method === 'direct' && !payload.temp_password) {
        payload.temp_password = generatedPassword
      }
      const { data } = await staffApi.onboardStaff(payload)
      if (form.onboarding_method === 'direct') {
        setCreated({ email: data.login_email, password: payload.temp_password })
      } else if (form.onboarding_method === 'invite') {
        navigate('/staff', { state: { message: `Invite sent to ${data.invite?.email || form.email}.` } })
      } else {
        navigate('/staff')
      }
    } catch (err) {
      setError(err.response?.data?.detail || Object.values(err.response?.data || {}).flat()[0] || 'Failed to create staff member.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <PageHeader title="Add Staff Member" />
      {error && <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
      <form onSubmit={submit} className="space-y-6">
        <Card className="p-6">
          <h2 className="mb-4 text-sm font-semibold text-gray-900">Personal Info</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <Input label="First name" value={form.first_name} onChange={(e) => set('first_name', e.target.value)} required />
            <Input label="Last name" value={form.last_name} onChange={(e) => set('last_name', e.target.value)} required />
            <Input label="Phone" value={form.phone} onChange={(e) => set('phone', e.target.value)} required />
            <Input label="Email" type="email" value={form.email} onChange={(e) => set('email', e.target.value)} required={form.onboarding_method === 'invite'} />
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
          <label className="mt-4 block text-sm font-medium text-gray-700">Qualifications</label>
          <textarea value={form.qualifications} onChange={(e) => set('qualifications', e.target.value)} className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" rows={3} />
          {form.job_title === 'teacher' && (
            <div className="mt-4 grid gap-2 md:grid-cols-3">
              {subjects.map((subject) => (
                <label key={subject.id} className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" checked={form.subjects_qualified.includes(subject.id)} onChange={(e) => set('subjects_qualified', e.target.checked ? [...form.subjects_qualified, subject.id] : form.subjects_qualified.filter((id) => id !== subject.id))} />
                  {subject.name}
                </label>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-6">
          <h2 className="mb-4 text-sm font-semibold text-gray-900">Account Setup</h2>
          <div className="flex flex-wrap gap-2">
            {[['direct', 'Create Login Now'], ['invite', 'Send Email Invite'], ['none', 'No Login Needed']].map(([value, label]) => (
              <button type="button" key={value} onClick={() => set('onboarding_method', value)} className={`rounded-lg border px-4 py-2 text-sm ${form.onboarding_method === value ? 'border-[var(--brand-primary)] bg-[var(--brand-primary-light)] text-[var(--brand-primary)]' : 'border-gray-200 text-gray-600'}`}>{label}</button>
            ))}
          </div>
          {form.onboarding_method !== 'none' && (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <Select label="Role" value={form.role} onChange={(e) => set('role', e.target.value)}>
                {['teacher', 'bursar', 'admin', 'support_staff'].map((role) => <option key={role} value={role}>{role.replace('_', ' ')}</option>)}
              </Select>
              {form.onboarding_method === 'direct' && (
                <Input label="Temporary password" value={form.temp_password} onChange={(e) => set('temp_password', e.target.value)} required />
              )}
            </div>
          )}
          {form.onboarding_method === 'direct' && <Button type="button" variant="secondary" className="mt-3" onClick={() => set('temp_password', generatedPassword)}>Generate Random Password</Button>}
        </Card>
        <Button loading={saving}>Create Staff Member</Button>
      </form>
      {created && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <Card className="w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-gray-900">Login Created</h2>
            <p className="mt-3 text-sm text-gray-600">Email: {created.email}</p>
            <p className="mt-1 text-sm text-gray-600">Temporary password: {created.password}</p>
            <Button className="mt-5" onClick={() => navigate('/staff')}>Done</Button>
          </Card>
        </div>
      )}
    </div>
  )
}
