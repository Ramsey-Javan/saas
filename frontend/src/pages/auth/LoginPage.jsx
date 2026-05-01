import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, GraduationCap, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'

const schema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})

export default function LoginPage() {
  const navigate = useNavigate()
  const { setAuth, school } = useAuthStore()
  const [showPassword, setShowPassword] = useState(false)
  const [serverError, setServerError] = useState('')

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) })

  const onSubmit = async ({ email, password }) => {
    setServerError('')
    // Temporary mock - replace with real API call later
    if (email === 'admin@demo.co.ke' && password === 'demo1234') {
      setAuth(
        { email, first_name: 'Demo', last_name: 'Admin', role: 'admin' },
        'fake-access-token',
        'fake-refresh-token'
      )
      navigate('/dashboard')
    } else {
      setServerError('Invalid email or password')
    }
  }

  // School branding from tenant (injected at runtime)
  const schoolName = school?.name || 'School Management'
  const primaryColor = school?.primary_color || '#1e40af'
  const logo = school?.logo

  return (
    <div className="min-h-screen flex" style={{ '--brand': primaryColor }}>

      {/* ── Left panel — branding ─────────────────────────────────────── */}
      <div
        className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 text-white relative overflow-hidden"
        style={{ backgroundColor: primaryColor }}
      >
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-10">
          <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="1"/>
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>
        </div>

        {/* Logo + name */}
        <div className="relative z-10 flex items-center gap-3">
          {logo ? (
            <img src={logo} alt={schoolName} className="h-10 w-10 rounded-lg object-cover" />
          ) : (
            <div className="h-10 w-10 rounded-lg bg-white/20 flex items-center justify-center">
              <GraduationCap className="h-6 w-6 text-white" />
            </div>
          )}
          <span className="text-xl font-bold tracking-tight">{schoolName}</span>
        </div>

        {/* Hero text */}
        <div className="relative z-10">
          <h1 className="text-4xl font-bold leading-tight mb-4">
            Everything your school needs,<br />in one place.
          </h1>
          <p className="text-white/70 text-lg">
            Students · Fees · Attendance · CBC Grading · SMS Alerts
          </p>
        </div>

        {/* Bottom decorative circles */}
        <div className="absolute bottom-0 right-0 w-64 h-64 rounded-full bg-white/5 translate-x-16 translate-y-16" />
        <div className="absolute bottom-24 right-12 w-32 h-32 rounded-full bg-white/10" />
      </div>

      {/* ── Right panel — form ────────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-8 bg-gray-50">
        <div className="w-full max-w-md">

          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div
              className="h-9 w-9 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: primaryColor }}
            >
              <GraduationCap className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-gray-900">{schoolName}</span>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-gray-900">Welcome back</h2>
              <p className="text-gray-500 mt-1">Sign in to your account</p>
            </div>

            {/* Server error */}
            {serverError && (
              <div className="mb-5 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
                {serverError}
              </div>
            )}

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

              {/* Email */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Email address
                </label>
                <input
                  type="email"
                  autoComplete="email"
                  placeholder="you@school.co.ke"
                  {...register('email')}
                  className={cn(
                    'w-full px-4 py-2.5 rounded-lg border text-sm outline-none transition-all',
                    'focus:ring-2 focus:border-transparent placeholder:text-gray-400',
                    errors.email
                      ? 'border-red-300 focus:ring-red-200'
                      : 'border-gray-200 focus:ring-blue-100'
                  )}
                  style={!errors.email ? { '--tw-ring-color': `${primaryColor}33` } : {}}
                />
                {errors.email && (
                  <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
                )}
              </div>

              {/* Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    placeholder="••••••••"
                    {...register('password')}
                    className={cn(
                      'w-full px-4 py-2.5 pr-10 rounded-lg border text-sm outline-none transition-all',
                      'focus:ring-2 focus:border-transparent placeholder:text-gray-400',
                      errors.password
                        ? 'border-red-300 focus:ring-red-200'
                        : 'border-gray-200 focus:ring-blue-100'
                    )}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {errors.password && (
                  <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
                )}
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={isSubmitting}
                className={cn(
                  'w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-all',
                  'disabled:opacity-60 disabled:cursor-not-allowed',
                  'hover:opacity-90 active:scale-[0.99]'
                )}
                style={{ backgroundColor: primaryColor }}
              >
                {isSubmitting ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 size={16} className="animate-spin" />
                    Signing in...
                  </span>
                ) : (
                  'Sign in'
                )}
              </button>
            </form>

            <p className="mt-6 text-center text-xs text-gray-400">
              Having trouble? Contact your school administrator.
            </p>
          </div>

          <p className="mt-4 text-center text-xs text-gray-400">
            Powered by{' '}
            <span className="font-medium text-gray-500">SchoolSaaS</span>
          </p>
        </div>
      </div>
    </div>
  )
}