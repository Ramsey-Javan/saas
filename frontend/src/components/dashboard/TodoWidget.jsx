import { useState, useEffect } from 'react'
import { Plus, Trash2, Check, Clock, AlertCircle, Calendar } from 'lucide-react'
import { Card } from '@/components/ui'
import { useAuthStore } from '@/store/authStore'

const STORAGE_KEY_PREFIX = 'admin-dashboard-todos'

const PRIORITY_CONFIG = {
  high: { color: 'bg-red-50 text-red-600 border-red-200', icon: AlertCircle, label: 'High' },
  medium: { color: 'bg-yellow-50 text-yellow-600 border-yellow-200', icon: Clock, label: 'Medium' },
  low: { color: 'bg-blue-50 text-blue-600 border-blue-200', icon: Calendar, label: 'Low' },
}

function loadTodos(storageKey) {
  try {
    const saved = localStorage.getItem(storageKey)
    return saved ? JSON.parse(saved) : []
  } catch {
    return []
  }
}

export default function TodoWidget() {
  const school = useAuthStore(state => state.school)
  // Scope the storage key by tenant id so two different schools sharing
  // the same browser (e.g. an admin testing both in dev, or simply the
  // same machine being used for two schools) never read/write each
  // other's tasks. Falls back to a generic key only if school isn't
  // loaded yet (briefly, on first paint) -- tasks created in that brief
  // window will migrate to the real per-school key on the next render
  // once `school` resolves, since the effect below re-keys on school.id.
  const storageKey = school?.id ? `${STORAGE_KEY_PREFIX}-${school.id}` : STORAGE_KEY_PREFIX

  const [todos, setTodos] = useState(() => loadTodos(storageKey))
  const [newTodo, setNewTodo] = useState('')
  const [newPriority, setNewPriority] = useState('medium')
  const [filter, setFilter] = useState('all')

  // Re-load from the correct key whenever the resolved school changes
  // (e.g. on first mount before `school` is hydrated, or if a user is
  // ever able to switch schools without a full page reload).
  useEffect(() => {
    setTodos(loadTodos(storageKey))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey])

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(todos))
  }, [todos, storageKey])

  const addTodo = () => {
    if (!newTodo.trim()) return
    const todo = {
      id: Date.now(),
      text: newTodo.trim(),
      completed: false,
      priority: newPriority,
      createdAt: new Date().toISOString(),
    }
    setTodos(prev => [todo, ...prev])
    setNewTodo('')
  }

  const toggleTodo = (id) => {
    setTodos(prev => prev.map(t => t.id === id ? { ...t, completed: !t.completed } : t))
  }

  const deleteTodo = (id) => {
    setTodos(prev => prev.filter(t => t.id !== id))
  }

  const filteredTodos = todos.filter(t => {
    if (filter === 'active') return !t.completed
    if (filter === 'completed') return t.completed
    return true
  })

  const activeCount = todos.filter(t => !t.completed).length
  const completedCount = todos.filter(t => t.completed).length

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Tasks & Reminders</h3>
          <p className="text-sm text-gray-500 mt-0.5">{activeCount} pending, {completedCount} completed</p>
        </div>
      </div>

      {/* Add new todo */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={newTodo}
          onChange={(e) => setNewTodo(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addTodo()}
          placeholder="Add a new task..."
          className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary-ring)] focus:border-transparent"
        />
        <select
          value={newPriority}
          onChange={(e) => setNewPriority(e.target.value)}
          className="px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary-ring)]"
        >
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <button
          onClick={addTodo}
          className="px-3 py-2 rounded-lg bg-[var(--brand-primary)] text-white hover:bg-[var(--brand-primary-hover)] transition-colors"
        >
          <Plus size={18} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-1 mb-4">
        {['all', 'active', 'completed'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              filter === f
                ? 'bg-[var(--brand-primary-light)] text-[var(--brand-primary)]'
                : 'text-gray-500 hover:bg-gray-100'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Todo list */}
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {filteredTodos.length === 0 ? (
          <div className="text-center py-6 text-gray-400 text-sm">
            <Check size={24} className="mx-auto mb-2" />
            <p>No tasks here</p>
          </div>
        ) : (
          filteredTodos.map(todo => {
            const config = PRIORITY_CONFIG[todo.priority]
            const PriorityIcon = config.icon
            return (
              <div
                key={todo.id}
                className={`flex items-center gap-3 p-3 rounded-lg border transition-all group ${
                  todo.completed ? 'bg-gray-50 border-gray-100' : 'bg-white border-gray-200 hover:border-gray-300'
                }`}
              >
                <button
                  onClick={() => toggleTodo(todo.id)}
                  className={`h-5 w-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                    todo.completed
                      ? 'bg-green-500 border-green-500 text-white'
                      : 'border-gray-300 hover:border-[var(--brand-primary)]'
                  }`}
                >
                  {todo.completed && <Check size={12} />}
                </button>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm truncate ${todo.completed ? 'line-through text-gray-400' : 'text-gray-900'}`}>
                    {todo.text}
                  </p>
                </div>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1 flex-shrink-0 ${config.color}`}>
                  <PriorityIcon size={10} />
                  {config.label}
                </span>
                <button
                  onClick={() => deleteTodo(todo.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-all"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            )
          })
        )}
      </div>
    </Card>
  )
}