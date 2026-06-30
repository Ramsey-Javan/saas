import { useEffect } from 'react'
import { staffApi } from '@/api/staff'
import { useAuthStore } from '@/store/authStore'

export default function TrialBanner() {
  const { user, school, setSchool } = useAuthStore()

  useEffect(() => {
    if (user?.role !== 'admin') return
    staffApi.getSchoolProfile()
      .then(({ data }) => setSchool(data))
      .catch(() => {})
  }, [user, setSchool])

  if (user?.role !== 'admin' || school?.plan !== 'trial') return null

  const days = school.days_until_trial_expiry
  const grace = school.is_in_grace_period
  const text = grace
    ? `⚠️ Your trial has expired. You have ${Math.max(0, 3 + (days || 0))} days left before your account is locked. Contact us to upgrade and avoid disruption.`
    : `Trial: ${days ?? 0} days remaining.`

  return (
    <div className={grace ? 'bg-red-50 border-b border-red-200 px-6 py-2 text-sm text-red-700' : 'bg-yellow-50 border-b border-yellow-200 px-6 py-2 text-sm text-yellow-800'}>
      <div className="flex items-center justify-between gap-4">
        <span>{text}</span>
        <a className="font-semibold underline" href="mailto:support@yourapp.co.ke">
          {grace ? 'Contact Support' : 'Upgrade Now'}
        </a>
      </div>
    </div>
  )
}
