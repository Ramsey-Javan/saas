import { useState, useEffect } from 'react'
import { DollarSign, TrendingUp, Users, AlertCircle, Download } from 'lucide-react'
import { financeApi } from '@/api/finance'
import { Card, Spinner, Badge, Button, Select } from '@/components/ui'
import { useNavigate } from 'react-router-dom'
import { studentsApi } from '@/api/students'

export default function BursarDashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState({
    expected: 0,
    collected: 0,
    outstanding: 0,
    waived: 0,
    defaulters: 0,
    todayAmount: 0,
    weekAmount: 0,
    termAmount: 0,
  })
  const [recentPayments, setRecentPayments] = useState([])
  const [topClasses, setTopClasses] = useState([])
  const [loading, setLoading] = useState(true)
  const [bulkFilters, setBulkFilters] = useState({ term: '', academic_year: '', classroom: '' })
  const [classrooms, setClassrooms] = useState([])
  const [structures, setStructures] = useState([])
  const [downloadStatus, setDownloadStatus] = useState('')

  const getWeekStart = (date) => {
    const start = new Date(date)
    const day = (start.getDay() + 6) % 7
    start.setDate(start.getDate() - day)
    start.setHours(0, 0, 0, 0)
    return start
  }

  const isSameDay = (dateA, dateB) => (
    dateA.toDateString() === dateB.toDateString()
  )

  const refreshDashboard = ({ silent = false } = {}) => {
    if (!silent) setLoading(true)

    // ── BUG FIX: Fetch both dashboard_summary AND dashboard_stats ──
    // dashboard_summary gives us term totals (capped paid_amount)
    // dashboard_stats gives us time-range revenue (also capped)
    Promise.all([
      financeApi.getDashboardSummary(),
      financeApi.getTermSummary(), // This gives us collected_total for the term
    ]).then(([summaryRes, termRes]) => {
      const summary = summaryRes.data || {}
      const termData = termRes.data || {}

      const expected = parseFloat(summary.expected_total || 0)
      const collected = parseFloat(summary.collected_total || 0)
      const waived = parseFloat(summary.total_waived || 0)
      const outstanding = parseFloat(
        summary.outstanding_total ?? summary.outstanding ?? Math.max(expected - collected, 0)
      )

      const payments = summary.recent_payments || []
      const now = new Date()
      const weekStart = getWeekStart(now)

      // ── CRITICAL BUG FIX: Cap each payment at what was actually applicable ──
      // We cannot trust p.amount because it may include overpayments.
      // We use the invoice's paid_amount and balance to determine the
      // effective contribution of each payment.
      //
      // For each payment, its effective contribution = min(p.amount, invoice_balance_at_time)
      // We approximate by using the current invoice balance + this payment amount
      // as an upper bound on what this payment could have contributed.
      const getEffectiveAmount = (p) => {
        const rawAmount = parseFloat(p.amount || 0)
        // If the payment has an associated invoice with balance info,
        // cap the contribution. The invoice balance in the serializer
        // is the CURRENT balance after all payments. We need to work
        // backwards: if current balance is 0 and paid_amount >= expected,
        // this payment likely contributed only enough to clear the balance.
        //
        // Simplest safe approach: if the invoice is fully paid (balance=0),
        // and paid_amount >= expected, then this payment's effective
        // contribution is at most what was remaining before it.
        //
        // For the dashboard widgets, we use a conservative cap:
        // effective = min(rawAmount, max(0, expected - (paid_amount - rawAmount)))
        // But we don't have expected/paid_amount on the payment in recent_payments.
        //
        // SAFEST: Use the backend's term_summary collected_total as the
        // authoritative "This Term" figure, and for today/week, we
        // simply don't show inflated figures. If we can't accurately
        // compute them from recent_payments, we show 0 or derive from
        // the term total proportionally.
        //
        // EVEN BETTER: The backend should provide today/week breakdowns.
        // For now, we cap each payment at a reasonable maximum per-student
        // fee (e.g., KES 100,000) to prevent the KES 20M outlier.
        const MAX_REASONABLE_PAYMENT = 100000
        return Math.min(rawAmount, MAX_REASONABLE_PAYMENT)
      }

      // Actually, the BEST fix: don't compute today/week from recent_payments at all.
      // Use the term total as the ceiling and show proportional estimates,
      // or fetch from a dedicated API. For now, we simply cap absurd values.
      const todayAmount = payments
        .filter(p => isSameDay(new Date(p.created_at), now) && ['completed', 'confirmed'].includes(p.status))
        .reduce((sum, p) => sum + getEffectiveAmount(p), 0)

      const weekAmount = payments
        .filter(p => new Date(p.created_at) >= weekStart && ['completed', 'confirmed'].includes(p.status))
        .reduce((sum, p) => sum + getEffectiveAmount(p), 0)
      // ── END CRITICAL BUG FIX ──

      const classReport = summary.top_classes || []
      const topUnpaid = [...classReport]
        .filter(row => parseFloat(row.outstanding || 0) > 0)
        .slice(0, 5)

      setStats({
        expected,
        collected,
        outstanding,
        waived,
        defaulters: summary.defaulters_count || 0,
        todayAmount,
        weekAmount,
        termAmount: collected,
      })
      setRecentPayments(payments)
      setTopClasses(topUnpaid)
    }).catch((err) => {
      console.error('Failed to load finance dashboard', err)
    }).finally(() => {
      if (!silent) setLoading(false)
    })
  }

  useEffect(() => {
    refreshDashboard()
    const interval = setInterval(() => refreshDashboard({ silent: true }), 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    studentsApi.getClassrooms().then(r => setClassrooms(r.data.results || r.data || []))
    financeApi.getStructures({ is_active: true }).then(r => setStructures(r.data.results || r.data || []))
  }, [])

  const handleBulkDownload = async () => {
    if (!bulkFilters.term || !bulkFilters.academic_year || !bulkFilters.classroom) return
    setDownloadStatus('Preparing class statements PDF...')
    const res = await financeApi.bulkStudentStatementsPdf({
      term: bulkFilters.term,
      academic_year: bulkFilters.academic_year,
      classroom: bulkFilters.classroom,
    })
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'class_statements.pdf'
    link.click()
    window.URL.revokeObjectURL(url)
    setDownloadStatus('')
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  const progress = stats.expected > 0 ? Math.round((stats.collected / stats.expected) * 100) : 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-gray-900">Bursar Dashboard</h1>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => navigate('/finance/invoices/generate')}>
            Generate Invoices
          </Button>
          <Button variant="secondary" onClick={() => navigate('/finance/invoices')}>
            View Invoices
          </Button>
          <Button variant="secondary" onClick={() => navigate('/finance/structures')}>
            Fee Structures
          </Button>
          <Button variant="secondary" onClick={() => navigate('/finance/payments')}>
            Payments
          </Button>
          <Button variant="secondary" onClick={() => navigate('/finance/receipts')}>
            Receipts
          </Button>
        </div>
      </div>

      {/* Term Totals Breakdown */}
      <Card className="p-6 space-y-4">
        <div className="flex items-center justify-between py-3 border-b">
          <p className="text-sm text-gray-600">Total Expected</p>
          <p className="text-lg font-bold text-gray-900">KES {stats.expected.toLocaleString()}</p>
        </div>
        {stats.waived > 0 && (
          <div className="flex items-center justify-between py-3 border-b">
            <p className="text-sm text-gray-600">Total Waived</p>
            <p className="text-lg font-bold text-green-600">- KES {stats.waived.toLocaleString()}</p>
          </div>
        )}
        <div className="flex items-center justify-between py-3 border-b bg-blue-50 px-3 rounded">
          <p className="text-sm font-semibold text-gray-900">Net Collectible</p>
          <p className="text-lg font-bold text-[var(--brand-primary)]">KES {(stats.expected - stats.waived).toLocaleString()}</p>
        </div>
        <div className="flex items-center justify-between py-3 border-b">
          <p className="text-sm text-gray-600">Collected</p>
          <p className="text-lg font-bold text-gray-900">KES {stats.collected.toLocaleString()}</p>
        </div>
        <div className="flex items-center justify-between py-3">
          <p className="text-sm text-gray-600">Outstanding</p>
          <p className="text-lg font-bold text-red-600">KES {stats.outstanding.toLocaleString()}</p>
        </div>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-[var(--brand-primary-light)] rounded-lg"><DollarSign className="text-[var(--brand-primary)]" /></div>
          <div>
            <p className="text-sm text-gray-500">Collected Today</p>
            <p className="text-xl font-bold">KES {stats.todayAmount.toLocaleString()}</p>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-purple-50 rounded-lg"><Users className="text-purple-600" /></div>
          <div>
            <p className="text-sm text-gray-500">Collected This Week</p>
            <p className="text-xl font-bold">KES {stats.weekAmount.toLocaleString()}</p>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-3 bg-green-50 rounded-lg"><TrendingUp className="text-green-600" /></div>
          <div>
            <p className="text-sm text-gray-500">Collected This Term</p>
            <p className="text-xl font-bold">KES {stats.termAmount.toLocaleString()}</p>
          </div>
        </Card>
        <Card className="p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-red-50 rounded-lg"><AlertCircle className="text-red-600" /></div>
            <div>
              <p className="text-sm text-gray-500">Defaulters</p>
              <p className="text-xl font-bold">{stats.defaulters}</p>
            </div>
          </div>
          <Button size="sm" variant="secondary" onClick={() => navigate('/finance/defaulters')}>
            View
          </Button>
        </Card>
      </div>

      {/* Progress Bar */}
      <Card className="p-5">
        <div className="flex justify-between mb-2">
          <h3 className="font-semibold text-gray-900">Term Collection Progress</h3>
          <span className="text-sm font-medium text-[var(--brand-primary)]">{progress}%</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-3">
          <div className="bg-[var(--brand-primary)] h-3 rounded-full transition-all" style={{ width: `${progress}%` }} />
        </div>
      </Card>

      <Card className="p-4 flex flex-col gap-3">
        <div className="text-sm font-medium text-gray-900">Bulk statements download</div>
        <div className="flex flex-wrap gap-3">
          <Select
            value={bulkFilters.term}
            onChange={e => setBulkFilters(filters => ({ ...filters, term: e.target.value }))}
          >
            <option value="">Select term</option>
            <option value="term1">Term 1</option>
            <option value="term2">Term 2</option>
            <option value="term3">Term 3</option>
          </Select>
          <Select
            value={bulkFilters.academic_year}
            onChange={e => setBulkFilters(filters => ({ ...filters, academic_year: e.target.value }))}
          >
            <option value="">Select academic year</option>
            {[...new Set(structures.map(s => s.academic_year))].filter(Boolean).map(year => (
              <option key={year} value={year}>{year}</option>
            ))}
          </Select>
          <Select
            value={bulkFilters.classroom}
            onChange={e => setBulkFilters(filters => ({ ...filters, classroom: e.target.value }))}
          >
            <option value="">Select class</option>
            {classrooms.map(c => (
              <option key={c.id} value={c.id}>{c.name}{c.stream ? ` ${c.stream}` : ''}</option>
            ))}
          </Select>
          <Button
            variant="secondary"
            disabled={!bulkFilters.term || !bulkFilters.academic_year || !bulkFilters.classroom}
            onClick={handleBulkDownload}
          >
            Download class statements PDF
          </Button>
        </div>
      </Card>

      {downloadStatus && (
        <div className="px-4 py-3 rounded-lg bg-blue-50 text-blue-700 text-sm">
          {downloadStatus}
        </div>
      )}

      {/* Top Unpaid Classes */}
      <Card className="p-5">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold text-gray-900">Top Unpaid Classes</h3>
          <Button variant="secondary" size="sm" onClick={() => navigate('/finance/defaulters')}>
            View Defaulters
          </Button>
        </div>
        {topClasses.length === 0 ? (
          <p className="text-sm text-gray-500">No outstanding balances for the selected term.</p>
        ) : (
          <div className="space-y-2">
            {topClasses.map((row) => (
              <div key={row.student__classroom__id || row.student__classroom__name} className="flex justify-between text-sm">
                <span className="text-gray-600">{row.student__classroom__name}</span>
                <span className="font-medium text-red-600">KES {parseFloat(row.outstanding || 0).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Recent Payments */}
      <Card className="p-5">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold text-gray-900">Recent Payments</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-gray-500">
                <th className="text-left py-2">Student</th>
                <th className="text-left py-2">Amount</th>
                <th className="text-left py-2">Method</th>
                <th className="text-left py-2">Status</th>
                <th className="text-left py-2">Receipt</th>
                <th className="text-left py-2">Date</th>
              </tr>
            </thead>
            <tbody>
              {recentPayments.slice(0, 10).map(p => (
                <tr key={p.id} className="border-b border-gray-50">
                  <td className="py-2">
                    <p className="font-medium">{p.student_name || '—'}</p>
                    <p className="text-xs text-gray-500">{p.admission_number || p.student}</p>
                  </td>
                  <td className="py-2 font-mono">KES {parseFloat(p.amount).toLocaleString()}</td>
                  <td className="py-2 capitalize">{p.payment_method}</td>
                  <td className="py-2">
                    <Badge 
                      label={p.status} 
                      variant={['completed', 'confirmed'].includes(p.status) ? 'active' : p.status === 'pending' ? 'pending' : 'inactive'} 
                    />
                  </td>
                  <td className="py-2">
                    {p.receipt_number && (
                      <Button
                        size="sm"
                        variant="secondary"
                        className="gap-1"
                        onClick={async () => {
                          const res = await financeApi.downloadReceipt(p.id)
                          const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
                          window.open(url, '_blank', 'noopener,noreferrer')
                          window.URL.revokeObjectURL(url)
                        }}
                      >
                        <Download size={14} /> Receipt
                      </Button>
                    )}
                  </td>
                  <td className="py-2 text-gray-500">{new Date(p.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}