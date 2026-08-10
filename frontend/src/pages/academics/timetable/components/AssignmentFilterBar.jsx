import { Select } from '@/components/ui'

export default function AssignmentFilterBar({ teachers, subjects, classrooms, filters, onChange }) {
  return (
    <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-4">
      <Select value={filters.teacher} onChange={(e) => onChange('teacher', e.target.value)}>
        <option value="">All Teachers</option>
        {teachers.map((t) => (
          <option key={t.id} value={t.id}>
            {[t.first_name, t.last_name].filter(Boolean).join(' ') || t.email}
          </option>
        ))}
      </Select>
      <Select value={filters.subject} onChange={(e) => onChange('subject', e.target.value)}>
        <option value="">All Subjects</option>
        {subjects.map((s) => (
          <option key={s.id} value={s.id}>{s.name}</option>
        ))}
      </Select>
      <Select value={filters.classroom} onChange={(e) => onChange('classroom', e.target.value)}>
        <option value="">All Classrooms</option>
        {classrooms.map((c) => (
          <option key={c.id} value={c.id}>
            {`${c.name || ''}${c.stream ? ` ${c.stream}` : ''}`.trim()}
          </option>
        ))}
      </Select>
      <Select value={filters.grade} onChange={(e) => onChange('grade', e.target.value)}>
        <option value="">All Grades</option>
        {[...new Set(classrooms.map((c) => c.grade_level).filter(Boolean))].sort().map((g) => (
          <option key={g} value={g}>{g}</option>
        ))}
      </Select>
    </div>
  )
}