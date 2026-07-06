import { useEffect, useState } from 'react'
import { financeApi } from '@/api/finance'
import { Button, Input, Select, Spinner } from '@/components/ui'
import { CheckCircle, AlertCircle, Download, X, Info } from 'lucide-react'
import MpesaPaymentModal from './MpesaPaymentModal'

const BANKS = ['KCB', 'Equity', 'Co-op', 'NCBA', 'Absa', 'Standard Chartered', 'Other']

const todayISO = () => new Date().toISOString().slice(0, 10)

export default function PaymentModal({ isOpen, onClose, student, fee, onSuccess }) {
  const [activeTab, setActiveTab] = useState('mpesa')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const [cashAmount, setCashAmount] = useState('')
  const [cashDate, setCashDate] = useState(todayISO())
  const [cashNotes, setCashNotes] = useState('')
  const [cashSms, setCashSms] = useState(true)

  const [bankAmount, setBankAmount] = useState('')
  const [bankDate, setBankDate] = useState(todayISO())
  const [bankName, setBankName] = useState('')
  const [bankRef, setBankRef] = useState('')
  const [bankNotes, setBankNotes] = useState('')
  const [bankSms, setBankSms] = useState(true)

  const [chequeAmount, setChequeAmount] = useState('')
  const [chequeDate, setChequeDate] = useState(todayISO())
  const [chequeNumber, setChequeNumber] = useState('')
  const [chequeBank, setChequeBank] = useState('')
  const [drawerName, setDrawerName] = useState('')
  const [chequeNotes, setChequeNotes] = useState('')

  useEffect(() => {
    if (!isOpen) {
      setActiveTab('mpesa')
      setResult(null)
      setError('')
      return
    }
    const nextAmount = fee?.effective_balance ?? fee?.balance ?? ''
    setCashAmount(nextAmount)
    setBankAmount(nextAmount)
    setChequeAmount(nextAmount)
    setCashDate(todayISO())
    setBankDate(todayISO())
    setChequeDate(todayISO())
    setCashNotes('')
    setBankNotes('')
    setChequeNotes('')
    setBankName('')
    setBankRef('')
    setChequeNumber('')
    setChequeBank('')
    setDrawerName('')
    setCashSms(true)
    setBankSms(true)
    setResult(null)
    setError('')
  }, [isOpen, fee])

  if (!isOpen) return null

  const refreshSuccess = (data) => {
    onSuccess?.(data)
  }

  const extractError = (data) => {
    if (!data) return 'Failed to record payment.'
    if (data.error) return data.error
    if (data.detail) return data.detail
    if (typeof data === 'string') return data
    const firstKey = Object.keys(data)[0]
    if (!firstKey) return 'Failed to record payment.'
    const value = data[firstKey]
    return Array.isArray(value) ? value[0] : value
  }

  const handleDownloadReceipt = async (paymentId) => {
    if (!paymentId) return
    const res = await financeApi.downloadReceipt(paymentId)
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    window.open(url, '_blank', 'noopener,noreferrer')
    window.URL.revokeObjectURL(url)
  }

  // ── BUG FIX (reverted): the previous version capped amount at
  // balance + credit and rejected anything higher. That directly
  // contradicted this same modal's own helper text ("Any excess beyond
  // the balance will be credited to the next term") -- overpayment isn't
  // an error state, it's a fully-supported feature. recalculate_student_fees()
  // on the backend already caps paid_amount at what's due and rolls the
  // surplus into `credit`, cascading correctly to future invoices. The
  // only thing worth validating client-side is that the amount is a
  // real, positive number -- the backend is the source of truth for
  // anything more nuanced.
  const validateAmount = (amount) => {
    const numAmount = parseFloat(amount)
    if (isNaN(numAmount) || numAmount <= 0) {
      return 'Please enter a valid positive amount.'
    }
    return null
  }
  // ── END BUG FIX ──

  const handleManualPayment = async (method) => {
    if (!fee?.id) return
    setError('')
    setResult(null)
    setLoading(true)

    const rawAmount = method === 'cash' ? cashAmount : method === 'bank' ? bankAmount : chequeAmount

    const validationError = validateAmount(rawAmount)
    if (validationError) {
      setError(validationError)
      setLoading(false)
      return
    }

    try {
      const payload = {
        invoice_id: fee.id,
        amount: String(rawAmount),
        method,
        date: method === 'cash' ? cashDate : method === 'bank' ? bankDate : chequeDate,
        notes: method === 'cash' ? cashNotes : method === 'bank' ? bankNotes : chequeNotes,
      }
      if (method === 'cash') {
        payload.send_sms = cashSms
      }
      if (method === 'bank') {
        payload.bank_name = bankName
        payload.bank_reference = bankRef
        payload.send_sms = bankSms
      }
      if (method === 'cheque') {
        payload.bank_name = chequeBank
        payload.cheque_number = chequeNumber
        payload.drawer_name = drawerName
      }

      const res = await financeApi.recordManualPayment(payload)
      const receiptNumber = res.data.receipt_number
      const paymentId = res.data.payment?.id
      const credit = parseFloat(res.data.updated_invoice?.credit || 0)
      setResult({
        status: res.data.payment?.status,
        receiptNumber,
        paymentId,
        credit,
        message: res.data.payment?.status === 'pending'
          ? 'Cheque recorded and marked as pending.'
          : credit > 0
            ? `Payment recorded. KES ${credit.toLocaleString()} credit will be applied to the next term invoice.`
          : 'Payment recorded successfully.'
      })
      refreshSuccess({ paymentId, receiptNumber })
    } catch (err) {
      setError(extractError(err.response?.data))
    } finally {
      setLoading(false)
    }
  }

  const renderSuccess = () => (
    <div className="text-center py-6 space-y-3">
      {result?.status === 'pending' ? (
        <AlertCircle size={48} className="text-yellow-500 mx-auto" />
      ) : (
        <CheckCircle size={48} className="text-green-500 mx-auto" />
      )}
      <div>
        <p className={`font-bold ${result?.status === 'pending' ? 'text-yellow-700' : 'text-green-700'}`}>
          {result?.message}
        </p>
        {result?.receiptNumber && (
          <p className="text-sm text-gray-600 mt-1">
            Receipt: <span className="font-mono font-medium">{result.receiptNumber}</span>
          </p>
        )}
      </div>
      <div className="flex items-center justify-center gap-2">
        {result?.receiptNumber && (
          <Button variant="secondary" className="gap-2" onClick={() => handleDownloadReceipt(result.paymentId)}>
            <Download size={16} /> Download Receipt
          </Button>
        )}
        <Button onClick={onClose}>Close</Button>
      </div>
    </div>
  )

  const tabButton = (value, label) => (
    <button
      type="button"
      onClick={() => { setActiveTab(value); setResult(null); setError('') }}
  className={`px-3 py-2 text-sm rounded-lg font-medium ${activeTab === value ? 'bg-[var(--brand-primary)] text-white' : 'bg-gray-100 text-gray-700'}`}
    >
      {label}
    </button>
  )

  // ── BUG FIX (reverted): this was labeled "maximum payable" but that
  // framing no longer applies now that overpayment is allowed -- it's
  // just the current balance. Kept as a helper display of the balance
  // itself, not a hard ceiling.
  const currentBalanceDisplay = () => {
    return parseFloat(fee?.effective_balance ?? fee?.balance ?? 0)
  }
  // ── END BUG FIX ──

  // Live "you're paying extra" notice -- reacts to whatever amount is
  // currently typed in, rather than only being visible after the fact on
  // the success screen. Returns null when the amount is at or under the
  // balance (nothing extra to flag).
  const overpaymentNotice = (amountValue) => {
    const balance = currentBalanceDisplay()
    const numAmount = parseFloat(amountValue)
    if (isNaN(numAmount) || numAmount <= balance) return null
    const excess = numAmount - balance
    return `You're paying KES ${excess.toLocaleString()} more than the balance. This extra amount will be carried forward as credit to the next term.`
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-lg max-w-lg w-full p-6 relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600">
          <X size={20} />
        </button>

        <div className="flex flex-wrap gap-2 mb-4">
          {tabButton('mpesa', 'M-Pesa')}
          {tabButton('cash', 'Cash')}
          {tabButton('bank', 'Bank Transfer')}
          {tabButton('cheque', 'Cheque')}
        </div>

        {error && (
          <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm">
            {error}
          </div>
        )}

        {result ? renderSuccess() : (
          <>
            {activeTab === 'mpesa' && (
              <MpesaPaymentModal
                isOpen={isOpen}
                onClose={onClose}
                student={student}
                fee={fee}
                onSuccess={refreshSuccess}
                mode="tab"
              />
            )}

            {activeTab === 'cash' && (
              <div className="space-y-4">
                <Input
                  label="Amount (KES)"
                  type="number"
                  value={cashAmount}
                  onChange={e => setCashAmount(e.target.value)}
                />
                <p className="text-xs text-gray-500 -mt-2">
                  Current balance: KES {currentBalanceDisplay().toLocaleString()}.
                  Any amount paid beyond the balance will be credited to the next term.
                </p>
                {overpaymentNotice(cashAmount) && (
                  <div className="flex items-center gap-2 text-xs text-blue-700 bg-blue-50 px-3 py-2 rounded-lg -mt-1">
                    <Info size={14} className="flex-shrink-0" /> {overpaymentNotice(cashAmount)}
                  </div>
                )}
                <Input
                  label="Date"
                  type="date"
                  value={cashDate}
                  onChange={e => setCashDate(e.target.value)}
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Notes</label>
                  <textarea
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm outline-none focus:ring-2 focus:ring-[var(--brand-primary-ring)] focus:border-[var(--brand-primary)]"
                    placeholder="Optional"
                    rows={3}
                    value={cashNotes}
                    onChange={e => setCashNotes(e.target.value)}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={cashSms}
                    onChange={e => setCashSms(e.target.checked)}
                  />
                  Send SMS confirmation
                </label>
                <Button
                  onClick={() => handleManualPayment('cash')}
                  loading={loading}
                  className="w-full"
                >
                  Record Cash Payment
                </Button>
              </div>
            )}

            {fee && (parseFloat(fee.effective_balance || fee.balance || 0) === 0) && (
              <div className="mb-4 px-4 py-3 rounded-lg bg-blue-50 text-blue-700 text-sm">
                This invoice is fully paid. Any additional amount will be credited to the next term invoice.
              </div>
            )}

            {activeTab === 'bank' && (
              <div className="space-y-4">
                <Input
                  label="Amount (KES)"
                  type="number"
                  value={bankAmount}
                  onChange={e => setBankAmount(e.target.value)}
                />
                <p className="text-xs text-gray-500 -mt-2">
                  Current balance: KES {currentBalanceDisplay().toLocaleString()}.
                  Any amount paid beyond the balance will be credited to the next term.
                </p>
                {overpaymentNotice(bankAmount) && (
                  <div className="flex items-center gap-2 text-xs text-blue-700 bg-blue-50 px-3 py-2 rounded-lg -mt-1">
                    <Info size={14} className="flex-shrink-0" /> {overpaymentNotice(bankAmount)}
                  </div>
                )}
                <Input
                  label="Date"
                  type="date"
                  value={bankDate}
                  onChange={e => setBankDate(e.target.value)}
                />
                <Select label="Bank Name" value={bankName} onChange={e => setBankName(e.target.value)}>
                  <option value="">Select bank</option>
                  {BANKS.map(bank => (
                    <option key={bank} value={bank}>{bank}</option>
                  ))}
                </Select>
                <Input
                  label="Bank Reference Number"
                  value={bankRef}
                  onChange={e => setBankRef(e.target.value)}
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Notes</label>
                  <textarea
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm outline-none focus:ring-2 focus:ring-[var(--brand-primary-ring)] focus:border-[var(--brand-primary)]"
                    placeholder="Optional"
                    rows={3}
                    value={bankNotes}
                    onChange={e => setBankNotes(e.target.value)}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={bankSms}
                    onChange={e => setBankSms(e.target.checked)}
                  />
                  Send SMS confirmation
                </label>
                <Button
                  onClick={() => handleManualPayment('bank')}
                  loading={loading}
                  className="w-full"
                >
                  Record Bank Payment
                </Button>
              </div>
            )}

            {activeTab === 'cheque' && (
              <div className="space-y-4">
                <Input
                  label="Amount (KES)"
                  type="number"
                  value={chequeAmount}
                  onChange={e => setChequeAmount(e.target.value)}
                />
                <p className="text-xs text-gray-500 -mt-2">
                  Current balance: KES {currentBalanceDisplay().toLocaleString()}.
                  Any amount paid beyond the balance will be credited to the next term.
                </p>
                {overpaymentNotice(chequeAmount) && (
                  <div className="flex items-center gap-2 text-xs text-blue-700 bg-blue-50 px-3 py-2 rounded-lg -mt-1">
                    <Info size={14} className="flex-shrink-0" /> {overpaymentNotice(chequeAmount)}
                  </div>
                )}
                <Input
                  label="Cheque Date"
                  type="date"
                  value={chequeDate}
                  onChange={e => setChequeDate(e.target.value)}
                />
                <Input
                  label="Cheque Number"
                  value={chequeNumber}
                  onChange={e => setChequeNumber(e.target.value)}
                />
                <Select label="Bank Name" value={chequeBank} onChange={e => setChequeBank(e.target.value)}>
                  <option value="">Select bank</option>
                  {BANKS.map(bank => (
                    <option key={bank} value={bank}>{bank}</option>
                  ))}
                </Select>
                <Input
                  label="Drawer Name"
                  value={drawerName}
                  onChange={e => setDrawerName(e.target.value)}
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Notes</label>
                  <textarea
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm outline-none focus:ring-2 focus:ring-[var(--brand-primary-ring)] focus:border-[var(--brand-primary)]"
                    placeholder="Optional"
                    rows={3}
                    value={chequeNotes}
                    onChange={e => setChequeNotes(e.target.value)}
                  />
                </div>
                <div className="flex items-center gap-2 text-xs text-yellow-700 bg-yellow-50 px-3 py-2 rounded-lg">
                  <Info size={14} /> Cheque will be marked as pending until cleared
                </div>
                <Button
                  onClick={() => handleManualPayment('cheque')}
                  loading={loading}
                  className="w-full"
                >
                  Record Cheque
                </Button>
              </div>
            )}

            {loading && (
              <div className="mt-4 flex items-center justify-center text-xs text-gray-500">
                <Spinner className="h-4 w-4" />
                <span className="ml-2">Recording payment...</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}