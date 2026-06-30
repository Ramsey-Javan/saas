import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { GraduationCap } from 'lucide-react'
import { staffApi } from '@/api/staff'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'

export default function AcceptInvitePage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const token = params.get('token')
  const [invite, setInvite] = useState(null)
  const [error, setError] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!token) {
      setError('This invite link is invalid or has expired. Please contact your school administrator.')
      return
    }
    staffApi.checkInvite(token)
      .then(({ data }) => data.valid ? setInvite(data) : setError(data.error))
      .catch((err) => setError(err.response?.data?.error || 'This invite link is invalid or has expired.'))
  }, [token])

  const submit = async (event) => {
    event.preventDefault()
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setSaving(true)
    await staffApi.acceptInvite(token, password)
    setSaving(false)
    navigate('/login', { state: { message: 'Account created! Please log in.' } })
  }

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 text-white bg-[var(--brand-primary)]">
        <div className="flex items-center gap-3"><GraduationCap /> <span className="font-bold">School Management Platform</span></div>
        <h1 className="text-4xl font-bold">Set up your staff account.</h1>
      </div>
      <div className="flex flex-1 items-center justify-center bg-gray-50 p-8">
        <div className="w-full max-w-md rounded-lg border border-gray-100 bg-white p-8 shadow-sm">
          {error && !invite ? (
            <>
              <h1 className="text-xl font-semibold text-gray-900">Invite unavailable</h1>
              <p className="mt-2 text-sm text-red-600">{error}</p>
              <Link to="/login"><Button className="mt-6">Go to Login</Button></Link>
            </>
          ) : invite ? (
            <form onSubmit={submit} className="space-y-4">
              <h1 className="text-xl font-semibold text-gray-900">Welcome {invite.name}</h1>
              <p className="text-sm text-gray-500">You've been invited to join as a {invite.role}.</p>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <Input label="Email" value={invite.email} readOnly />
              <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              <Input label="Confirm password" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
              <Button loading={saving}>Set Up My Account</Button>
            </form>
          ) : (
            <p className="text-sm text-gray-500">Checking invite...</p>
          )}
        </div>
      </div>
    </div>
  )
}
