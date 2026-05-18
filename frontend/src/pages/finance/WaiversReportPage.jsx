import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { financeApi, subscribeToWaiverUpdates } from '@/api/finance'
import { Card, Button, Spinner } from '@/components/ui'

const CATEGORY_CHOICES = [
  { value: 'full_waiver', label: 'Full Waiver' },
  { value: 'staff_child', label: 'Staff Child' },
  { value: 'bursary', label: 'Bursary' },
  { value: 'sibling', label: 'Sibling Discount' },
  { value: 'sponsor', label: 'Sponsor' },
  { value: 'partial', label: 'Partial Waiver' },
  { value: 'orphan', label: 'Orphan' },
]

const categoryMap = new Map(CATEGORY_CHOICES.map(c => [c.value, c.label]))
const formatMoney = (value) => `KES ${parseFloat(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export default function WaiversReportPage() {
  const [tabs, setTabs] = useState([])
  const [activeTab, setActiveTab] = useState('all')
  const [waivers, setWaivers] = useState([])
  const [summary, setSummary] = useState({})
  const [loading, setLoading] = useState(true)
  const [tableLoading, setTableLoading] = useState(false)
  const [message, setMessage] = useState('')

  const navigate = useNavigate()

  const loadDashboardAndSummary = useCallback(async () => {
    try {
      const [dashRes, reportRes] = await Promise.all([
        financeApi.getWaiverPoliciesDashboard(),
        financeApi.getWaiverReport(),
      ])
      
      const policies = dashRes.data.results || dashRes.data || []
      const activePolicies = policies.filter(p => p.student_count > 0)
      
      const tabList = [
        { id: 'all', label: `All (${policies.reduce((sum, p) => sum + p.student_count, 0)})` },
        ...activePolicies.map(p => ({
          id: p.id,
          label: `${p.category} (${p.student_count})`,
        })),
      ]
      
      setTabs(tabList)
      setSummary(reportRes.data || {})
      
      setActiveTab((current) => current || 'all')
    } catch (err) {
      setMessage('Failed to load waiver policies.')
      console.error(err)
    }
  }, [])

  const loadWaivers = useCallback(async (tabId) => {
    setTableLoading(true)
    try {
      let res
      if (tabId === 'all') {
        res = await financeApi.getWaivers({ is_active: true })
      } else {
        res = await financeApi.getWaiversByPolicy(tabId)
      }
      setWaivers(res.data.results || res.data || [])
    } catch (err) {
      setMessage('Failed to load waivers.')
      console.error(err)
    } finally {
      setTableLoading(false)
    }
  }, [])

  useEffect(() => {
    const loadInitial = async () => {
      setLoading(true)
      await loadDashboardAndSummary()
      setLoading(false)
    }
    loadInitial()
  }, [loadDashboardAndSummary])

  useEffect(() => {
    if (activeTab) {
      loadWaivers(activeTab)
    }
  }, [activeTab, loadWaivers])

  useEffect(() => {
    const handleRefresh = () => {
      if (document.visibilityState && document.visibilityState !== 'visible') return
      loadDashboardAndSummary()
      loadWaivers(activeTab)
    }
    const unsubscribeWaiverUpdates = subscribeToWaiverUpdates(handleRefresh)

    window.addEventListener('focus', handleRefresh)
    document.addEventListener('visibilitychange', handleRefresh)

    return () => {
      window.removeEventListener('focus', handleRefresh)
      document.removeEventListener('visibilitychange', handleRefresh)
      unsubscribeWaiverUpdates()
    }
  }, [activeTab, loadDashboardAndSummary, loadWaivers])

  const handleExportCSV = () => {
    if (waivers.length === 0) {
      alert('No waivers to export.')
      return
    }

    const headers = [
      'Student Name',
      'Admission No.',
      'Class',
      'Category',
      'Original Fee',
      'Waiver Amount',
      'Net Due',
      'Amount Paid',
      'Balance',
      'Valid Until',
      'Approved By',
    ]
    
    const rows = waivers.map(w => [
      w.student_name,
      w.admission_number,
      w.classroom_name,
      categoryMap.get(w.policy_category) || w.policy_category,
      w.invoice_original_amount,
      w.invoice_waived_amount,
      w.invoice_net_due,
      w.invoice_paid,
      w.invoice_balance,
      w.valid_until_year ? `${w.valid_until_term} ${w.valid_until_year}` : 'Permanent',
      w.approved_by_name,
    ])

    const csv = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(',')),
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `waivers-report-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    window.URL.revokeObjectURL(url)
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-7 w-7" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {message && (
        <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
          {message}
        </div>
      )}

      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Waivers Report</h1>
          <p className="text-gray-600">Overview of active student fee waivers</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => navigate('/finance/waiver-policies')}>
            Waiver Policies
          </Button>
          <Button onClick={handleExportCSV} disabled={waivers.length === 0}>
            Export CSV
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <div className="text-center">
            <div className="text-4xl font-bold text-blue-600">{summary.total_students_with_waivers || 0}</div>
            <div className="text-gray-600 mt-2">Students with Active Waivers</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-4xl font-bold text-green-600">{formatMoney(summary.total_waived_amount)}</div>
            <div className="text-gray-600 mt-2">Total Waived Amount</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-4xl font-bold text-purple-600">{tabs.length - 1}</div>
            <div className="text-gray-600 mt-2">Active Policies</div>
          </div>
        </Card>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <div className="flex gap-4 overflow-x-auto">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'text-blue-600 border-blue-600'
                  : 'text-gray-600 border-transparent hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <Card>
        {tableLoading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : waivers.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No waivers found for this category.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-900">Student Name</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-900">Adm No.</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-900">Class</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-900">Category</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-900">Original Fee</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-900">Waiver Amount</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-900">Net Due</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-900">Paid</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-900">Balance</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-900">Valid Until</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-900">Approved By</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {waivers.map((waiver) => (
                  <tr key={waiver.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-900 font-medium">{waiver.student_name}</td>
                    <td className="px-4 py-3 text-gray-600">{waiver.admission_number}</td>
                    <td className="px-4 py-3 text-gray-600">{waiver.classroom_name}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium">
                        {categoryMap.get(waiver.policy_category) || waiver.policy_category}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-900 text-right">{formatMoney(waiver.invoice_original_amount)}</td>
                    <td className="px-4 py-3 text-green-600 font-semibold text-right">{formatMoney(waiver.invoice_waived_amount)}</td>
                    <td className="px-4 py-3 text-gray-900 text-right">{formatMoney(waiver.invoice_net_due)}</td>
                    <td className="px-4 py-3 text-gray-600 text-right">{formatMoney(waiver.invoice_paid)}</td>
                    <td className={`px-4 py-3 text-right font-semibold ${parseFloat(waiver.invoice_balance) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                      {formatMoney(waiver.invoice_balance)}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {waiver.valid_until_year
                        ? `${waiver.valid_until_term} ${waiver.valid_until_year}`
                        : <span className="text-green-600 font-medium">Permanent</span>
                      }
                    </td>
                    <td className="px-4 py-3 text-gray-600">{waiver.approved_by_name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
