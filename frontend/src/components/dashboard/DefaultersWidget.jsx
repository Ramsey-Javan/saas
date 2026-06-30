import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, ArrowRight, User } from 'lucide-react'
import { Card } from '@/components/ui'

export default function DefaultersWidget({ data, compact = false }) {
  const navigate = useNavigate()

  const defaulters = useMemo(() => {
    if (!data || data.length === 0) {
      return [
        { id: 1, name: 'John Kamau', admission_number: 'ADM/2024/001', classroom: 'Grade 5 East', balance: 45000, days_overdue: 12 },
        { id: 2, name: 'Mary Wanjiku', admission_number: 'ADM/2024/042', classroom: 'Grade 7 West', balance: 32000, days_overdue: 8 },
        { id: 3, name: 'Peter Ochieng', admission_number: 'ADM/2024/089', classroom: 'Grade 3 East', balance: 28000, days_overdue: 5 },
        { id: 4, name: 'Grace Achieng', admission_number: 'ADM/2024/156', classroom: 'Grade 8 East', balance: 56000, days_overdue: 21 },
        { id: 5, name: 'Daniel Mwangi', admission_number: 'ADM/2024/203', classroom: 'Grade 6 West', balance: 19000, days_overdue: 3 },
      ]
    }
    return data.slice(0, 5)
  }, [data])

  const totalOwed = defaulters.reduce((sum, d) => sum + (d.balance || 0), 0)
  const totalDefaulters = defaulters.length

  if (compact) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">Top Defaulters</h3>
          <button
            onClick={() => navigate('/finance/defaulters')}
            className="text-xs text-[var(--brand-primary)] hover:underline flex items-center gap-1"
          >
            View all <ArrowRight size={12} />
          </button>
        </div>
        <div className="space-y-2">
          {defaulters.map((d, i) => (
            <div
              key={d.id}
              onClick={() => navigate(`/students/${d.id}`)}
              className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors group"
            >
              <div className="h-8 w-8 rounded-full bg-red-50 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-red-600">{i + 1}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate group-hover:text-[var(--brand-primary)]">{d.name}</p>
                <p className="text-xs text-gray-500">{d.classroom} · {d.admission_number}</p>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-sm font-bold text-red-600">KES {d.balance?.toLocaleString()}</p>
                <p className="text-xs text-gray-400">{d.days_overdue}d overdue</p>
              </div>
            </div>
          ))}
        </div>
        <div className="pt-2 border-t border-gray-100 flex items-center justify-between text-xs">
          <span className="text-gray-500">{totalDefaulters} defaulters</span>
          <span className="text-red-600 font-semibold">KES {totalOwed.toLocaleString()} owed</span>
        </div>
      </div>
    )
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-red-50 flex items-center justify-center">
            <AlertCircle size={20} className="text-red-500" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Fee Defaulters</h3>
            <p className="text-sm text-gray-500">Students with outstanding balances</p>
          </div>
        </div>
        <button
          onClick={() => navigate('/finance/defaulters')}
          className="px-4 py-2 rounded-lg bg-red-50 text-red-600 text-sm font-medium hover:bg-red-100 transition-colors flex items-center gap-2"
        >
          View All <ArrowRight size={16} />
        </button>
      </div>

      <div className="space-y-3">
        {defaulters.map((d, i) => (
          <div
            key={d.id}
            onClick={() => navigate(`/students/${d.id}`)}
            className="flex items-center gap-4 p-4 rounded-xl bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors group"
          >
            <div className="h-10 w-10 rounded-full bg-white flex items-center justify-center shadow-sm flex-shrink-0">
              <span className="text-sm font-bold text-gray-400">{i + 1}</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-gray-900 group-hover:text-[var(--brand-primary)]">{d.name}</p>
                {d.days_overdue > 14 && (
                  <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-600 text-xs font-medium">Critical</span>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-0.5">{d.classroom} · {d.admission_number}</p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-lg font-bold text-red-600">KES {d.balance?.toLocaleString()}</p>
              <p className="text-xs text-gray-400">{d.days_overdue} days overdue</p>
            </div>
            <ArrowRight size={16} className="text-gray-300 group-hover:text-[var(--brand-primary)] transition-colors flex-shrink-0" />
          </div>
        ))}
      </div>

      <div className="mt-6 pt-6 border-t border-gray-100 grid grid-cols-3 gap-4">
        <div className="text-center">
          <p className="text-2xl font-bold text-red-600">{totalDefaulters}</p>
          <p className="text-xs text-gray-500 mt-1">Defaulters</p>
        </div>
        <div className="text-center border-x border-gray-100">
          <p className="text-2xl font-bold text-gray-900">KES {totalOwed.toLocaleString()}</p>
          <p className="text-xs text-gray-500 mt-1">Total Owed</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-900">{Math.round(totalOwed / totalDefaulters).toLocaleString()}</p>
          <p className="text-xs text-gray-500 mt-1">Avg per Student</p>
        </div>
      </div>
    </Card>
  )
}