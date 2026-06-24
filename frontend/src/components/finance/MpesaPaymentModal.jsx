import { useState, useEffect, useRef } from 'react'
import { financeApi } from '@/api/finance'
import { Button, Input, Spinner } from '@/components/ui'
import { X, Phone, CheckCircle, AlertCircle, Download } from 'lucide-react'

export default function MpesaPaymentModal({ isOpen, onClose, student, fee, onSuccess, mode = 'modal' }) {
  const [phone, setPhone] = useState('')
  const [amount, setAmount] = useState(fee?.balance || '')
  const [loading, setLoading] = useState(false)
  const [polling, setPolling] = useState(false)
  const [result, setResult] = useState(null)
  const [paymentId, setPaymentId] = useState(null)
  const pollRef = useRef(null)

  useEffect(() => {
    if (!isOpen) {
      setPhone(''); setResult(null); setPolling(false); setPaymentId(null)
      if (pollRef.current) clearInterval(pollRef.current)
    } else {
      setAmount(fee?.balance || '')
    }
  }, [isOpen, fee])

  const handlePay = async () => {
    if (!phone || !amount) return
    setLoading(true)
    try {
      const res = await financeApi.initiateMpesa({
        student: student.id,
        student_fee: fee?.id,
        amount: String(amount),
        phone: phone.startsWith('0') ? '254' + phone.slice(1) : phone,
        account_ref: student.admission_number,
        description: `School Fee Payment - ${student.admission_number}`
      })
      setPaymentId(res.data.payment_id)
      setResult({ status: 'waiting', message: res.data.message })
      setPolling(true)
      
      // Poll status every 3s for up to 2 mins
      let attempts = 0
      pollRef.current = setInterval(async () => {
        attempts++
        try {
          const statusRes = await financeApi.getPaymentStatus(res.data.payment_id)
          const st = statusRes.data.status
          
          if (st === 'completed') {
            setResult({ status: 'success', receipt: statusRes.data.receipt_number })
            clearInterval(pollRef.current)
            setPolling(false)
            setTimeout(() => onSuccess?.({ paymentId: res.data.payment_id, receiptNumber: statusRes.data.receipt_number }), 1500)
          } else if (st === 'cancelled') {
            setResult({ status: 'cancelled', message: statusRes.data.message || 'You cancelled the payment on your phone.' })
            clearInterval(pollRef.current)
            setPolling(false)
          } else if (st === 'expired') {
            setResult({ status: 'timeout', message: statusRes.data.message || 'Payment timed out. No response from your phone.' })
            clearInterval(pollRef.current)
            setPolling(false)
          } else if (st === 'failed') {
            setResult({ status: 'failed', message: statusRes.data.message || 'Payment failed. Please try again.' })
            clearInterval(pollRef.current)
            setPolling(false)
          }
          // pending = keep polling
        } catch (e) {
          // Ignore poll errors, keep trying
        }
        
        if (attempts >= 40) { // 2 minutes max
          clearInterval(pollRef.current)
          setPolling(false)
          setResult({ status: 'timeout', message: 'Payment confirmation timed out. Please check your M-Pesa messages and try again if needed.' })
        }
      }, 3000)
    } catch (err) {
      setResult({ status: 'failed', message: err.response?.data?.error || 'Initiation failed' })
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  const handleDownloadReceipt = async () => {
    if (!paymentId) return
    const res = await financeApi.downloadReceipt(paymentId)
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    window.open(url, '_blank', 'noopener,noreferrer')
    window.URL.revokeObjectURL(url)
  }

  const body = (
    <>
      <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
        <Phone size={20} className="text-green-600" /> M-Pesa Payment
      </h3>

      {result?.status === 'waiting' ? (
        <div className="text-center py-6">
          <Spinner className="h-10 w-10 mx-auto mb-3 text-green-600" />
          <p className="font-medium text-gray-900">{result.message}</p>
          <p className="text-sm text-gray-500 mt-1">Waiting for payment confirmation...</p>
        </div>
      ) : result?.status === 'success' ? (
        <div className="text-center py-6 space-y-3">
          <CheckCircle size={48} className="text-green-500 mx-auto" />
          <div>
            <p className="font-bold text-green-700">Payment Successful!</p>
            <p className="text-sm text-gray-600 mt-1">Payment of KES {parseFloat(amount || 0).toLocaleString()} confirmed</p>
            <p className="text-sm text-gray-600 mt-1">Receipt: <span className="font-mono font-medium">{result.receipt}</span></p>
          </div>
          <div className="flex items-center justify-center gap-2">
            <Button variant="secondary" className="gap-2" onClick={handleDownloadReceipt}>
              <Download size={16} /> Download Receipt
            </Button>
            {onClose && (
              <Button onClick={onClose}>Close</Button>
            )}
          </div>
        </div>
      ) : result?.status === 'cancelled' ? (
        <div className="text-center py-6">
          <AlertCircle size={48} className="text-orange-500 mx-auto mb-3" />
          <p className="font-bold text-orange-700">{result.message}</p>
          <p className="text-sm text-gray-500 mt-2">You can try again if this was a mistake.</p>
          <Button onClick={() => setResult(null)} className="mt-4">Try Again</Button>
        </div>
      ) : result?.status === 'timeout' ? (
        <div className="text-center py-6">
          <AlertCircle size={48} className="text-amber-500 mx-auto mb-3" />
          <p className="font-bold text-amber-700">{result.message}</p>
          <p className="text-sm text-gray-500 mt-2">No response was received from your phone.</p>
          <Button onClick={() => setResult(null)} className="mt-4">Try Again</Button>
        </div>
      ) : result?.status === 'failed' ? (
        <div className="text-center py-6">
          <AlertCircle size={48} className="text-red-500 mx-auto mb-3" />
          <p className="font-bold text-red-700">{result.message}</p>
          <Button onClick={() => setResult(null)} className="mt-4">Try Again</Button>
        </div>
      ) : (
        <div className="space-y-4">
          <Input label="Phone Number" placeholder="0712 345 678" value={phone} onChange={e => setPhone(e.target.value)} />
          <Input label="Amount (KES)" type="number" value={amount} onChange={e => setAmount(e.target.value)} />
          <Button onClick={handlePay} loading={loading} className="w-full">Send STK Push</Button>
        </div>
      )}

      {polling && (
        <div className="mt-4 text-center">
          <p className="text-xs text-gray-500 animate-pulse">Polling for confirmation...</p>
        </div>
      )}
    </>
  )

  if (mode === 'tab') {
    return <div>{body}</div>
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-lg max-w-md w-full p-6 relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"><X size={20} /></button>
        {body}
      </div>
    </div>
  )
}