import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Download, FileText } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { studentsApi } from '@/api/students'
import { useAuthStore } from '@/store/authStore'
import { Button, Card, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { EmptyTableRow, Modal, StatCard, StatusBadge, TERMS, classroomLabel, listFromResponse, openBlobInNewTab, termLabel, thisYear } from './shared'

function GenerateModal({ annual = false, classrooms, onClose, onDone }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ classroom: '', term: 'term1', academic_year: thisYear(), closing_date: '', next_term_opening_date: '' })
  const [preview, setPreview] = useState(0)
  useEffect(() => {
    if (!form.classroom) return setPreview(0)
    studentsApi.getStudents({ classroom: form.classroom, status: 'active' }).then(res => setPreview(listFromResponse(res.data).length))
  }, [form.classroom])
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      if (annual) await academicsApi.generateAnnualReportCards({ classroom: form.classroom, academic_year: form.academic_year })
      else await academicsApi.generateReportCards({ ...form, report_type: 'termly' })
      onDone()
      onClose()
    } finally {
      setSaving(false)
    }
  }
  return (
    <Modal title={annual ? 'Generate Annual Summary' : 'Generate Termly Report Cards'} onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" form="generate-report-form" loading={saving}>{annual ? 'Generate Annual Summary' : 'Generate'}</Button></>}>
      <form id="generate-report-form" onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Select label="Classroom" value={form.classroom} onChange={e => setForm(f => ({ ...f, classroom: e.target.value }))} required>
          <option value="">Select class</option>
          {classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}
        </Select>
        {!annual && <Select label="Term" value={form.term} onChange={e => setForm(f => ({ ...f, term: e.target.value }))}>{TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}</Select>}
        <Input label="Academic Year" type="number" value={form.academic_year} onChange={e => setForm(f => ({ ...f, academic_year: e.target.value }))} required />
        {!annual && <>
          <Input label="Closing Date" type="date" value={form.closing_date} onChange={e => setForm(f => ({ ...f, closing_date: e.target.value }))} />
          <Input label="Next Term Opening Date" type="date" value={form.next_term_opening_date} onChange={e => setForm(f => ({ ...f, next_term_opening_date: e.target.value }))} />
        </>}
      </form>
      <div className="mt-4 rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-700">Will generate for {preview} active students. Existing report cards will be skipped.</div>
    </Modal>
  )
}

function RemarksModal({ card, onClose, onDone }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    class_teacher_remarks: card.class_teacher_remarks || '',
    principal_remarks: card.principal_remarks || '',
    conduct_discipline: card.conduct_discipline || 3,
    conduct_respect: card.conduct_respect || 3,
    conduct_responsibility: card.conduct_responsibility || 3,
    conduct_punctuality: card.conduct_punctuality || 3,
    conduct_participation: card.conduct_participation || 3,
    closing_date: card.closing_date || '',
    next_term_opening_date: card.next_term_opening_date || '',
  })
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      await academicsApi.updateReportCard(card.id, form)
      onDone()
      onClose()
    } finally {
      setSaving(false)
    }
  }
  const conduct = ['discipline', 'respect', 'responsibility', 'punctuality', 'participation']
  return (
    <Modal title="Edit Remarks" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" form="remarks-form" loading={saving}>Save Remarks</Button></>}>
      <form id="remarks-form" onSubmit={submit} className="space-y-4">
        <label className="block text-sm font-medium text-gray-700">Class Teacher Remarks<textarea rows={3} value={form.class_teacher_remarks} onChange={e => setForm(f => ({ ...f, class_teacher_remarks: e.target.value }))} className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" /></label>
        <label className="block text-sm font-medium text-gray-700">Principal Remarks<textarea rows={3} value={form.principal_remarks} onChange={e => setForm(f => ({ ...f, principal_remarks: e.target.value }))} className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" /></label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {conduct.map(item => <Input key={item} label={`${item[0].toUpperCase()}${item.slice(1)} Rating`} type="number" min="1" max="4" value={form[`conduct_${item}`]} onChange={e => setForm(f => ({ ...f, [`conduct_${item}`]: e.target.value }))} />)}
          <Input label="Closing Date" type="date" value={form.closing_date} onChange={e => setForm(f => ({ ...f, closing_date: e.target.value }))} />
          <Input label="Next Term Opening Date" type="date" value={form.next_term_opening_date} onChange={e => setForm(f => ({ ...f, next_term_opening_date: e.target.value }))} />
        </div>
      </form>
    </Modal>
  )
}

export default function ReportCardsDashboard() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const isAdmin = useAuthStore(state => state.hasRole('admin', 'superadmin'))
  const [cards, setCards] = useState([])
  const [classrooms, setClassrooms] = useState([])
  const [selected, setSelected] = useState([])
  const [modal, setModal] = useState(null)
  const [filters, setFilters] = useState({ term: 'term1', academic_year: thisYear(), classroom: '', status: '', report_type: 'termly', student: searchParams.get('student') || '' })
  const [loading, setLoading] = useState(true)

  const fetchCards = useCallback(async () => {
    setLoading(true)
    try {
      if (filters.student) {
        const { data } = await academicsApi.getStudentReportCards(filters.student)
        setCards(listFromResponse(data).filter(card => (
          (!filters.term || filters.report_type !== 'termly' || card.term === filters.term)
          && (!filters.academic_year || String(card.academic_year) === String(filters.academic_year))
          && (!filters.classroom || String(card.classroom) === String(filters.classroom))
          && (!filters.status || card.status === filters.status)
          && (!filters.report_type || card.report_type === filters.report_type)
        )))
      } else {
        const { data } = await academicsApi.getReportCards({
          term: filters.report_type === 'termly' ? filters.term : undefined,
          academic_year: filters.academic_year || undefined,
          classroom: filters.classroom || undefined,
          status: filters.status || undefined,
          report_type: filters.report_type || undefined,
          page_size: 1000,
        })
        setCards(listFromResponse(data))
      }
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { studentsApi.getClassrooms().then(res => setClassrooms(listFromResponse(res.data))) }, [])
  useEffect(() => { fetchCards() }, [fetchCards])

  const stats = useMemo(() => ({
    total: cards.length,
    published: cards.filter(c => c.status === 'published').length,
    drafts: cards.filter(c => c.status !== 'published').length,
    pending: cards.filter(c => !c.class_teacher_remarks || !c.principal_remarks).length,
  }), [cards])

  const openPdf = async (card) => {
    const { data } = await academicsApi.getReportCardPdf(card.id)
    openBlobInNewTab(data)
  }
  const publish = async (card) => {
    await academicsApi.publishReportCard(card.id)
    fetchCards()
  }
  const publishSelected = async () => {
    for (const id of selected) await academicsApi.publishReportCard(id)
    setSelected([])
    fetchCards()
  }
  const downloadSelected = async () => {
    for (const id of selected) {
      const { data } = await academicsApi.getReportCardPdf(id)
      openBlobInNewTab(data)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Report Cards"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setModal({ type: 'generate' })}>Generate Termly Report Cards</Button>
            <Button variant="secondary" onClick={() => setModal({ type: 'annual' })}>Generate Annual Summary</Button>
          </div>
        }
      />
      <Card className="p-4 grid grid-cols-1 md:grid-cols-5 gap-3">
        <Select label="Term" value={filters.term} onChange={e => setFilters(f => ({ ...f, term: e.target.value }))}>{TERMS.map(term => <option key={term.value} value={term.value}>{term.label}</option>)}</Select>
        <Input label="Academic Year" type="number" value={filters.academic_year} onChange={e => setFilters(f => ({ ...f, academic_year: e.target.value }))} />
        <Select label="Classroom" value={filters.classroom} onChange={e => setFilters(f => ({ ...f, classroom: e.target.value }))}><option value="">All classes</option>{classrooms.map(c => <option key={c.id} value={c.id}>{classroomLabel(c)}</option>)}</Select>
        <Select label="Status" value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}><option value="">All</option><option value="draft">Draft</option><option value="published">Published</option></Select>
        <Select label="Type" value={filters.report_type} onChange={e => setFilters(f => ({ ...f, report_type: e.target.value }))}><option value="termly">Termly</option><option value="annual">Annual</option></Select>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon={FileText} label="Total Generated" value={stats.total} />
        <StatCard label="Published" value={stats.published} tone="green" />
        <StatCard label="Drafts" value={stats.drafts} tone="orange" />
        <StatCard label="Pending Remarks" value={stats.pending} tone="red" />
      </div>
      <Card className="p-2"><div className="flex gap-2">{['termly', 'annual'].map(type => <button key={type} onClick={() => setFilters(f => ({ ...f, report_type: type }))} className={`rounded-lg px-4 py-2 text-sm font-medium capitalize ${filters.report_type === type ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}>{type}</button>)}</div></Card>
      {selected.length > 0 && (
        <Card className="p-3 flex flex-wrap gap-2">
          {isAdmin && <Button size="sm" onClick={publishSelected}>Publish Selected</Button>}
          <Button size="sm" variant="secondary" onClick={downloadSelected} className="gap-1"><Download size={14} /> Download PDFs</Button>
        </Card>
      )}
      <Card>
        {loading ? <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-100">{['', 'Student', 'Class', 'Term', 'Year', 'Attendance %', 'Status', 'Actions'].map(h => <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-gray-50">
                {cards.length === 0 ? <EmptyTableRow colSpan={8} message="No report cards found." /> : cards.map(card => (
                  <tr key={card.id}>
                    <td className="px-4 py-3"><input type="checkbox" checked={selected.includes(card.id)} onChange={e => setSelected(current => e.target.checked ? [...current, card.id] : current.filter(id => id !== card.id))} /></td>
                    <td className="px-4 py-3 font-medium text-gray-900">{card.student_name}</td>
                    <td className="px-4 py-3 text-gray-600">{card.classroom_name}</td>
                    <td className="px-4 py-3 text-gray-600">{termLabel(card.term)}</td>
                    <td className="px-4 py-3 text-gray-600">{card.academic_year}</td>
                    <td className="px-4 py-3">{card.attendance_percentage || 0}%</td>
                    <td className="px-4 py-3"><StatusBadge status={card.status} /></td>
                    <td className="px-4 py-3"><div className="flex gap-2"><Button size="sm" variant="secondary" onClick={() => setModal({ type: 'remarks', card })}>Edit Remarks</Button><Button size="sm" variant="secondary" onClick={() => openPdf(card)}>PDF</Button><Button size="sm" variant="secondary" onClick={() => navigate(`/academics/report-cards/${card.id}`)}>View</Button>{isAdmin && card.status !== 'published' && <Button size="sm" onClick={() => publish(card)}>Publish</Button>}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {modal?.type === 'generate' && <GenerateModal classrooms={classrooms} onClose={() => setModal(null)} onDone={fetchCards} />}
      {modal?.type === 'annual' && <GenerateModal annual classrooms={classrooms} onClose={() => setModal(null)} onDone={fetchCards} />}
      {modal?.type === 'remarks' && <RemarksModal card={modal.card} onClose={() => setModal(null)} onDone={fetchCards} />}
    </div>
  )
}
