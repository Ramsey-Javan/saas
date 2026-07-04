import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authAPI } from '@/api/auth'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Input from '@/components/ui/Input'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authAPI.requestPasswordReset(email)
      setSent(true)
    } catch (err) {
      // Surface the actual server message if available
      const data = err.response?.data
      const message =
        data?.error ||
        data?.detail ||
        'Something went wrong. Please try again.'
      setError(message)
      console.error('Password reset error:', err.response?.status, data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="w-full max-w-md p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2 text-center">
          Forgot Password?
        </h1>
        <p className="text-sm text-gray-500 mb-6 text-center">
          Enter your email and we'll send you a reset link.
        </p>

        <Card className="p-6">
          {sent ? (
            <div className="text-center space-y-4">
              <div className="px-4 py-3 rounded-lg bg-green-50 text-green-700 text-sm">
                If an account exists, a reset email has been sent.
              </div>
              <Link
                to="/login"
                className="text-sm text-[var(--brand-primary)] hover:underline font-medium"
              >
                Back to login
              </Link>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <Input
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              {error && (
                <div className="px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm">
                  {error}
                </div>
              )}
              <Button loading={loading} className="w-full">
                Send Reset Link
              </Button>
              <div className="text-center">
                <Link
                  to="/login"
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  Remember your password? Sign in
                </Link>
              </div>
            </form>
          )}
        </Card>
      </div>
    </div>
  )
}