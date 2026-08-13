// Same stream-aware matching as timetabling/services/solver.py and
// timetabling/services/readiness.py: an exact grade+stream rule wins over a
// blank-stream (whole-grade) fallback rule. Keeping these in sync matters —
// this is what makes the live load numbers and the assignment matrix agree
// with what Readiness and the solver will actually see.
export function buildRuleLookup(subjectRules) {
  const exact = new Map()
  const fallback = new Map()
  subjectRules.forEach((r) => {
    const subjectId = typeof r.subject === 'object' ? r.subject.id : r.subject
    if (r.stream) {
      exact.set(`${r.grade_band}|${r.stream}|${subjectId}`, r)
    } else {
      fallback.set(`${r.grade_band}|${subjectId}`, r)
    }
  })
  return (classroom, subjectId) => {
    if (!classroom) return null
    const exactKey = `${classroom.grade_level}|${classroom.stream || ''}|${subjectId}`
    if (exact.has(exactKey)) return exact.get(exactKey)
    const fallbackKey = `${classroom.grade_level}|${subjectId}`
    return fallback.get(fallbackKey) || null
  }
}