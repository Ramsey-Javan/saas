import { useMemo } from 'react'
import { CheckCircle, XCircle, Clock, Users, TrendingUp, TrendingDown } from 'lucide-react'
import { Card } from '@/components/ui'

export default function AttendanceWidget({ data, compact = false }) {
  const attendance = useMemo(() => {
    if (!data || !data.length) {
      return [
        { classroom: 'PP1 East', present: 22, absent: 3, total: 25, rate: 88 },
        { classroom: 'PP2 West', present: 28, absent: 1, total: 29, rate: 97 },
        { classroom: 'Grade 1 East', present: 35, absent: 2, total: 37, rate: 95 },
        { classroom: 'Grade 2 West', present: 38, absent: 4, total: 42, rate: 90 },
        { classroom: 'Grade 3 East', present: 32, absent: 5, total: 37, rate: 87 },
        { classroom: 'Grade 4 West', present: 40, absent: 2, total: 42, rate: 95 },
        { classroom: 'Grade 5 East', present: 42, absent: 1, total: 43, rate: 98 },
      ]
    }
    return data
  }, [data])

  const totalPresent = attendance.reduce((sum, a) => sum + a.present, 0)
  const totalAbsent = attendance.reduce((sum, a) => sum + a.absent, 0)
  const totalStudents = attendance.reduce((sum, a) => sum + a.total, 0)
  const overallRate = totalStudents > 0 ? Math.round((totalPresent / totalStudents) * 100) : 0
  const yesterdayRate = 92 // Simulated for demo
  const rateChange = overallRate - yesterdayRate

  if (compact) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">Today's Attendance</h3>
          <div className="flex items-center gap-1 text-xs">
            {rateChange >= 0 ? (
              <TrendingUp size={12} className="text-green-500" />
            ) : (
              <TrendingDown size={12} className="text-red-500" />
            )}
            <span className={rateChange >= 0 ? 'text-green-600' : 'text-red-600'}>
              {rateChange > 0 ? '+' : ''}{rateChange}%
            </span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="relative h-20 w-20">
            <svg className="h-20 w-20 -rotate-90" viewBox="0 0 36 36">
              <path className="text-gray-100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="3" />
              <path className="text-green-500" strokeDasharray={`${overallRate}, 100`} d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="3" />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-lg font-bold text-gray-900">{overallRate}%</span>
            </div>
          </div>
          <div className="flex-1 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5 text-gray-600">
                <CheckCircle size={14} className="text-green-500" /> Present
              </span>
              <span className="font-semibold text-gray-900">{totalPresent}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5 text-gray-600">
                <XCircle size={14} className="text-red-500" /> Absent
              </span>
              <span className="font-semibold text-gray-900">{totalAbsent}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5 text-gray-600">
                <Users size={14} className="text-gray-400" /> Total
              </span>
              <span className="font-semibold text-gray-900">{totalStudents}</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Attendance Overview</h3>
          <p className="text-sm text-gray-500 mt-0.5">Today's attendance by classroom</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative h-16 w-16">
            <svg className="h-16 w-16 -rotate-90" viewBox="0 0 36 36">
              <path className="text-gray-100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="3" />
              <path className="text-green-500" strokeDasharray={`${overallRate}, 100`} d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="3" />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-sm font-bold text-gray-900">{overallRate}%</span>
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {attendance.map((a) => (
          <div key={a.classroom} className="flex items-center gap-4 p-3 rounded-lg bg-gray-50">
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-900">{a.classroom}</span>
                <span className={`text-xs font-semibold ${a.rate >= 95 ? 'text-green-600' : a.rate >= 85 ? 'text-yellow-600' : 'text-red-600'}`}>
                  {a.rate}%
                </span>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${a.rate >= 95 ? 'bg-green-500' : a.rate >= 85 ? 'bg-yellow-500' : 'bg-red-500'}`}
                  style={{ width: `${a.rate}%` }}
                />
              </div>
              <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <CheckCircle size={10} className="text-green-500" /> {a.present}
                </span>
                <span className="flex items-center gap-1">
                  <XCircle size={10} className="text-red-500" /> {a.absent}
                </span>
                <span>of {a.total}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 pt-6 border-t border-gray-100 grid grid-cols-3 gap-4">
        <div className="text-center">
          <p className="text-2xl font-bold text-green-600">{totalPresent}</p>
          <p className="text-xs text-gray-500 mt-1">Present</p>
        </div>
        <div className="text-center border-x border-gray-100">
          <p className="text-2xl font-bold text-red-600">{totalAbsent}</p>
          <p className="text-xs text-gray-500 mt-1">Absent</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-900">{totalStudents}</p>
          <p className="text-xs text-gray-500 mt-1">Total</p>
        </div>
      </div>
    </Card>
  )
}