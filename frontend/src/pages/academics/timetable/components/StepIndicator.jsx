import { CheckCircle2 } from 'lucide-react'

export default function StepIndicator({ current, steps }) {
  return (
    <div className="flex items-center justify-between">
      {steps.map((step, idx) => {
        const Icon = step.icon
        const isActive = step.id === current
        const isDone = step.id < current
        return (
          <div key={step.id} className="flex flex-1 items-center">
            <div className="flex flex-col items-center gap-1">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-semibold ${
                  isDone
                    ? 'border-green-600 bg-green-600 text-white'
                    : isActive
                    ? 'border-[var(--brand-primary)] bg-white text-[var(--brand-primary)]'
                    : 'border-gray-200 bg-white text-gray-400'
                }`}
              >
                {isDone ? <CheckCircle2 size={18} /> : <Icon size={18} />}
              </div>
              <span className={`hidden text-xs font-medium sm:block ${isActive || isDone ? 'text-gray-900' : 'text-gray-400'}`}>
                {step.title}
              </span>
            </div>
            {idx < steps.length - 1 && (
              <div className={`mx-2 h-0.5 flex-1 ${isDone ? 'bg-green-600' : 'bg-gray-200'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}