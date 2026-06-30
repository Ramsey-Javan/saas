import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { platformApi } from '@/api/platform'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import PageHeader from '@/components/ui/PageHeader'

export default function SuperadminDashboard() {
  const [stats, setStats] = useState(null)
  const [schools, setSchools] = useState([])
  const [filters, setFilters] = useState({ search: '', plan: '', is_active: '' })
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({
    name: '',
    slug: '',
    domain: '',
    email: '',
    phone: '',
    school_type: 'combined',
    admin_email: '',
    admin_password: '',
    admin_first_name: '',
    admin_last_name: '',
  })
  const [formError, setFormError] = useState('')
  const [createdSchool, setCreatedSchool] = useState(null)

  const load = () => {
    const params = {}
    if (filters.search) params.search = filters.search
    if (filters.plan) params.plan = filters.plan
    if (filters.is_active) params.is_active = filters.is_active
    platformApi.getPlatformStats().then(({ data }) => setStats(data))
    platformApi.getSchools(params).then(({ data }) => setSchools(data.results || data))
  }

  useEffect(() => { load() }, [filters])

  const toggle = async (id) => {
    if (window.confirm('Toggle this school active status?')) {
      await platformApi.toggleActive(id)
      load()
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setFormError('')
    setCreatedSchool(null)
    try {
      const { data } = await platformApi.createSchool(form)
      setCreatedSchool(data)
      setForm({
        name: '', slug: '', domain: '', email: '', phone: '',
        school_type: 'combined', admin_email: '', admin_password: '',
        admin_first_name: '', admin_last_name: '',
      })
      load()
    } catch (err) {
      setFormError(err.response?.data?.error || 'Failed to create school.')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <PageHeader title="Platform Dashboard" />
        <Button onClick={() => { setShowModal(true); setCreatedSchool(null); setFormError(''); }}>+ Create School</Button>
      </div>

      {stats && (
        <div className="mb-6 grid gap-4 md:grid-cols-5">
          {[
            ['Total Schools', stats.total_schools],
            ['Active Schools', stats.active_schools],
            ['Trial Schools', stats.trial_schools],
            ['Paying Schools', stats.paying_schools],
            ['Total Students', stats.total_students_platform_wide],
          ].map(([label, value]) => (
            <Card key={label} className="p-4">
              <p className="text-xs text-gray-500">{label}</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
            </Card>
          ))}
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <input
          placeholder="Search schools"
          value={filters.search}
          onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
          className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
        />
        <select
          value={filters.plan}
          onChange={(e) => setFilters((f) => ({ ...f, plan: e.target.value }))}
          className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
        >
          <option value="">Any plan</option>
          {['trial', 'starter', 'growth', 'enterprise'].map((plan) => (
            <option key={plan} value={plan}>{plan}</option>
          ))}
        </select>
      </div>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
            <tr>
              <th className="px-4 py-3">School</th>
              <th className="px-4 py-3">Plan</th>
              <th className="px-4 py-3">Students</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Trial Days</th>
              <th className="px-4 py-3">Admin</th>
              <th></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {schools.map((school) => (
              <tr key={school.id}>
                <td className="px-4 py-3 font-medium text-gray-900">{school.name}</td>
                <td className="px-4 py-3 capitalize">{school.plan}</td>
                <td className="px-4 py-3">{school.student_count}</td>
                <td className="px-4 py-3">
                  <Badge
                    label={school.is_active ? 'Active' : 'Inactive'}
                    variant={school.is_active ? 'active' : 'inactive'}
                  />
                </td>
                <td className="px-4 py-3">{school.days_until_expiry ?? '-'}</td>
                <td className="px-4 py-3">{school.admin_email || '-'}</td>
                <td className="px-4 py-3 text-right space-x-3">
                  <Link className="text-[var(--brand-primary)] hover:underline" to={`/platform/schools/${school.id}`}>View</Link>
                  <button className="text-gray-600 hover:underline" onClick={() => toggle(school.id)}>Toggle</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-lg bg-white p-6 shadow-lg">
            <h2 className="mb-4 text-lg font-semibold">Create New School</h2>

            {createdSchool ? (
              <div className="space-y-4">
                <div className="rounded-lg bg-green-50 p-4 text-green-800">
                  <p className="font-semibold">School created successfully!</p>
                  <p className="mt-1 text-sm">School: <strong>{createdSchool.name}</strong></p>
                  <p className="text-sm">Admin Email: <strong>{createdSchool.admin_email}</strong></p>
                  <p className="text-sm">Admin Password: <strong className="select-all">{createdSchool.admin_password}</strong></p>
                  <p className="mt-2 text-xs text-green-700">Copy this password now. It will not be shown again.</p>
                </div>
                <div className="flex justify-end">
                  <Button onClick={() => { setShowModal(false); setCreatedSchool(null); }}>Close</Button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleCreate} className="space-y-3">
                {formError && <p className="text-sm text-red-600">{formError}</p>}

                <p className="text-xs font-semibold uppercase text-gray-500">School Details</p>
                <input className="w-full rounded border px-3 py-2 text-sm" placeholder="School Name *" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required />
                <input className="w-full rounded border px-3 py-2 text-sm" placeholder="Slug (subdomain) *" value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value }))} required />
                <input className="w-full rounded border px-3 py-2 text-sm" placeholder="Domain (optional)" value={form.domain} onChange={e => setForm(f => ({ ...f, domain: e.target.value }))} />
                <input className="w-full rounded border px-3 py-2 text-sm" placeholder="School Email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
                <input className="w-full rounded border px-3 py-2 text-sm" placeholder="School Phone" value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} />
                <select className="w-full rounded border px-3 py-2 text-sm" value={form.school_type} onChange={e => setForm(f => ({ ...f, school_type: e.target.value }))}>
                  <option value="primary">CBC Primary</option>
                  <option value="junior_secondary">Junior Secondary</option>
                  <option value="senior_secondary">Senior Secondary</option>
                  <option value="combined">Combined</option>
                </select>

                <hr className="my-2" />
                <p className="text-xs font-semibold uppercase text-gray-500">School Admin Account</p>
                <input className="w-full rounded border px-3 py-2 text-sm" placeholder="Admin Email *" type="email" value={form.admin_email} onChange={e => setForm(f => ({ ...f, admin_email: e.target.value }))} required />
                <input className="w-full rounded border px-3 py-2 text-sm" placeholder="Admin Password *" type="password" value={form.admin_password} onChange={e => setForm(f => ({ ...f, admin_password: e.target.value }))} required />
                <input className="w-full rounded border px-3 py-2 text-sm" placeholder="Admin First Name" value={form.admin_first_name} onChange={e => setForm(f => ({ ...f, admin_first_name: e.target.value }))} />
                <input className="w-full rounded border px-3 py-2 text-sm" placeholder="Admin Last Name" value={form.admin_last_name} onChange={e => setForm(f => ({ ...f, admin_last_name: e.target.value }))} />

                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" onClick={() => setShowModal(false)} type="button">Cancel</Button>
                  <Button type="submit">Create School</Button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  )
}