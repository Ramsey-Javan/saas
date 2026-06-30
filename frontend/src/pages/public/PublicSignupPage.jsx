import { useEffect, useState } from 'react'
import { platformApi } from '@/api/platform'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Input from '@/components/ui/Input'
import Select from '@/components/ui/Select'

export default function PublicSignupPage() {
  const [form, setForm] = useState({ name: '', subdomain: '', email: '', phone: '', school_type: 'combined', admin_email: '', admin_password: '', confirm: '' })
  const [availability, setAvailability] = useState(null)
  const [created, setCreated] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (form.subdomain.length < 3) {
      setAvailability(null)
      return
    }
    const timer = setTimeout(() => {
      platformApi.checkSubdomainAvailability(form.subdomain).then(({ data }) => setAvailability(data))
    }, 350)
    return () => clearTimeout(timer)
  }, [form.subdomain])

  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }))

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (form.admin_password !== form.confirm) {
      setError('Admin passwords do not match.')
      return
    }
    setSaving(true)
    try {
      const { data } = await platformApi.onboardSchool(form)
      setCreated(data)
    } catch (err) {
      setError(err.response?.data?.error || 'Unable to create school account.')
    } finally {
      setSaving(false)
    }
  }

  if (created) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 p-6">
        <Card className="max-w-md p-8 text-center">
          <h1 className="text-2xl font-bold text-gray-900">Your school is ready!</h1>
          <p className="mt-3 text-sm text-gray-600">Log in at {created.login_url}</p>
          <a href={created.login_url}><Button className="mt-6">Go to My School</Button></a>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-6">
      <Card className="w-full max-w-2xl p-8">
        <h1 className="text-2xl font-bold text-gray-900">Create your school account</h1>
        {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <form onSubmit={submit} className="mt-6 grid gap-4 md:grid-cols-2">
          <Input label="School name" value={form.name} onChange={(e) => set('name', e.target.value)} required />
          <Input label="Subdomain" value={form.subdomain} onChange={(e) => set('subdomain', e.target.value)} required />
          <p className="md:col-span-2 text-xs text-gray-500">
            Preview: {form.subdomain || 'yourschool'}.yourapp.co.ke
            {availability && <span className={availability.available ? 'ml-3 text-green-600' : 'ml-3 text-red-600'}>{availability.available ? 'Available' : 'Taken'}</span>}
          </p>
          <Input label="School email" type="email" value={form.email} onChange={(e) => set('email', e.target.value)} required />
          <Input label="Phone" value={form.phone} onChange={(e) => set('phone', e.target.value)} required />
          <Select label="School type" value={form.school_type} onChange={(e) => set('school_type', e.target.value)}>
            <option value="primary">Primary</option>
            <option value="junior_secondary">Junior Secondary</option>
            <option value="senior_secondary">Senior Secondary</option>
            <option value="combined">Combined</option>
          </Select>
          <Input label="Admin email" type="email" value={form.admin_email} onChange={(e) => set('admin_email', e.target.value)} required />
          <Input label="Admin password" type="password" value={form.admin_password} onChange={(e) => set('admin_password', e.target.value)} required />
          <Input label="Confirm password" type="password" value={form.confirm} onChange={(e) => set('confirm', e.target.value)} required />
          <div className="md:col-span-2"><Button loading={saving}>Create My School Account</Button></div>
        </form>
      </Card>
    </div>
  )
}
