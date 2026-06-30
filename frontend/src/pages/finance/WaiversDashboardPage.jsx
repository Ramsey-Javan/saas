import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { financeApi, subscribeToWaiverUpdates } from '@/api/finance'
import { Card, Button, Spinner, Badge } from '@/components/ui'
import { Plus, ChevronRight, AlertCircle } from 'lucide-react'
import WaiverStudentsModal from '@/components/finance/WaiverStudentsModal'

const formatMoney = (value) => `KES ${parseFloat(value || 0).toLocaleString()}`

export default function WaiversDashboardPage() {
  const navigate = useNavigate()
  const [policies, setPolicies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedPolicy, setSelectedPolicy] = useState(null)
  const [showStudentsModal, setShowStudentsModal] = useState(false)

  const loadPolicies = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true)
    setError('')
    try {
      const res = await financeApi.getWaiverPoliciesDashboard()
      const nextPolicies = res.data.results || res.data || []
      setPolicies(nextPolicies)
      setSelectedPolicy((current) => {
        if (!current) return current
        return nextPolicies.find((policy) => policy.id === current.id) || current
      })
    } catch (err) {
      setError('Failed to load waiver policies.')
      console.error(err)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPolicies()
  }, [loadPolicies])

  useEffect(() => {
    const handleRefresh = () => {
      if (document.visibilityState && document.visibilityState !== 'visible') return
      loadPolicies({ silent: true })
    }
    const unsubscribeWaiverUpdates = subscribeToWaiverUpdates(handleRefresh)

    window.addEventListener('focus', handleRefresh)
    document.addEventListener('visibilitychange', handleRefresh)

    return () => {
      window.removeEventListener('focus', handleRefresh)
      document.removeEventListener('visibilitychange', handleRefresh)
      unsubscribeWaiverUpdates()
    }
  }, [loadPolicies])

  const handlePolicyClick = (policy) => {
    setSelectedPolicy(policy)
    setShowStudentsModal(true)
  }

  const handleStudentsUpdate = async () => {
    // Reload policies after student waivers are updated
    await loadPolicies({ silent: true })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Waivers Dashboard</h1>
          <p className="text-gray-600">Manage active waiver policies and assigned students</p>
        </div>
        <Button onClick={() => navigate('/finance/waiver-policies')} variant="secondary">
          <Plus className="w-4 h-4 mr-2" />
          New Policy
        </Button>
      </div>

      {/* Error Message */}
      {error && (
        <Card className="p-4 bg-red-50 border border-red-200">
          <div className="flex items-center gap-3 text-red-700">
            <AlertCircle className="w-5 h-5" />
            <span>{error}</span>
          </div>
        </Card>
      )}

      {/* Loading State */}
      {loading ? (
        <Card className="p-8 flex justify-center">
          <Spinner />
        </Card>
      ) : policies.length === 0 ? (
        <Card className="p-8 text-center">
          <div className="text-gray-500">
            <p className="mb-4">No active waiver policies found.</p>
            <Button onClick={() => navigate('/finance/waiver-policies')}>
              Create First Policy
            </Button>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {policies.map((policy) => (
            <Card
              key={policy.id}
              className="p-6 cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => handlePolicyClick(policy)}
            >
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="font-semibold text-lg text-gray-900">
                    {policy.category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </h3>
                  {policy.description && (
                    <p className="text-sm text-gray-600 mt-1">{policy.description}</p>
                  )}
                </div>
                <Badge variant="success">Active</Badge>
              </div>

              <div className="space-y-3">
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-600">Discount</p>
                  <p className="text-xl font-bold text-gray-900">
                    {policy.discount_type === 'percentage'
                      ? `${policy.discount_value}%`
                      : formatMoney(policy.discount_value)
                    }
                  </p>
                </div>

                <div className="p-3 bg-[var(--brand-primary-light)] rounded-lg">
                  <p className="text-sm text-[var(--brand-primary)]">Students Assigned</p>
                  <p className="text-2xl font-bold text-[var(--brand-primary)]">
                    {policy.student_count || 0}
                  </p>
                </div>
              </div>

              <button className="w-full mt-4 px-4 py-2 flex items-center justify-between text-sm font-medium text-[var(--brand-primary)] hover:bg-[var(--brand-primary-light)] rounded-lg transition-colors">
                <span>View Students</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </Card>
          ))}
        </div>
      )}

      {/* Students Modal */}
      {selectedPolicy && (
        <WaiverStudentsModal
          isOpen={showStudentsModal}
          onClose={() => setShowStudentsModal(false)}
          policy={selectedPolicy}
          onUpdate={handleStudentsUpdate}
        />
      )}
    </div>
  )
}
