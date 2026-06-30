import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { platformApi } from '@/api/platform'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import PageHeader from '@/components/ui/PageHeader'

export default function PlatformSchoolDetailPage() {
  const { id } = useParams()
  const [school, setSchool] = useState(null)
  const [plan, setPlan] = useState('')

  const load = () => platformApi.getSchool(id).then(({ data }) => { setSchool(data); setPlan(data.plan) })
  useEffect(() => { load() }, [id])

  const updatePlan = async () => {
    await platformApi.changePlan(id, plan)
    load()
  }

  const toggle = async () => {
    await platformApi.toggleActive(id)
    load()
  }

  if (!school) return null

  return (
    <div>
      <PageHeader title={school.name} description={school.domain} action={<Link to="/platform"><Button variant="secondary">Back</Button></Link>} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">School Info</h2>
          <p className="text-sm text-gray-600">Email: {school.email || '-'}</p>
          <p className="text-sm text-gray-600">Phone: {school.phone || '-'}</p>
          <p className="text-sm text-gray-600">Type: {school.school_type}</p>
          <p className="mt-2"><Badge label={school.is_active ? 'Active' : 'Inactive'} variant={school.is_active ? 'active' : 'inactive'} /></p>
        </Card>
        <Card className="p-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">Subscription</h2>
          <select value={plan} onChange={(e) => setPlan(e.target.value)} className="rounded-lg border border-gray-200 px-3 py-2 text-sm">
            {['trial', 'starter', 'growth', 'enterprise'].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <Button className="ml-2" onClick={updatePlan}>Update Plan</Button>
          {school.trial_ends_on && <p className="mt-3 text-sm text-gray-600">Trial ends: {school.trial_ends_on}</p>}
        </Card>
        <Card className="p-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">Admin Account</h2>
          <p className="text-sm text-gray-600">{school.admin_name || '-'}</p>
          <p className="text-sm text-gray-600">{school.admin_email || '-'}</p>
        </Card>
        <Card className="p-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">Stats</h2>
          <p className="text-sm text-gray-600">Students: {school.student_count}</p>
          <p className="text-sm text-gray-600">Staff: {school.staff_count}</p>
        </Card>
      </div>
      <div className="mt-6 flex gap-2">
        <Button variant={school.is_active ? 'danger' : 'primary'} onClick={toggle}>{school.is_active ? 'Deactivate School' : 'Activate School'}</Button>
        <Button variant="secondary" onClick={() => platformApi.seedDemoData(id)}>Seed Demo Data</Button>
      </div>
    </div>
  )
}
