import { CheckCircle2, Lock } from 'lucide-react'

export default function StepIndicator({ current, steps, maxStepReached = 1, onStepClick }) {
  return (
    <div className="flex items-center justify-between">
      {steps.map((step, idx) => {
        const Icon = step.icon
        const isActive = step.id === current
        const isDone = step.id < current
        const isReachable = step.id <= maxStepReached
        const isLocked = !isReachable

        const handleClick = () => {
          if (onStepClick) onStepClick(step.id)
        }

        return (
          <div key={step.id} className="flex flex-1 items-center">
            <button
              type="button"
              onClick={handleClick}
              disabled={false /* always clickable so locked steps can still trigger the "complete X first" message */}
              title={isLocked ? 'Complete the previous step first' : step.title}
              className={`flex flex-col items-center gap-1 bg-transparent ${
                isLocked ? 'cursor-not-allowed' : 'cursor-pointer'
              }`}
            >
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors ${
                  isDone
                    ? 'border-green-600 bg-green-600 text-white'
                    : isActive
                    ? 'border-[var(--brand-primary)] bg-white text-[var(--brand-primary)]'
                    : isLocked
                    ? 'border-gray-200 bg-gray-50 text-gray-300'
                    : 'border-gray-300 bg-white text-gray-500 hover:border-[var(--brand-primary)] hover:text-[var(--brand-primary)]'
                }`}
              >
                {isDone ? <CheckCircle2 size={18} /> : isLocked ? <Lock size={14} /> : <Icon size={18} />}
              </div>
              <span
                className={`hidden text-xs font-medium sm:block ${
                  isActive || isDone ? 'text-gray-900' : isLocked ? 'text-gray-300' : 'text-gray-500'
                }`}
              >
                {step.title}
              </span>
            </button>
            {idx < steps.length - 1 && (
              <div className={`mx-2 h-0.5 flex-1 ${isDone ? 'bg-green-600' : 'bg-gray-200'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}