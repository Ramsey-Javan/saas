import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { authAPI } from '@/api/auth'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'

function PasswordInput({ label, value, onChange, required }) {
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

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [form, setForm] = useState({ new_password: '', confirm_password: '' })
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(true)
  const [valid, setValid] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const uid = searchParams.get('uid')
  const token = searchParams.get('token')

  useEffect(() => {
    if (!uid || !token) {
      setChecking(false)
      setError('Invalid reset link.')
      return
    }
    authAPI
      .checkPasswordResetToken(uid, token)
      .then(() => setValid(true))
      .catch(() => setError('This link is invalid or has expired.'))
      .finally(() => setChecking(false))
  }, [uid, token])

  const submit = async (e) => {
    e.preventDefault()
    setError('')

    if (form.new_password !== form.confirm_password) {
      setError('Passwords do not match.')
      return
    }
    if (form.new_password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    setLoading(true)
    try {
      await authAPI.confirmPasswordReset({
        uid,
        token,
        new_password: form.new_password,
      })
      setSuccess(true)
      setTimeout(() => navigate('/login'), 3000)
    } catch (err) {
      const data = err.response?.data
      setError(data?.error || data?.detail || 'Could not reset password. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (checking) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-gray-500 text-sm">Verifying link...</div>
      </div>
    )
  }

  if (!valid || error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="w-full max-w-md p-6">
          <Card className="p-6 text-center space-y-4">
            <div className="px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm">
              {error || 'Invalid reset link.'}
            </div>
            <Link to="/login">
              <Button className="w-full">Back to Login</Button>
            </Link>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="w-full max-w-md p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2 text-center">
          Reset Password
        </h1>
        <p className="text-sm text-gray-500 mb-6 text-center">
          Enter your new password below.
        </p>

        <Card className="p-6">
          {success ? (
            <div className="text-center space-y-4">
              <div className="px-4 py-3 rounded-lg bg-green-50 text-green-700 text-sm">
                Password reset successfully. Redirecting to login...
              </div>
              <Link
                to="/login"
                className="text-sm text-[var(--brand-primary)] hover:underline font-medium"
              >
                Go to login now
              </Link>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <PasswordInput
                label="New password"
                value={form.new_password}
                onChange={(e) => setForm(f => ({ ...f, new_password: e.target.value }))}
                required
              />
              <PasswordInput
                label="Confirm new password"
                value={form.confirm_password}
                onChange={(e) => setForm(f => ({ ...f, confirm_password: e.target.value }))}
                required
              />
              {error && (
                <div className="px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm">
                  {error}
                </div>
              )}
              <Button loading={loading} className="w-full">
                Reset Password
              </Button>
            </form>
          )}
        </Card>
      </div>
    </div>
  )
}