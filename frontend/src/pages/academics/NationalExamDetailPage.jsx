import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Download, Upload } from 'lucide-react'
import { academicsApi } from '@/api/academics'
import { Button, Card, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { LevelBadge, Modal, listFromResponse } from './shared'

const LEVELS = ['EE', 'ME', 'AE', 'BE']

function computeLevel(marks, total) {
  if (marks === '' || !total) return ''
  const pct = (Number(marks) / Number(total)) * 100
  if (pct >= 75) return 'EE'
  if (pct >= 50) return 'ME'
  if (pct >= 30) return 'AE'
  return 'BE'
}

function BulkIndexModal({ candidates, onClose, onDone }) {
  const [file, setFile] = useState(null)
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    const text = await file.text()
    const byAdmission = Object.fromEntries(candidates.map(candidate => [candidate.admission_number, candidate.id]))
    const updates = text.split(/\r?\n/).slice(1).map(line => {
      const [admissionNumber, indexNumber] = line.split(',').map(value => value?.trim())
      return byAdmission[admissionNumber] && indexNumber ? { candidate_id: byAdmission[admissionNumber], index_number: indexNumber } : null
    }).filter(Boolean)
    setSaving(true)
    try {
      const res = await academicsApi.bulkUpdateIndexNumbers({ updates })
      setMessage(`${res.data.updated || 0} index numbers updated, ${(res.data.errors || []).length} errors`)
      onDone()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Bulk Update Index Numbers" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Close</Button><Button type="submit" form="bulk-index-form" loading={saving}>Upload CSV</Button></>}>
      <form id="bulk-index-form" onSubmit={submit} className="space-y-4">
        <Input label="CSV File" type="file" accept=".csv,text/csv" onChange={e => setFile(e.target.files?.[0] || null)} required />
        {message && <div className="rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div>}
      </form>
    </Modal>
  )
}

function ImportResultsModal({ sessionId, onClose, onDone }) {
  const [file, setFile] = useState(null)
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    if (!file) return
    const data = new FormData()
    data.append('file', file)
    setSaving(true)
    try {
      const res = await academicsApi.importNationalExamCSV(sessionId, data)
      const created = res.data.created || 0
      const updated = res.data.updated || 0
      const errors = (res.data.errors || []).length
      setMessage(`${created} created, ${updated} updated, ${errors} errors`)
      onDone()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Import National Exam Results" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Close</Button><Button type="submit" form="national-import-form" loading={saving}>Upload CSV</Button></>}>
      <form id="national-import-form" onSubmit={submit} className="space-y-4">
        <Input label="CSV File (KNEC format)" type="file" accept=".csv,text/csv" onChange={e => setFile(e.target.files?.[0] || null)} required />
        {message && <div className="rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div>}
      </form>
    </Modal>
  )
}

export default function NationalExamDetailPage() {
  const { sessionId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const [tab, setTab] = useState(searchParams.get('tab') || 'candidates')
  const [session, setSession] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [subjects, setSubjects] = useState([])
  const [results, setResults] = useState({})
  const [dirtyResults, setDirtyResults] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [bulkOpen, setBulkOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [sessionRes, candidateRes, subjectRes] = await Promise.all([
        academicsApi.getNationalSession(sessionId),
        academicsApi.getCandidates({ session: sessionId }),
        academicsApi.getSubjects(),
      ])
      const candidateList = listFromResponse(candidateRes.data)
      setSession(sessionRes.data)
      setCandidates(candidateList)
      setSubjects(listFromResponse(subjectRes.data))
      const resultPairs = await Promise.all(candidateList.map(candidate => academicsApi.getNationalResults({ candidate: candidate.id })))
      const next = {}
      resultPairs.flatMap(res => listFromResponse(res.data)).forEach(result => {
        next[`${result.candidate}_${result.subject}`] = result
      })
      setResults(next)
      setDirtyResults({})
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => { fetchData() }, [fetchData])

  const setActiveTab = (next) => {
    setTab(next)
    setSearchParams({ tab: next })
  }

  const registerClass = async () => {
    const { data } = await academicsApi.registerClass(sessionId)
    setMessage(`${data.registered || 0} registered, ${data.already_existed || 0} already existed`)
    fetchData()
  }

  const updateCandidate = async (candidateId, patch) => {
    await academicsApi.updateCandidate(candidateId, patch)
    fetchData()
  }

  const visibleSubjects = useMemo(() => subjects.filter(subject => subject.is_active), [subjects])

  const changeResult = (candidate, subject, marks) => {
    const key = `${candidate.id}_${subject.id}`
    setDirtyResults(current => ({
      ...current,
      [key]: {
        candidate: candidate.id,
        subject: subject.id,
        marks,
        total_marks: 100,
        grade: computeLevel(marks, 100),
      },
    }))
  }

  const saveResults = async () => {
    const entries = Object.entries(dirtyResults)
    if (!entries.length) return
    setSaving(true)
    try {
      for (const [key, payload] of entries) {
        if (results[key]?.id) await academicsApi.updateNationalResult(results[key].id, payload)
        else await academicsApi.createNationalResult(payload)
      }
      setMessage(`${entries.length} results saved`)
      fetchData()
    } finally {
      setSaving(false)
    }
  }

  const markComplete = async () => {
    await academicsApi.updateNationalSession(sessionId, { is_results_entered: true })
    setMessage('Session marked complete')
    fetchData()
  }

  const downloadTemplate = async () => {
    const { data } = await academicsApi.downloadNationalExamCSV(sessionId)
    const filename = `${session?.name || 'national_exam'}_${session?.academic_year || ''}_template.csv`
    const url = window.URL.createObjectURL(new Blob([data], { type: 'text/csv;charset=utf-8;' }))
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    window.URL.revokeObjectURL(url)
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  return (
    <div className="space-y-5">
      <PageHeader title={`${session?.name || 'National Exam'} - ${session?.classroom_name || ''} - ${session?.academic_year || ''}`} />
      {message && <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">{message}</div>}
      <Card className="p-2">
        <div className="flex gap-2">
          {['candidates', 'results'].map(item => <button key={item} onClick={() => setActiveTab(item)} className={`rounded-lg px-4 py-2 text-sm font-medium capitalize ${tab === item ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}>{item}</button>)}
        </div>
      </Card>
      {tab === 'candidates' ? (
        <Card>
          <div className="flex flex-wrap justify-end gap-2 border-b border-gray-100 p-4">
            <Button variant="secondary" onClick={() => setBulkOpen(true)} className="gap-2"><Upload size={16} /> Bulk Update Index Numbers</Button>
            <Button onClick={registerClass}>Register All Students</Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-100">{['Student', 'Adm No', 'Index Number', 'Registered', 'Confirmed', 'Special Needs', 'Edit'].map(h => <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-gray-50">
                {candidates.map(candidate => (
                  <CandidateRow key={candidate.id} candidate={candidate} onSave={updateCandidate} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <Card>
          <div className="flex justify-end gap-2 border-b border-gray-100 p-4">
            <Button variant="secondary" onClick={downloadTemplate} className="gap-2"><Download size={16} /> Download CSV Template</Button>
            <Button variant="secondary" onClick={() => setImportOpen(true)} className="gap-2"><Upload size={16} /> Import CSV</Button>
            <Button variant="secondary" onClick={markComplete}>Mark Session Complete</Button>
            <Button onClick={saveResults} loading={saving}>Save All Results</Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-max min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="sticky left-0 bg-white px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Student</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Index No</th>
                  {visibleSubjects.map(subject => <th key={subject.id} className="min-w-[160px] px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">{subject.name}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {candidates.map(candidate => (
                  <tr key={candidate.id}>
                    <td className="sticky left-0 bg-white px-4 py-3 font-medium text-gray-900">{candidate.student_name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-600">{candidate.index_number || '-'}</td>
                    {visibleSubjects.map(subject => {
                      const key = `${candidate.id}_${subject.id}`
                      const value = dirtyResults[key] || results[key]
                      return (
                        <td key={subject.id} className="px-4 py-3">
                          <Input type="number" min="0" max="100" value={value?.marks ?? ''} onChange={e => changeResult(candidate, subject, e.target.value)} />
                          <div className="mt-1"><LevelBadge level={value?.grade || computeLevel(value?.marks, value?.total_marks || 100)} /></div>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {bulkOpen && <BulkIndexModal candidates={candidates} onClose={() => setBulkOpen(false)} onDone={fetchData} />}
      {importOpen && <ImportResultsModal sessionId={sessionId} onClose={() => setImportOpen(false)} onDone={fetchData} />}
    </div>
  )
}

function CandidateRow({ candidate, onSave }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    index_number: candidate.index_number || '',
    is_registered: candidate.is_registered,
    registration_confirmed: candidate.registration_confirmed,
    special_needs: candidate.special_needs || '',
  })
  useEffect(() => {
    setForm({
      index_number: candidate.index_number || '',
      is_registered: candidate.is_registered,
      registration_confirmed: candidate.registration_confirmed,
      special_needs: candidate.special_needs || '',
    })
  }, [candidate])
  return (
    <tr>
      <td className="px-4 py-3 font-medium text-gray-900">{candidate.student_name}</td>
      <td className="px-4 py-3 font-mono text-xs text-gray-600">{candidate.admission_number}</td>
      <td className="px-4 py-3">{editing ? <Input value={form.index_number} onChange={e => setForm(f => ({ ...f, index_number: e.target.value }))} /> : candidate.index_number || '-'}</td>
      <td className="px-4 py-3">{editing ? <input type="checkbox" checked={form.is_registered} onChange={e => setForm(f => ({ ...f, is_registered: e.target.checked }))} /> : candidate.is_registered ? 'Yes' : 'No'}</td>
      <td className="px-4 py-3">{editing ? <input type="checkbox" checked={form.registration_confirmed} onChange={e => setForm(f => ({ ...f, registration_confirmed: e.target.checked }))} /> : candidate.registration_confirmed ? 'Yes' : 'No'}</td>
      <td className="px-4 py-3">{editing ? <Input value={form.special_needs} onChange={e => setForm(f => ({ ...f, special_needs: e.target.value }))} /> : candidate.special_needs || '-'}</td>
      <td className="px-4 py-3">
        {editing ? (
          <div className="flex gap-2">
            <Button size="sm" onClick={() => { onSave(candidate.id, form); setEditing(false) }}>Save</Button>
            <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        ) : <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>Edit</Button>}
      </td>
    </tr>
  )
}
