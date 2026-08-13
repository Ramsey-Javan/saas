import { useCallback, useEffect, useState } from 'react'
import { Clock, DoorOpen, BookOpen, Users, CheckCircle2 } from 'lucide-react'
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
  { id: 1, title: 'Bell Schedule', icon: Clock, description: 'Set daily period times' },
  { id: 2, title: 'Rooms', icon: DoorOpen, description: 'Add labs & shared spaces' },
  { id: 3, title: 'Subjects', icon: BookOpen, description: 'Periods & rules per grade' },
  { id: 4, title: 'Teachers', icon: Users, description: 'Assign to classes' },
  { id: 5, title: 'Review', icon: CheckCircle2, description: 'Check readiness' },
]

const TERM_OPTIONS = [
  { value: 'term1', label: 'Term 1' },
  { value: 'term2', label: 'Term 2' },
  { value: 'term3', label: 'Term 3' },
]

export default function TimetableSetupWizard({ onComplete }) {
  const [step, setStep] = useState(1)
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
      const [subRes, classRes, userRes, tempRes, roomRes, ruleRes, assignRes, periodRes] = await Promise.all([
        academicsApi.getSubjects({ is_active: true }),
        studentsApi.getClassrooms({ is_active: true }),
        api.get('/auth/users/').catch(() => ({ data: { results: [] } })),
        timetablingApi.getScheduleTemplates({}),
        timetablingApi.getRooms({}),
        timetablingApi.getSubjectRules({}),
        timetablingApi.getTeacherAssignments({ term: activeTerm, academic_year: activeYear }),
        timetablingApi.getPeriods({}),
      ])
      setSubjects(listFromResponse(subRes.data))
      setClassrooms(listFromResponse(classRes.data))
      setTeachers(listFromResponse(userRes.data).filter((u) => u.role === 'teacher'))
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

      <StepIndicator current={step} steps={STEPS} />

      {step === 1 && (
        <BellScheduleStep
          templates={templates}
          periods={periods}
          setTemplates={setTemplates}
          setPeriods={setPeriods}
          onNext={() => setStep(2)}
        />
      )}

      {step === 2 && (
        <RoomsStep
          rooms={rooms}
          setRooms={setRooms}
          onBack={() => setStep(1)}
          onNext={() => setStep(3)}
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
          onBack={() => setStep(2)}
          onNext={() => setStep(4)}
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
          onBack={() => setStep(3)}
          onNext={() => setStep(5)}
        />
      )}

      {step === 5 && (
        <ReviewStep
          readiness={readiness}
          setReadiness={setReadiness}
          term={term}
          academicYear={academicYear}
          onBack={() => setStep(4)}
          onComplete={onComplete}
        />
      )}
    </div>
  )
}
