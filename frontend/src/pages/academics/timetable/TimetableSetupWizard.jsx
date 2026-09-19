import { useCallback, useEffect, useMemo, useState } from 'react'
import { Clock, DoorOpen, BookOpen, Users, CheckCircle2, AlertTriangle } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { timetablingApi } from '@/api/timetabling'
import { Spinner, Select } from '@/components/ui'
import { listFromResponse } from '../shared'
import api from '@/api/client'
import StepIndicator from './components/StepIndicator'
import BellScheduleStep from './steps/BellScheduleStep'
import RoomsStep from './steps/RoomStep'
import SubjectRulesStep from './steps/SubjectRulesStep'
import TeachersStep from './steps/TeacherStep'
import ReviewStep from './steps/ReviewStep'

const STEPS = [
  { id: 1, title: 'Bell Schedule', icon: Clock, description: 'Set when each class starts and ends — every other step depends on this being right first.' },
  { id: 2, title: 'Rooms', icon: DoorOpen, description: 'Only needed if a subject requires a special room like a lab or hall. Safe to skip otherwise.' },
  { id: 3, title: 'Subjects', icon: BookOpen, description: 'Set how many lessons per week each subject gets — this decides how full each class\u2019s week looks.' },
  { id: 4, title: 'Teachers', icon: Users, description: 'Match a teacher to each subject for every class. You can leave some blank and fill them in later.' },
  { id: 5, title: 'Review', icon: CheckCircle2, description: 'Check for any gaps before generating, and see exactly what\u2019s missing if something isn\u2019t ready.' },
]

const TERM_OPTIONS = [
  { value: 'term1', label: 'Term 1' },
  { value: 'term2', label: 'Term 2' },
  { value: 'term3', label: 'Term 3' },
]

// DRF's default pagination caps /auth/users/ at its page size (commonly 20).
// A single api.get() call was silently dropping every teacher past that
// threshold, which is why the wizard worked fine with a small staff list and
// broke once more teachers were added: the Grid's <select> can't render a
// selected value for a teacher ID that isn't in its own <option> list, so it
// falls back to "Unassigned" even though the assignment genuinely exists.
// This walks every page via DRF's `next` cursor until exhausted, so the
// teachers array is always complete regardless of how many staff exist.
async function fetchAllUsers() {
  let results = []
  let nextUrl = '/auth/users/'
  let isFirstRequest = true
  while (nextUrl) {
    const { data } = await api.get(nextUrl, isFirstRequest ? { params: { page_size: 200 } } : undefined)
    isFirstRequest = false
    if (Array.isArray(data)) {
      // Endpoint isn't paginated at all — nothing more to fetch.
      results = results.concat(data)
      break
    }
    results = results.concat(data.results || [])
    nextUrl = data.next || null
  }
  return results
}

export default function TimetableSetupWizard({ onComplete }) {
  const [step, setStep] = useState(1)
  const [maxStepReached, setMaxStepReached] = useState(1)
  const [blockMessage, setBlockMessage] = useState(null)
  const [loading, setLoading] = useState(true)

  const [subjects, setSubjects] = useState([])
  const [classrooms, setClassrooms] = useState([])
  const [teachers, setTeachers] = useState([])
  const [templates, setTemplates] = useState([])
  const [periods, setPeriods] = useState([])
  const [rooms, setRooms] = useState([])
  const [subjectRules, setSubjectRules] = useState([])
  const [teacherAssignments, setTeacherAssignments] = useState([])
  const [readiness, setReadiness] = useState(null)

  // Which term this whole wizard session is configuring. Bell schedules, rooms,
  // and subject rules are tenant-wide (reused term to term), but teacher
  // assignments are scoped to a specific term — see TeacherSubjectAssignment.
  const [term, setTerm] = useState('term1')
  const [academicYear, setAcademicYear] = useState(new Date().getFullYear())

  const loadAll = useCallback(async (activeTerm, activeYear) => {
    setLoading(true)
    try {
      const [subRes, classRes, allUsers, tempRes, roomRes, ruleRes, assignRes, periodRes] = await Promise.all([
        academicsApi.getSubjects({ is_active: true }),
        studentsApi.getClassrooms({ is_active: true }),
        fetchAllUsers().catch(() => []),
        timetablingApi.getScheduleTemplates({}),
        timetablingApi.getRooms({}),
        timetablingApi.getSubjectRules({}),
        timetablingApi.getTeacherAssignments({ term: activeTerm, academic_year: activeYear }),
        timetablingApi.getPeriods({}),
      ])
      setSubjects(listFromResponse(subRes.data))
      setClassrooms(listFromResponse(classRes.data))
      setTeachers(allUsers.filter((u) => u.role === 'teacher'))
      setTemplates(listFromResponse(tempRes.data))
      setRooms(listFromResponse(roomRes.data))
      setSubjectRules(listFromResponse(ruleRes.data))
      setTeacherAssignments(listFromResponse(assignRes.data))
      setPeriods(listFromResponse(periodRes.data))
    } finally {
      setLoading(false)
    }
  }, [])

  // Only teacherAssignments are term-scoped, so switching term/year mid-session
  // just re-fetches that one list rather than reloading everything.
  const reloadTeacherAssignments = useCallback(async (activeTerm, activeYear) => {
    const { data } = await timetablingApi.getTeacherAssignments({ term: activeTerm, academic_year: activeYear })
    setTeacherAssignments(listFromResponse(data))
  }, [])

  useEffect(() => {
    loadAll(term, academicYear)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleTermChange = (nextTerm) => {
    setTerm(nextTerm)
    reloadTeacherAssignments(nextTerm, academicYear)
  }

  const handleYearChange = (nextYear) => {
    setAcademicYear(nextYear)
    reloadTeacherAssignments(term, nextYear)
  }

  // --- Step completion criteria ---
  // Rooms (step 2) and Teachers (step 4) are intentionally always "complete":
  // rooms are only required if a subject rule later needs a specific room
  // type (readiness.py already catches that at generation time), and teacher
  // assignments can legitimately be partial — the Review step surfaces
  // exactly what's still missing rather than blocking the wizard on it.
  const stepStatus = useMemo(() => ({
    1: templates.some((t) => t.is_active) && periods.some((p) => !p.is_break),
    2: true,
    3: subjectRules.some((r) => r.is_active && r.periods_per_week > 0),
    4: true,
  }), [templates, periods, subjectRules])

  // Auto-dismiss the "locked step" message so it doesn't linger forever.
  useEffect(() => {
    if (!blockMessage) return
    const t = setTimeout(() => setBlockMessage(null), 5000)
    return () => clearTimeout(t)
  }, [blockMessage])

  // Called by each step's own Next button (passed as that step's onNext prop).
  // The step components themselves are unchanged — they still just call
  // onNext() when their local "Next" button is clicked. This function decides
  // whether that's actually allowed to move the wizard forward.
  const guardedAdvance = (fromStepId) => {
    if (!stepStatus[fromStepId]) {
      const stepName = STEPS.find((s) => s.id === fromStepId)?.title || 'this step'
      setBlockMessage(`Complete "${stepName}" before continuing.`)
      return
    }
    setBlockMessage(null)
    const next = fromStepId + 1
    setStep(next)
    setMaxStepReached((m) => Math.max(m, next))
  }

  // Called when the user clicks a circle in StepIndicator. Backward/visited
  // navigation is always allowed; jumping past the furthest-completed step
  // is blocked with the same messaging as a blocked Next button.
  const handleStepClick = (targetStepId) => {
    if (targetStepId <= maxStepReached) {
      setBlockMessage(null)
      setStep(targetStepId)
      return
    }
    const blockingStep = STEPS.find((s) => s.id === maxStepReached)?.title || 'the current step'
    setBlockMessage(`Complete "${blockingStep}" before continuing.`)
  }

  const goBack = (targetStepId) => {
    setBlockMessage(null)
    setStep(targetStepId)
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Spinner className="h-8 w-8" />
        <p className="mt-3 text-sm text-gray-500">Loading your school data...</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-gray-900">Set Up Your Timetable</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure your bell schedule, rooms, subjects, and teacher assignments before generating.
        </p>
      </div>

      <div className="mx-auto flex max-w-xs items-center justify-center gap-3 rounded-lg border border-gray-100 bg-gray-50 px-4 py-2.5">
        <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Configuring</span>
        <Select
          className="w-32"
          value={term}
          onChange={(e) => handleTermChange(e.target.value)}
        >
          {TERM_OPTIONS.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </Select>
        <Select
          className="w-24"
          value={academicYear}
          onChange={(e) => handleYearChange(parseInt(e.target.value, 10))}
        >
          {[academicYear - 1, academicYear, academicYear + 1].map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </Select>
      </div>

      <StepIndicator
        current={step}
        steps={STEPS}
        maxStepReached={maxStepReached}
        onStepClick={handleStepClick}
      />

      <p className="mx-auto max-w-xl text-center text-sm text-gray-500">
        {STEPS.find((s) => s.id === step)?.description}
      </p>

      {blockMessage && (
        <div className="mx-auto flex max-w-xl items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
          <AlertTriangle size={16} className="shrink-0" />
          <span>{blockMessage}</span>
        </div>
      )}

      {step === 1 && (
        <BellScheduleStep
          templates={templates}
          periods={periods}
          setTemplates={setTemplates}
          setPeriods={setPeriods}
          onNext={() => guardedAdvance(1)}
        />
      )}

      {step === 2 && (
        <RoomsStep
          rooms={rooms}
          setRooms={setRooms}
          onBack={() => goBack(1)}
          onNext={() => guardedAdvance(2)}
        />
      )}

      {step === 3 && (
        <SubjectRulesStep
          subjects={subjects}
          classrooms={classrooms}
          templates={templates}
          periods={periods}
          subjectRules={subjectRules}
          setSubjectRules={setSubjectRules}
          onBack={() => goBack(2)}
          onNext={() => guardedAdvance(3)}
        />
      )}

      {step === 4 && (
        <TeachersStep
          teachers={teachers}
          subjects={subjects}
          classrooms={classrooms}
          periods={periods}
          teacherAssignments={teacherAssignments}
          setTeacherAssignments={setTeacherAssignments}
          subjectRules={subjectRules}
          term={term}
          academicYear={academicYear}
          onBack={() => goBack(3)}
          onNext={() => guardedAdvance(4)}
        />
      )}

      {step === 5 && (
        <ReviewStep
          readiness={readiness}
          setReadiness={setReadiness}
          term={term}
          academicYear={academicYear}
          onBack={() => goBack(4)}
          onComplete={onComplete}
        />
      )}
    </div>
  )
}
