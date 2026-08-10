import { useState } from 'react'
import { ChevronLeft, ChevronRight, CheckCircle2, AlertCircle, XCircle } from 'lucide-react'
import { Button, Card, Spinner } from '@/components/ui'
import { timetablingApi } from '@/api/timetabling'

export default function ReviewStep({ readiness, setReadiness, onBack, onComplete }) {
  const [saving, setSaving] = useState(false)

  const runReadiness = async () => {
    setSaving(true)
    try {
      const { data } = await timetablingApi.getReadiness()
      setReadiness(data)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-gray-900">Readiness Check</h3>
          <Button size="sm" variant="secondary" onClick={runReadiness} loading={saving}>
            Run Check
          </Button>
        </div>

        {!readiness && (
          <p className="text-sm text-gray-500">Click "Run Check" to verify your timetable is ready to generate.</p>
        )}

        {readiness && (
          <div className="space-y-3">
            {readiness.ready ? (
              <div className="flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-700">
                <CheckCircle2 size={18} />
                <span className="font-medium">Ready to generate!</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                <XCircle size={18} />
                <span className="font-medium">Please fix the issues below before generating.</span>
              </div>
            )}

            {readiness.errors?.map((err, i) => (
              <div key={`e-${i}`} className="rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
                {err.message}
              </div>
            ))}

            {readiness.warnings?.map((warn, i) => (
              <div key={`w-${i}`} className="rounded-md border border-amber-100 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                {warn.message}
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="flex justify-between">
        <Button variant="secondary" onClick={onBack}>
          <ChevronLeft size={16} className="mr-1" /> Back
        </Button>
        <Button
          onClick={onComplete}
          disabled={!readiness?.ready}
          className={!readiness?.ready ? 'opacity-50 cursor-not-allowed' : ''}
        >
          Finish & Open Timetable <ChevronRight size={16} className="ml-1" />
        </Button>
      </div>
    </div>
  )
}