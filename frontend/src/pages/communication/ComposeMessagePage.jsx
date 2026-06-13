import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { communicationApi } from '@/api/communication'
import { studentsApi } from '@/api/students'
import api from '@/api/client'
import { Button, Card, Input, Select, Spinner } from '@/components/ui'
import {
  CHANNELS, GRADE_LEVELS, RECIPIENT_TYPES, TEMPLATE_CATEGORIES,
  extractVariables, listFromResponse,
} from './shared'
import { useAuthStore } from '@/store/authStore'

export default function ComposeMessagePage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const isTeacher = user?.role === 'teacher'
  const recipientOptions = isTeacher
    ? RECIPIENT_TYPES.filter(r => ['class', 'individual'].includes(r.value))
    : RECIPIENT_TYPES

  const [tab, setTab] = useState('freeform')
  const [templates, setTemplates] = useState([])
  const [classrooms, setClassrooms] = useState([])
  const [users, setUsers] = useState([])
  const [saving, setSaving] = useState(false)

  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [templateVars, setTemplateVars] = useState({})
  const [channels, setChannels] = useState(['sms'])
  const [recipientType, setRecipientType] = useState('class')
  const [recipientClass, setRecipientClass] = useState('')
  const [recipientGrade, setRecipientGrade] = useState('')
  const [recipientUser, setRecipientUser] = useState('')
  const [userSearch, setUserSearch] = useState('')
  const [scheduleMode, setScheduleMode] = useState('now')
  const [scheduledAt, setScheduledAt] = useState('')
  const [recurrence, setRecurrence] = useState({
    frequency: 'weekly', day: 'monday', day_of_month: 1, time: '08:00', end_date: '',
  })
  const [recipientCount, setRecipientCount] = useState(null)

  useEffect(() => {
    communicationApi.getTemplates({ is_active: true }).then(r => setTemplates(listFromResponse(r.data)))
    studentsApi.getClassrooms({ is_active: true }).then(r => setClassrooms(listFromResponse(r.data)))
    api.get('/auth/users/').then(r => setUsers(listFromResponse(r.data))).catch(() => {})
  }, [])

  const activeTemplate = templates.find(t => String(t.id) === String(selectedTemplate))
  const templateVariables = useMemo(
    () => extractVariables(activeTemplate?.body || ''),
    [activeTemplate]
  )

  const previewBody = useMemo(() => {
    if (tab === 'template' && activeTemplate) {
      let text = activeTemplate.body
      Object.entries(templateVars).forEach(([k, v]) => {
        text = text.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), v || `{{${k}}}`)
      })
      return text
    }
    return body
  }, [tab, activeTemplate, templateVars, body])

  useEffect(() => {
    if (recipientType === 'class' && recipientClass) {
      studentsApi.getClassroomStudents(recipientClass).then(r => {
        setRecipientCount(listFromResponse(r.data).length)
      }).catch(() => setRecipientCount(null))
    } else if (recipientType === 'grade' && recipientGrade) {
      studentsApi.getStudents({ classroom__grade_level: recipientGrade, is_active: true }).then(r => {
        setRecipientCount(listFromResponse(r.data).length)
      }).catch(() => setRecipientCount(null))
    } else if (recipientType === 'school') {
      studentsApi.getStudents({ is_active: true, page_size: 1 }).then(r => {
        setRecipientCount(r.data?.count ?? listFromResponse(r.data).length)
      }).catch(() => setRecipientCount(null))
    } else if (recipientType === 'individual') {
      setRecipientCount(recipientUser ? 1 : 0)
    } else if (recipientType === 'teachers') {
      setRecipientCount(users.filter(u => u.role === 'teacher' && u.is_active !== false).length)
    } else if (recipientType === 'staff') {
      setRecipientCount(users.filter(u => ['teacher', 'bursar', 'finance', 'admin'].includes(u.role)).length)
    } else {
      setRecipientCount(null)
    }
  }, [recipientType, recipientClass, recipientGrade, recipientUser, users])

  const toggleChannel = (id) => {
    setChannels(prev => prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id])
  }

  const buildPayload = () => ({
    title: title || activeTemplate?.name || 'Announcement',
    body: previewBody,
    template: tab === 'template' && activeTemplate ? activeTemplate.id : null,
    template_vars: tab === 'template' ? templateVars : {},
    channels,
    recipient_type: recipientType,
    recipient_class: recipientType === 'class' ? recipientClass || null : null,
    recipient_grade: recipientType === 'grade' ? recipientGrade : '',
    recipient_user: recipientType === 'individual' ? recipientUser || null : null,
    send_immediately: scheduleMode === 'now',
    scheduled_at: scheduleMode === 'schedule' && scheduledAt ? scheduledAt : null,
    is_recurring: scheduleMode === 'recurring',
    recurrence_rule: scheduleMode === 'recurring' ? recurrence : {},
  })

  const handleSave = async (send = false) => {
    if (!channels.length) return
    setSaving(true)
    try {
      const res = await communicationApi.createAnnouncement(buildPayload())
      if (send) {
        await communicationApi.sendAnnouncement(res.data.id)
      }
      navigate('/communication')
    } catch (err) {
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  const filteredUsers = users.filter(u => {
    const q = userSearch.toLowerCase()
    const name = `${u.first_name || ''} ${u.last_name || ''}`.toLowerCase()
    return !q || name.includes(q) || (u.email || '').toLowerCase().includes(q)
  })

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900">Compose Message</h1>
        <p className="mt-1 text-sm text-gray-500">Create and send announcements across multiple channels</p>
      </div>

      <div className="mb-4 flex gap-2">
        {['freeform', 'template'].map(t => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-lg px-4 py-2 text-sm font-medium ${tab === t ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border border-gray-200'}`}
          >
            {t === 'freeform' ? 'Free-form' : 'Use Template'}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {tab === 'freeform' ? (
            <Card className="space-y-4 p-5">
              <Input label="Title" value={title} onChange={e => setTitle(e.target.value)} />
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Message Body</label>
                <textarea
                  value={body}
                  onChange={e => setBody(e.target.value)}
                  rows={6}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
                <p className="mt-1 text-xs text-gray-400">{body.length} chars · {Math.ceil(body.length / 160) || 1} SMS segment(s)</p>
              </div>
            </Card>
          ) : (
            <Card className="space-y-4 p-5">
              <Select
                label="Template"
                value={selectedTemplate}
                onChange={e => { setSelectedTemplate(e.target.value); setTemplateVars({}) }}
              >
                <option value="">Select template...</option>
                {templates.map(t => (
                  <option key={t.id} value={t.id}>
                    {`${TEMPLATE_CATEGORIES.find(c => c.value === t.category)?.label || t.category} — ${t.name}`}
                  </option>
                ))}
              </Select>
              {activeTemplate && (
                <>
                  <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700 whitespace-pre-wrap">{activeTemplate.body}</div>
                  {templateVariables.map(v => (
                    <Input
                      key={v}
                      label={v.replace(/_/g, ' ')}
                      value={templateVars[v] || ''}
                      onChange={e => setTemplateVars(prev => ({ ...prev, [v]: e.target.value }))}
                    />
                  ))}
                </>
              )}
            </Card>
          )}

          <Card className="p-5">
            <h3 className="mb-3 font-medium text-gray-900">Channels</h3>
            <div className="flex flex-wrap gap-2">
              {CHANNELS.map(ch => (
                <button
                  key={ch.id}
                  type="button"
                  onClick={() => toggleChannel(ch.id)}
                  className={`rounded-lg border px-4 py-2 text-sm ${channels.includes(ch.id) ? 'border-blue-600 bg-blue-50 text-blue-700' : 'border-gray-200 text-gray-600'}`}
                >
                  {ch.label}
                  <span className="ml-1 text-xs text-gray-400">({ch.cost})</span>
                </button>
              ))}
            </div>
          </Card>

          <Card className="space-y-4 p-5">
            <h3 className="font-medium text-gray-900">Recipients</h3>
            <div className="flex flex-wrap gap-2">
              {recipientOptions.map(r => (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => setRecipientType(r.value)}
                  className={`rounded-lg border px-3 py-1.5 text-sm ${recipientType === r.value ? 'border-blue-600 bg-blue-50 text-blue-700' : 'border-gray-200 text-gray-600'}`}
                >
                  {r.label}
                </button>
              ))}
            </div>
            {recipientType === 'class' && (
              <Select label="Classroom" value={recipientClass} onChange={e => setRecipientClass(e.target.value)}>
                <option value="">Select class...</option>
                {classrooms.map(c => (
                  <option key={c.id} value={c.id}>{`${c.name}${c.stream ? ` ${c.stream}` : ''}`}</option>
                ))}
              </Select>
            )}
            {recipientType === 'grade' && (
              <Select label="Grade Level" value={recipientGrade} onChange={e => setRecipientGrade(e.target.value)}>
                <option value="">Select grade...</option>
                {GRADE_LEVELS.map(g => <option key={g} value={g}>{g}</option>)}
              </Select>
            )}
            {recipientType === 'individual' && (
              <div>
                <Input label="Search user" value={userSearch} onChange={e => setUserSearch(e.target.value)} />
                <Select label="Recipient" value={recipientUser} onChange={e => setRecipientUser(e.target.value)}>
                  <option value="">Select user...</option>
                  {filteredUsers.slice(0, 50).map(u => (
                    <option key={u.id} value={u.id}>
                      {`${u.first_name || ''} ${u.last_name || ''} (${u.email})`.trim()}
                    </option>
                  ))}
                </Select>
              </div>
            )}
            {recipientCount != null && recipientCount > 0 && (
              <p className="text-sm text-blue-600">Send to ~{recipientCount} recipient{recipientCount !== 1 ? 's' : ''}</p>
            )}
          </Card>

          <Card className="space-y-4 p-5">
            <h3 className="font-medium text-gray-900">Scheduling</h3>
            <div className="flex flex-wrap gap-4">
              {[
                { value: 'now', label: 'Send Now' },
                { value: 'schedule', label: 'Schedule' },
                { value: 'recurring', label: 'Recurring' },
              ].map(opt => (
                <label key={opt.value} className="flex items-center gap-2 text-sm">
                  <input type="radio" checked={scheduleMode === opt.value} onChange={() => setScheduleMode(opt.value)} />
                  {opt.label}
                </label>
              ))}
            </div>
            {scheduleMode === 'schedule' && (
              <Input label="Scheduled Date & Time" type="datetime-local" value={scheduledAt} onChange={e => setScheduledAt(e.target.value)} />
            )}
            {scheduleMode === 'recurring' && (
              <div className="grid grid-cols-2 gap-3">
                <Select label="Frequency" value={recurrence.frequency} onChange={e => setRecurrence(p => ({ ...p, frequency: e.target.value }))}>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </Select>
                {recurrence.frequency === 'weekly' && (
                  <Select label="Day" value={recurrence.day} onChange={e => setRecurrence(p => ({ ...p, day: e.target.value }))}>
                    {['monday','tuesday','wednesday','thursday','friday','saturday','sunday'].map(d => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </Select>
                )}
                {recurrence.frequency === 'monthly' && (
                  <Input label="Day of month" type="number" min={1} max={31} value={recurrence.day_of_month}
                    onChange={e => setRecurrence(p => ({ ...p, day_of_month: e.target.value }))} />
                )}
                <Input label="Time" type="time" value={recurrence.time} onChange={e => setRecurrence(p => ({ ...p, time: e.target.value }))} />
                <Input label="End date (optional)" type="date" value={recurrence.end_date} onChange={e => setRecurrence(p => ({ ...p, end_date: e.target.value }))} />
              </div>
            )}
          </Card>

          <div className="flex gap-3">
            <Button variant="secondary" loading={saving} onClick={() => handleSave(false)}>Save Draft</Button>
            <Button loading={saving} onClick={() => handleSave(true)}>
              {scheduleMode === 'now' ? 'Send Now' : 'Schedule'}
            </Button>
          </div>
        </div>

        <Card className="h-fit p-5">
          <h3 className="mb-3 font-medium text-gray-900">Live Preview</h3>
          <p className="mb-2 text-sm font-semibold text-gray-800">{title || activeTemplate?.name || 'Untitled'}</p>
          <p className="whitespace-pre-wrap text-sm text-gray-600">{previewBody || 'Message preview will appear here.'}</p>
        </Card>
      </div>
    </div>
  )
}
