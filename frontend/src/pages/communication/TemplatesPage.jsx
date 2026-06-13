import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { communicationApi } from '@/api/communication'
import { Button, Card, EmptyState, Input, Select, Spinner } from '@/components/ui'
import { Modal } from '@/pages/academics/shared'
import {
  TEMPLATE_CATEGORIES, TEMPLATE_VARIABLES, extractVariables, listFromResponse,
} from './shared'

const CHANNEL_OPTIONS = [
  { value: 'all', label: 'All Channels' },
  { value: 'sms', label: 'SMS' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'email', label: 'Email' },
]

const SAMPLE_VARS = {
  student_name: 'John Kamau',
  guardian_name: 'Mary Kamau',
  school_name: 'Sample Academy',
  balance: 'KES 5,000',
  term: 'Term 1',
  class_name: 'Grade 5 East',
  date: new Date().toLocaleDateString(),
  admission_number: 'ADM-2024-001',
  subject_name: 'Mathematics',
  attendance_percentage: '92%',
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [categoryFilter, setCategoryFilter] = useState('')
  const [channelFilter, setChannelFilter] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [preview, setPreview] = useState(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    name: '', category: 'general', channel: 'all', subject: '', body: '', is_active: true,
  })

  const load = () => {
    setLoading(true)
    communicationApi.getTemplates({
      ...(categoryFilter && { category: categoryFilter }),
      ...(channelFilter && { channel: channelFilter }),
    }).then(r => setTemplates(listFromResponse(r.data))).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [categoryFilter, channelFilter])

  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', category: 'general', channel: 'all', subject: '', body: '', is_active: true })
    setModalOpen(true)
  }

  const openEdit = (t) => {
    setEditing(t)
    setForm({
      name: t.name, category: t.category, channel: t.channel,
      subject: t.subject || '', body: t.body, is_active: t.is_active,
    })
    setModalOpen(true)
  }

  const insertVariable = (v) => {
    setForm(prev => ({ ...prev, body: `${prev.body}{{${v}}}` }))
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      if (editing) {
        await communicationApi.updateTemplate(editing.id, form)
      } else {
        await communicationApi.createTemplate(form)
      }
      setModalOpen(false)
      load()
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this template?')) return
    await communicationApi.deleteTemplate(id)
    load()
  }

  const handlePreview = async (t) => {
    const res = await communicationApi.previewTemplate(t.id, SAMPLE_VARS)
    setPreview({ name: t.name, ...res.data })
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Message Templates</h1>
          <p className="mt-1 text-sm text-gray-500">Reusable templates with variable placeholders</p>
        </div>
        <Button onClick={openCreate}><Plus size={16} className="mr-1" /> New Template</Button>
      </div>

      <Card className="mb-6 flex flex-wrap gap-4 p-4">
        <Select label="Category" value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
          <option value="">All categories</option>
          {TEMPLATE_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </Select>
        <Select label="Channel" value={channelFilter} onChange={e => setChannelFilter(e.target.value)}>
          <option value="">All channels</option>
          {CHANNEL_OPTIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </Select>
      </Card>

      {loading ? (
        <div className="flex justify-center py-16"><Spinner /></div>
      ) : templates.length === 0 ? (
        <EmptyState title="No templates" description="Create your first message template." action={<Button onClick={openCreate}>New Template</Button>} />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {templates.map(t => (
            <Card key={t.id} className="flex flex-col p-5">
              <div className="mb-2 flex flex-wrap gap-2">
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs capitalize">{t.category}</span>
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs capitalize">{t.channel}</span>
              </div>
              <h3 className="font-semibold text-gray-900">{t.name}</h3>
              <p className="mt-2 line-clamp-3 text-sm text-gray-600">{t.body.slice(0, 100)}{t.body.length > 100 ? '…' : ''}</p>
              <div className="mt-3 flex flex-wrap gap-1">
                {extractVariables(t.body).map(v => (
                  <span key={v} className="rounded bg-yellow-50 px-1.5 py-0.5 text-xs text-yellow-700">{`{{${v}}}`}</span>
                ))}
              </div>
              <div className="mt-4 flex gap-2">
                <Button size="sm" variant="secondary" onClick={() => handlePreview(t)}>Preview</Button>
                <Button size="sm" variant="secondary" onClick={() => openEdit(t)}>Edit</Button>
                <Button size="sm" variant="danger" onClick={() => handleDelete(t.id)}>Delete</Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {modalOpen && (
        <Modal
          title={editing ? 'Edit Template' : 'New Template'}
          onClose={() => setModalOpen(false)}
          footer={
            <>
              <Button type="button" variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button>
              <Button type="submit" form="template-form" loading={saving}>Save</Button>
            </>
          }
        >
          <form id="template-form" onSubmit={handleSave} className="space-y-4">
            <Input label="Name" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} required />
            <Select label="Category" value={form.category} onChange={e => setForm(p => ({ ...p, category: e.target.value }))}>
              {TEMPLATE_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </Select>
            <Select label="Channel" value={form.channel} onChange={e => setForm(p => ({ ...p, channel: e.target.value }))}>
              {CHANNEL_OPTIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </Select>
            {(form.channel === 'email' || form.channel === 'all') && (
              <Input label="Email Subject" value={form.subject} onChange={e => setForm(p => ({ ...p, subject: e.target.value }))} />
            )}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Body</label>
              <textarea
                value={form.body}
                onChange={e => setForm(p => ({ ...p, body: e.target.value }))}
                rows={6}
                required
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
              />
              <div className="mt-2 flex flex-wrap gap-1">
                {TEMPLATE_VARIABLES.map(v => (
                  <button key={v} type="button" onClick={() => insertVariable(v)}
                    className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-200">{`{{${v}}}`}</button>
                ))}
              </div>
            </div>
          </form>
        </Modal>
      )}

      {preview && (
        <Modal title={`Preview: ${preview.name}`} onClose={() => setPreview(null)}
          footer={<Button onClick={() => setPreview(null)}>Close</Button>}>
          {preview.subject && <p className="mb-2 text-sm"><strong>Subject:</strong> {preview.subject}</p>}
          <p className="whitespace-pre-wrap text-sm text-gray-700">{preview.body}</p>
        </Modal>
      )}
    </div>
  )
}
