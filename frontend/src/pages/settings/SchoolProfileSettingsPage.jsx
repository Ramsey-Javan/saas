import { useEffect, useState } from 'react'
import { staffApi } from '@/api/staff'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Input from '@/components/ui/Input'
import PageHeader from '@/components/ui/PageHeader'
import Select from '@/components/ui/Select'
import { generateBrandPalette } from '@/lib/colorUtils'
import { useAuthStore } from '@/store/authStore'

function applyPalette(primary, secondary, accent) {
  const palette = generateBrandPalette(primary || '#1e40af')
  const root = document.documentElement
  root.style.setProperty('--brand-primary', palette.primary)
  root.style.setProperty('--brand-primary-hover', palette.primaryHover)
  root.style.setProperty('--brand-primary-light', palette.primaryLight)
  root.style.setProperty('--brand-primary-ring', palette.primaryRing)
  root.style.setProperty('--brand-secondary', secondary || '#ffffff')
  root.style.setProperty('--brand-accent', accent || '#fbbc04')
}

export default function SchoolProfileSettingsPage() {
  const { setSchool } = useAuthStore()
  const [form, setForm] = useState(null)
  const [logo, setLogo] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    staffApi.getSchoolProfile().then(({ data }) => setForm(data))
  }, [])

  const set = (key, value) => {
    const next = { ...form, [key]: value }
    setForm(next)
    if (['primary_color', 'secondary_color', 'accent_color'].includes(key)) {
      applyPalette(next.primary_color, next.secondary_color, next.accent_color)
    }
  }

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    const data = new FormData()
    Object.entries(form).forEach(([key, value]) => {
      if (!['logo', 'is_in_grace_period', 'days_until_trial_expiry'].includes(key) && value !== null) data.append(key, value)
    })
    if (logo) data.append('logo', logo)
    const response = await staffApi.updateSchoolProfile(data)
    setSchool(response.data)
    applyPalette(response.data.primary_color, response.data.secondary_color, response.data.accent_color)
    setSaving(false)
  }

  if (!form) return null

  return (
    <form onSubmit={submit}>
      <PageHeader title="School Profile & Branding" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6 space-y-4">
          <Input label="School name" value={form.name || ''} onChange={(e) => set('name', e.target.value)} />
          <Input label="Motto" value={form.motto || ''} onChange={(e) => set('motto', e.target.value)} />
          <Input label="Email" value={form.email || ''} onChange={(e) => set('email', e.target.value)} />
          <Input label="Phone" value={form.phone || ''} onChange={(e) => set('phone', e.target.value)} />
          <Input label="County" value={form.county || ''} onChange={(e) => set('county', e.target.value)} />
          <Input label="Sub-county" value={form.sub_county || ''} onChange={(e) => set('sub_county', e.target.value)} />
          <label className="block text-sm font-medium text-gray-700">Address</label>
          <textarea value={form.address || ''} onChange={(e) => set('address', e.target.value)} className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" rows={3} />
        </Card>
        <Card className="p-6 space-y-4">
          <Input label="Primary color" type="color" value={form.primary_color || '#1e40af'} onChange={(e) => set('primary_color', e.target.value)} />
          <Input label="Secondary color" type="color" value={form.secondary_color || '#ffffff'} onChange={(e) => set('secondary_color', e.target.value)} />
          <Input label="Accent color" type="color" value={form.accent_color || '#fbbc04'} onChange={(e) => set('accent_color', e.target.value)} />
          <input type="file" accept="image/*" onChange={(e) => setLogo(e.target.files?.[0] || null)} className="text-sm" />
          <div className="rounded-lg border border-gray-100 p-4">
            <div className="rounded-lg bg-[var(--brand-primary)] p-4 text-white">{form.name}</div>
            <Button className="mt-4">Primary Action</Button>
          </div>
        </Card>
      </div>
      <Button className="mt-6" loading={saving}>Save Changes</Button>
    </form>
  )
}
