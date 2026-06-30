import { useEffect, useMemo, useState } from 'react'
import { BookOpen, ChevronDown, Edit2, Plus, Search, Trash2 } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { Badge, Button, Card, EmptyState, Input, PageHeader, Spinner } from '@/components/ui'
import { Modal, listFromResponse } from './shared'

const GRADE_LEVELS = ['PP1', 'PP2', 'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8', 'Grade 9']

function CurriculumForm({ type, item, parent, onClose, onSaved }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(() => ({
    name: item?.name || '',
    code: item?.code || '',
    description: item?.description || item?.description || '',
    grade_levels: item?.grade_levels || [],
    subject: parent?.subject || item?.subject || '',
    strand: parent?.strand || item?.strand || '',
    sub_strand: parent?.sub_strand || item?.sub_strand || '',
  }))

  const title = {
    subject: item ? 'Edit Subject' : 'Add Subject',
    strand: item ? 'Edit Strand' : 'Add Strand',
    sub: item ? 'Edit Sub-strand' : 'Add Sub-strand',
    outcome: item ? 'Edit Learning Outcome' : 'Add Learning Outcome',
  }[type]

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSaving(true)
    const payloads = {
      subject: {
        name: form.name,
        code: form.code,
        description: form.description,
        grade_levels: form.grade_levels,
      },
      strand: { name: form.name, subject: form.subject },
      sub: { name: form.name, strand: form.strand },
      outcome: { description: form.description, sub_strand: form.sub_strand },
    }
    const create = {
      subject: academicsApi.createSubject,
      strand: academicsApi.createStrand,
      sub: academicsApi.createSubStrand,
      outcome: academicsApi.createOutcome,
    }
    const update = {
      subject: academicsApi.updateSubject,
      strand: academicsApi.updateStrand,
      sub: academicsApi.updateSubStrand,
      outcome: academicsApi.updateOutcome,
    }
    try {
      if (item?.id) await update[type](item.id, payloads[type])
      else await create[type](payloads[type])
      onSaved()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  const toggleGrade = (grade) => {
    setForm(current => ({
      ...current,
      grade_levels: current.grade_levels.includes(grade)
        ? current.grade_levels.filter(g => g !== grade)
        : [...current.grade_levels, grade],
    }))
  }

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="curriculum-form" loading={saving}>{item ? 'Save Changes' : 'Create'}</Button>
        </>
      }
    >
      <form id="curriculum-form" onSubmit={handleSubmit} className="space-y-4">
        {type === 'subject' && (
          <>
            <Input label="Subject Name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required />
            <Input label="Code" value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value }))} required />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Grade Levels</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {GRADE_LEVELS.map(grade => (
                  <label key={grade} className="flex items-center gap-2 rounded-lg border border-gray-100 px-3 py-2 text-sm">
                    <input type="checkbox" checked={form.grade_levels.includes(grade)} onChange={() => toggleGrade(grade)} />
                    {grade}
                  </label>
                ))}
              </div>
            </div>
            <label className="block text-sm font-medium text-gray-700">
              Description
              <textarea
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[var(--brand-primary)] focus:ring-2 focus:ring-[var(--brand-primary-ring)]"
                rows={3}
              />
            </label>
          </>
        )}

        {type === 'strand' && (
          <>
            <Input label="Strand Name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required />
            <input type="hidden" value={form.subject} />
          </>
        )}

        {type === 'sub' && (
          <>
            <Input label="Sub-strand Name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required />
            <input type="hidden" value={form.strand} />
          </>
        )}

        {type === 'outcome' && (
          <>
            <label className="block text-sm font-medium text-gray-700">
              Outcome Description
              <textarea
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-[var(--brand-primary)] focus:ring-2 focus:ring-[var(--brand-primary-ring)]"
                rows={4}
                required
              />
            </label>
            <input type="hidden" value={form.sub_strand} />
          </>
        )}
      </form>
    </Modal>
  )
}

function ItemActions({ item, onEdit, onDelete }) {
  const locked = item?.is_preloaded
  return (
    <div className="flex items-center gap-1">
      <button onClick={onEdit} className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"><Edit2 size={14} /></button>
      <button
        onClick={onDelete}
        disabled={locked}
        title={locked ? 'KNEC official - cannot delete' : 'Delete'}
        className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}

export default function CurriculumPage() {
  const [subjects, setSubjects] = useState([])
  const [subjectDetail, setSubjectDetail] = useState(null)
  const [activeId, setActiveId] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [modal, setModal] = useState(null)
  const [openStrands, setOpenStrands] = useState({})

  const fetchSubjects = async () => {
    setLoading(true)
    try {
      const { data } = await academicsApi.getSubjects()
      const list = listFromResponse(data)
      setSubjects(list)
      setActiveId(current => current || list[0]?.id || '')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchSubjects() }, [])

  useEffect(() => {
    if (!activeId) {
      setSubjectDetail(null)
      return
    }
    academicsApi.getSubject(activeId)
      .then(res => setSubjectDetail(res.data))
      .catch(() => setSubjectDetail(null))
  }, [activeId])

  const activeSubject = subjectDetail || subjects.find(subject => String(subject.id) === String(activeId))
  const filteredSubjects = useMemo(() => {
    const q = search.toLowerCase()
    return subjects.filter(subject => `${subject.name} ${subject.code}`.toLowerCase().includes(q))
  }, [subjects, search])

  const loadCurriculum = async () => {
    const confirmed = window.confirm('This will load all official KNEC subjects, strands, sub-strands and learning outcomes. This cannot be undone.')
    if (!confirmed) return
    setMessage('')
    try {
      const { data } = await academicsApi.loadCurriculum()
      setMessage(data?.message || `Curriculum loaded. ${data?.created || data?.count || 0} records added.`)
      fetchSubjects()
    } catch (err) {
      const detail = err.response?.data?.detail || err.response?.data?.message || err.response?.data?.error
      setMessage(detail || 'Curriculum already loaded')
    }
  }

  const deleteItem = async (type, item) => {
    if (item?.is_preloaded) return
    if (!window.confirm(`Delete ${item.name || item.description}?`)) return
    const calls = {
      subject: academicsApi.deleteSubject,
      strand: academicsApi.deleteStrand,
      sub: academicsApi.deleteSubStrand,
      outcome: academicsApi.deleteOutcome,
    }
    await calls[type](item.id)
    await fetchSubjects()
    if (type !== 'subject' && activeId) {
      const { data } = await academicsApi.getSubject(activeId)
      setSubjectDetail(data)
    }
  }

  const refreshCurriculum = async () => {
    await fetchSubjects()
    if (activeId) {
      const { data } = await academicsApi.getSubject(activeId)
      setSubjectDetail(data)
    }
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  return (
    <div className="space-y-6">
      <PageHeader
        title="Curriculum Management"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={loadCurriculum}>Load KNEC CBC Curriculum</Button>
            <Button onClick={() => setModal({ type: 'subject' })} className="gap-2"><Plus size={16} /> Add Subject</Button>
          </div>
        }
      />

      {message && <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">{message}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-5">
        <Card className="p-4">
          <div className="relative mb-4">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search subjects..."
              className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-3 text-sm outline-none focus:border-[var(--brand-primary)] focus:ring-2 focus:ring-[var(--brand-primary-ring)]"
            />
          </div>
          <div className="space-y-2">
            {filteredSubjects.length === 0 ? (
              <EmptyState icon={BookOpen} title="No subjects found" />
            ) : filteredSubjects.map(subject => (
              <button
                key={subject.id}
                onClick={() => setActiveId(subject.id)}
                className={`w-full rounded-lg border px-3 py-3 text-left transition ${String(activeId) === String(subject.id) ? 'border-[var(--brand-primary-ring)] bg-[var(--brand-primary-light)]' : 'border-gray-100 hover:bg-gray-50'}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-gray-900">{subject.name}</p>
                    <p className="text-xs text-gray-500">{subject.code}</p>
                  </div>
                  <Badge label={subject.is_active ? 'Active' : 'Inactive'} variant={subject.is_active ? 'active' : 'inactive'} />
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {(subject.grade_levels || []).map(grade => <Badge key={grade} label={grade} variant="default" />)}
                </div>
              </button>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          {!activeSubject ? (
            <EmptyState icon={BookOpen} title="Select a subject" />
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-gray-900">{activeSubject.name}</h2>
                    <span className="font-mono text-xs text-gray-500">{activeSubject.code}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {(activeSubject.grade_levels || []).map(grade => <Badge key={grade} label={grade} />)}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" onClick={() => setModal({ type: 'subject', item: activeSubject })}>Edit</Button>
                  <Button size="sm" onClick={() => setModal({ type: 'strand', parent: { subject: activeSubject.id } })} className="gap-1"><Plus size={14} /> Add Strand</Button>
                </div>
              </div>

              <div className="mt-4 space-y-3">
                {(activeSubject.strands || []).length === 0 ? (
                  <EmptyState icon={BookOpen} title="No strands yet" />
                ) : activeSubject.strands.map(strand => {
                  const open = openStrands[strand.id] ?? true
                  return (
                    <div key={strand.id} className="rounded-lg border border-gray-100">
                      <div className="flex items-center justify-between gap-2 px-4 py-3">
                        <button onClick={() => setOpenStrands(s => ({ ...s, [strand.id]: !open }))} className="flex items-center gap-2 font-medium text-gray-900">
                          <ChevronDown size={16} className={open ? '' : '-rotate-90'} /> {strand.name}
                        </button>
                        <div className="flex items-center gap-2">
                          <Button size="sm" variant="secondary" onClick={() => setModal({ type: 'sub', parent: { strand: strand.id } })}>Add Sub-strand</Button>
                          <ItemActions item={strand} onEdit={() => setModal({ type: 'strand', item: strand, parent: { subject: activeSubject.id } })} onDelete={() => deleteItem('strand', strand)} />
                        </div>
                      </div>
                      {open && (
                        <div className="space-y-3 border-t border-gray-100 p-4">
                          {(strand.sub_strands || []).map(sub => (
                            <div key={sub.id} className="rounded-lg bg-gray-50 p-3">
                              <div className="flex items-center justify-between gap-2">
                                <p className="font-medium text-gray-900">{sub.name}</p>
                                <div className="flex items-center gap-2">
                                  <Button size="sm" variant="secondary" onClick={() => setModal({ type: 'outcome', parent: { sub_strand: sub.id } })}>Add Learning Outcome</Button>
                                  <ItemActions item={sub} onEdit={() => setModal({ type: 'sub', item: sub, parent: { strand: strand.id } })} onDelete={() => deleteItem('sub', sub)} />
                                </div>
                              </div>
                              <div className="mt-3 space-y-2">
                                {(sub.outcomes || []).map(outcome => (
                                  <div key={outcome.id} className="flex items-start justify-between gap-3 rounded-lg bg-white px-3 py-2 text-sm">
                                    <p className="text-gray-700">{outcome.description}</p>
                                    <ItemActions item={outcome} onEdit={() => setModal({ type: 'outcome', item: outcome, parent: { sub_strand: sub.id } })} onDelete={() => deleteItem('outcome', outcome)} />
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </Card>
      </div>

      {modal && (
        <CurriculumForm
          {...modal}
          onClose={() => setModal(null)}
          onSaved={refreshCurriculum}
        />
      )}
    </div>
  )
}
