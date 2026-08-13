import { Fragment, useMemo, useState } from 'react'
import { Copy } from 'lucide-react'
import { Select, Spinner } from '@/components/ui'
import { timetablingApi } from '@/api/timetabling'
import api from '@/api/client'
import { buildRuleLookup } from '../AssignmentRules'

function classroomLabel(c) {
  return `${c.name || ''}${c.stream ? ` ${c.stream}` : ''}`.trim()
}

function teacherLabel(t) {
  return [t.first_name, t.last_name].filter(Boolean).join(' ') || t.email
}

export default function AssignmentMatrix({
  teachers,
  subjects,
  classrooms,
  subjectRules,
  teacherAssignments,
  setTeacherAssignments,
  term,
  academicYear,
  onError,
}) {
  const [pendingKeys, setPendingKeys] = useState(() => new Set())
  const ruleFor = useMemo(() => buildRuleLookup(subjectRules), [subjectRules])

  // Classrooms grouped by grade, each group sorted by stream.
  const gradeGroups = useMemo(() => {
    const groups = new Map()
    classrooms.forEach((c) => {
      if (!groups.has(c.grade_level)) groups.set(c.grade_level, [])
      groups.get(c.grade_level).push(c)
    })
    for (const list of groups.values()) {
      list.sort((a, b) => (a.stream || '').localeCompare(b.stream || ''))
    }
    return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]))
  }, [classrooms])

  // For a given grade, which subjects have at least one active rule?
  const subjectsForGrade = (grade) => {
    const ids = new Set(
      subjectRules
        .filter((r) => r.grade_band === grade && r.periods_per_week > 0 && r.is_active !== false)
        .map((r) => (typeof r.subject === 'object' ? r.subject.id : r.subject))
    )
    return subjects
      .filter((s) => ids.has(s.id))
      .sort((a, b) => a.name.localeCompare(b.name))
  }

  const assignmentMap = useMemo(() => {
    const map = new Map()
    teacherAssignments.forEach((a) => {
      const classroomId = typeof a.classroom === 'object' ? a.classroom.id : a.classroom
      const subjectId = typeof a.subject === 'object' ? a.subject.id : a.subject
      map.set(`${classroomId}|${subjectId}`, a)
    })
    return map
  }, [teacherAssignments])

  const cellKey = (classroomId, subjectId) => `${classroomId}|${subjectId}`

  const withPending = async (keys, fn) => {
    setPendingKeys((prev) => new Set([...prev, ...keys]))
    try {
      await fn()
    } finally {
      setPendingKeys((prev) => {
        const next = new Set(prev)
        keys.forEach((k) => next.delete(k))
        return next
      })
    }
  }

  const refetch = async () => {
    const { data } = await timetablingApi.getTeacherAssignments({ term, academic_year: academicYear })
    setTeacherAssignments(data.results || data)
  }

  const extractError = (err, fallback) => {
    const data = err?.response?.data
    if (!data) return err?.message || fallback
    if (data.detail) return data.detail
    const firstValue = Object.values(data)[0]
    if (Array.isArray(firstValue)) return firstValue[0]
    return fallback
  }

  const setCell = (classroom, subject, teacherId) => {
    const key = cellKey(classroom.id, subject.id)
    const existing = assignmentMap.get(key)
    if (existing && String(existing.teacher) === String(teacherId)) return
    if (!existing && !teacherId) return

    return withPending([key], async () => {
      try {
        if (existing) {
          await api.delete(`/timetabling/teacher-subject-assignments/${existing.id}/`)
        }
        if (teacherId) {
          await timetablingApi.bulkTeacherAssignment({
            teacher: parseInt(teacherId, 10),
            subject: subject.id,
            classrooms: [classroom.id],
            term,
            academic_year: academicYear,
          })
        }
        await refetch()
      } catch (err) {
        onError?.(extractError(err, 'Failed to save this assignment.'))
      }
    })
  }

  const fillDown = (sourceClassroom, subject, group) => {
    const source = assignmentMap.get(cellKey(sourceClassroom.id, subject.id))
    if (!source) return
    const siblings = group.filter((c) => c.id !== sourceClassroom.id && ruleFor(c, subject.id))
    if (siblings.length === 0) return

    const keys = siblings.map((c) => cellKey(c.id, subject.id))
    return withPending(keys, async () => {
      try {
        const toClear = siblings
          .map((c) => assignmentMap.get(cellKey(c.id, subject.id)))
          .filter((a) => a && String(a.teacher) !== String(source.teacher))
        await Promise.all(toClear.map((a) => api.delete(`/timetabling/teacher-subject-assignments/${a.id}/`)))

        const targetIds = siblings
          .filter((c) => {
            const existing = assignmentMap.get(cellKey(c.id, subject.id))
            return !existing || String(existing.teacher) !== String(source.teacher)
          })
          .map((c) => c.id)

        if (targetIds.length > 0) {
          await timetablingApi.bulkTeacherAssignment({
            teacher: source.teacher,
            subject: subject.id,
            classrooms: targetIds,
            term,
            academic_year: academicYear,
          })
        }
        await refetch()
      } catch (err) {
        onError?.(extractError(err, 'Failed to copy this assignment to sibling streams.'))
      }
    })
  }

  if (gradeGroups.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-gray-400">
        No classes found.
      </p>
    )
  }

  return (
    <div className="space-y-8">
      {gradeGroups.map(([grade, group]) => {
        const cols = subjectsForGrade(grade)
        if (cols.length === 0) return null

        return (
          <div key={grade}>
            <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
              {grade}
            </h4>
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full border-separate border-spacing-0 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="sticky left-0 z-10 bg-gray-50 px-3 py-2 text-left font-semibold text-gray-700">
                      Class
                    </th>
                    {cols.map((s) => (
                      <th
                        key={s.id}
                        className="min-w-44 border-l border-gray-200 px-3 py-2 text-left font-semibold text-gray-700"
                      >
                        {s.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {group.map((classroom) => (
                    <tr key={classroom.id}>
                      <td className="sticky left-0 z-10 border-t border-gray-100 bg-white px-3 py-2 font-medium text-gray-700">
                        {classroomLabel(classroom)}
                      </td>
                      {cols.map((subject) => {
                        const applicable = ruleFor(classroom, subject.id)
                        const key = cellKey(classroom.id, subject.id)
                        const assignment = assignmentMap.get(key)
                        const isPending = pendingKeys.has(key)

                        if (!applicable) {
                          return (
                            <td
                              key={subject.id}
                              className="border-l border-t border-gray-50 px-3 py-2 text-center text-gray-200"
                            >
                              —
                            </td>
                          )
                        }

                        return (
                          <td key={subject.id} className="border-l border-t border-gray-100 px-2 py-1.5 align-middle">
                            <div className="flex items-center gap-1">
                              <Select
                                className="flex-1"
                                value={assignment?.teacher || ''}
                                disabled={isPending}
                                onChange={(e) => setCell(classroom, subject, e.target.value)}
                              >
                                <option value="">Unassigned</option>
                                {teachers.map((t) => (
                                  <option key={t.id} value={t.id}>{teacherLabel(t)}</option>
                                ))}
                              </Select>
                              {isPending && <Spinner className="h-4 w-4 shrink-0" />}
                              {!isPending && assignment && group.length > 1 && (
                                <button
                                  type="button"
                                  title={`Copy to other streams in ${grade}`}
                                  className="shrink-0 rounded p-1 text-gray-300 hover:bg-blue-50 hover:text-blue-500"
                                  onClick={() => fillDown(classroom, subject, group)}
                                >
                                  <Copy size={14} />
                                </button>
                              )}
                            </div>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      })}
    </div>
  )
}