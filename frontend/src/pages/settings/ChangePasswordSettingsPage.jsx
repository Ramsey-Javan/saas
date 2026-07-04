import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { authAPI } from '@/api/auth'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import PageHeader from '@/components/ui/PageHeader'

function PasswordInput({ label, value, onChange, required, minLength }) {
  const [visible, setVisible] = useState(false)

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <div className="relative">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={onChange}
          required={required}
          minLength={minLength}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-[var(--brand-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--brand-primary)] pr-10 transition-colors"
        />
        <button
          type="button"
          onClick={() => setVisible(v => !v)}
          className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600 focus:outline-none"
          tabIndex={-1}
          aria-label={visible ? 'Hide password' : 'Show password'}
        >
          {visible ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
    </div>
  )
}

export default function ChangePasswordSettingsPage() {
  const [form, setForm] = useState({
    old_password: '',
    new_password: '',
    confirm_password: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const set = (key, value) => {
    setForm(prev => ({ ...prev, [key]: value }))
    setError('')
    setSuccess('')
  }

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setSuccess('')

    if (form.new_password !== form.confirm_password) {
      setError('New password and confirmation do not match.')
      return
    }
    if (form.new_password.length < 8) {
      setError('New password must be at least 8 characters.')
      return
    }

    setSaving(true)
    try {
      await authAPI.changePassword({
        old_password: form.old_password,
        new_password: form.new_password,
      })
      setSuccess('Password updated successfully.')
      setForm({ old_password: '', new_password: '', confirm_password: '' })
    } catch (err) {
      const data = err.response?.data
      const message =
        data?.old_password?.[0] ||
        data?.new_password?.[0] ||
        data?.detail ||
        data?.error ||
        'Could not update password. Please check your current password and try again.'
      setError(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-12rem)]">
      <div className="w-full max-w-lg">
        <PageHeader title="Change Password" />
        <p className="text-sm text-gray-500 -mt-4 mb-6">
          Update the password you use to sign in.
        </p>

        <Card className="p-6 space-y-4">
          <PasswordInput
            label="Current password"
            value={form.old_password}
            onChange={(e) => set('old_password', e.target.value)}
            required
          />
          <PasswordInput
            label="New password"
            value={form.new_password}
            onChange={(e) => set('new_password', e.target.value)}
            required
            minLength={8}
          />
          <PasswordInput
            label="Confirm new password"
            value={form.confirm_password}
            onChange={(e) => set('confirm_password', e.target.value)}
            required
            minLength={8}
          />

          {error && (
            <div className="px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm">
              {error}
            </div>
          )}
          {success && (
            <div className="px-4 py-3 rounded-lg bg-green-50 text-green-700 text-sm">
              {success}
            </div>
          )}

          <Button loading={saving}>Update Password</Button>
        </Card>
      </div>
    </div>
  )
}