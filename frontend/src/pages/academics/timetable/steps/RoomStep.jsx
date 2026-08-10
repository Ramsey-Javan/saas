import { useState } from 'react'
import { ChevronLeft, ChevronRight, Plus, Trash2 } from 'lucide-react'
import { Button, Card, Input, Select } from '@/components/ui'
import { timetablingApi } from '@/api/timetabling'

const ROOM_TYPES = [
  { value: 'classroom', label: 'Classroom' },
  { value: 'lab', label: 'Lab' },
  { value: 'hall', label: 'Hall' },
  { value: 'library', label: 'Library' },
  { value: 'field', label: 'Field' },
  { value: 'other', label: 'Other' },
]

export default function RoomsStep({ rooms, setRooms, onBack, onNext }) {
  const [roomForm, setRoomForm] = useState({ name: '', room_type: 'classroom', capacity: '' })
  const [saving, setSaving] = useState(false)
  const [editingRoom, setEditingRoom] = useState(null)

  const saveRoom = async () => {
    if (!roomForm.name.trim()) return
    setSaving(true)
    try {
      if (editingRoom) {
        const { data } = await timetablingApi.updateRoom(editingRoom.id, {
          name: roomForm.name.trim(),
          room_type: roomForm.room_type,
          capacity: roomForm.capacity ? parseInt(roomForm.capacity) : null,
        })
        setRooms((prev) => prev.map((r) => (r.id === editingRoom.id ? data : r)))
        setEditingRoom(null)
      } else {
        const { data } = await timetablingApi.createRoom({
          name: roomForm.name.trim(),
          room_type: roomForm.room_type,
          capacity: roomForm.capacity ? parseInt(roomForm.capacity) : null,
        })
        setRooms((prev) => [...prev, data])
      }
      setRoomForm({ name: '', room_type: 'classroom', capacity: '' })
    } finally {
      setSaving(false)
    }
  }

  const startEditRoom = (room) => {
    setEditingRoom(room)
    setRoomForm({ name: room.name, room_type: room.room_type, capacity: room.capacity || '' })
  }

  const deleteRoom = async (id) => {
    if (!window.confirm('Delete this room?')) return
    setSaving(true)
    try {
      await timetablingApi.deleteRoom?.(id).catch(() => {})
      setRooms((prev) => prev.filter((r) => r.id !== id))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <h3 className="mb-1 text-base font-semibold text-gray-900">
          {editingRoom ? 'Edit Room' : 'Add Shared Rooms'}
        </h3>
        <p className="mb-4 text-sm text-gray-500">
          Only add special rooms like labs or halls. Regular classrooms are handled automatically.
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <div className="sm:col-span-2">
            <Input
              label="Room Name"
              value={roomForm.name}
              onChange={(e) => setRoomForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Science Lab 1"
            />
          </div>
          <div>
            <Select label="Type" value={roomForm.room_type} onChange={(e) => setRoomForm((f) => ({ ...f, room_type: e.target.value }))}>
              {ROOM_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </Select>
          </div>
          <div>
            <Input label="Capacity" type="number" value={roomForm.capacity} onChange={(e) => setRoomForm((f) => ({ ...f, capacity: e.target.value }))} placeholder="40" />
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <Button onClick={saveRoom} loading={saving} disabled={!roomForm.name.trim()}>
            <Plus size={16} className="mr-1" /> {editingRoom ? 'Update Room' : 'Add Room'}
          </Button>
          {editingRoom && (
            <Button variant="secondary" onClick={() => { setEditingRoom(null); setRoomForm({ name: '', room_type: 'classroom', capacity: '' }) }}>
              Cancel
            </Button>
          )}
        </div>
      </Card>

      {rooms.length > 0 && (
        <Card className="p-5">
          <h3 className="mb-3 text-base font-semibold text-gray-900">Saved Rooms</h3>
          <div className="divide-y divide-gray-100">
            {rooms.map((r) => (
              <div key={r.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="font-medium text-gray-900">{r.name}</p>
                  <p className="text-xs text-gray-500">
                    {ROOM_TYPES.find((t) => t.value === r.room_type)?.label || r.room_type}
                    {r.capacity ? ` · Capacity ${r.capacity}` : ''}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => startEditRoom(r)}>Edit</Button>
                  <button onClick={() => deleteRoom(r.id)} className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600">
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="flex justify-between">
        <Button variant="secondary" onClick={onBack}>
          <ChevronLeft size={16} className="mr-1" /> Back
        </Button>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={onNext}>Skip</Button>
          <Button onClick={onNext}>Next: Subjects <ChevronRight size={16} className="ml-1" /></Button>
        </div>
      </div>
    </div>
  )
}