import { useEffect, useState } from 'react'
import { financeApi } from '@/api/finance'
import { Card, Spinner, Button } from '@/components/ui'
import { Download } from 'lucide-react'

const formatMoney = (value) => `KES ${parseFloat(value || 0).toLocaleString()}`

export default function ReceiptsPage() {
  const [receipts, setReceipts] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedIds, setSelectedIds] = useState([])
  const [statusMessage, setStatusMessage] = useState('')

  useEffect(() => {
    setLoading(true)
    financeApi.getReceipts({ page: 1 }).then(res => {
      setReceipts(res.data.results || res.data || [])
      setLoading(false)
    })
  }, [])

  if (loading) return <div className="flex justify-center py-20"><Spinner ClassName="h-7 w-7"/></div>

  const toggleAll = (checked) => {
    setSelectedIds(checked ? receipts.map(r => r.id) : [])
  }

  const toggleOne = (id) => {
    setSelectedIds(ids => ids.includes(id) ? ids.filter(item => item !== id) : [...ids, id])
  }

  const handleBulkReceiptsPdf = async () => {
    if (selectedIds.length === 0) return
    setStatusMessage('Preparing receipts PDF...')
    const res = await financeApi.bulkReceiptsPdf({ receipt_ids: selectedIds })
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'receipts.pdf'
    link.click()
    window.URL.revokeObjectURL(url)
    setStatusMessage('')
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Receipts</h1>
          <p className="text-sm text-gray-500">Issued receipts for completed payments.</p>
        </div>
        <Button
          variant="secondary"
          className="gap-2"
          disabled={selectedIds.length === 0}
          onClick={handleBulkReceiptsPdf}
        >
          <Download size={16} /> Download Selected Receipts PDF
        </Button>
      </div>

      {statusMessage && (
        <div className="px-4 py-3 rounded-lg bg-blue-50 text-blue-700 text-sm">
          {statusMessage}
        </div>
      )}

      <Card className="p-5">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b text-gray-500">
              <tr>
                <th className="text-left py-2">
                  <input
                    type="checkbox"
                    checked={selectedIds.length > 0 && selectedIds.length === receipts.length}
                    onChange={e => toggleAll(e.target.checked)}
                  />
                </th>
                <th className="text-left py-2">Receipt #</th>
                <th className="text-left py-2">Student</th>
                <th className="text-left py-2">Amount</th>
                <th className="text-left py-2">Term</th>
                <th className="text-left py-2">Academic Year</th>
                <th className="text-left py-2">Date</th>
              </tr>
            </thead>
            <tbody>
              {receipts.map(receipt => (
                <tr key={receipt.id} className="border-b border-gray-50">
                  <td className="py-2">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(receipt.id)}
                      onChange={() => toggleOne(receipt.id)}
                    />
                  </td>
                  <td className="py-2 font-mono">{receipt.receipt_number}</td>
                  <td className="py-2">
                    <p className="font-medium">{receipt.student_name || receipt.student}</p>
                  </td>
                  <td className="py-2 font-mono">{formatMoney(receipt.amount)}</td>
                  <td className="py-2 capitalize">{receipt.term}</td>
                  <td className="py-2">{receipt.academic_year}</td>
                  <td className="py-2 text-gray-500">{new Date(receipt.issued_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
