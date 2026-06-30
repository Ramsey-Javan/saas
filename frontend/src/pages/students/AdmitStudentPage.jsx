import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowLeft, Camera, Edit2, UserPlus, X } from 'lucide-react'
import { studentsApi } from '@/api/students'
import { PageHeader, Card, Input, Select, Button } from '@/components/ui'

const studentFields = {
  admission_number: z.string().min(1, 'Required'),
  first_name: z.string().min(1, 'Required'),
  middle_name: z.string().optional(),
  last_name: z.string().min(1, 'Required'),
  gender: z.enum(['M', 'F'], { required_error: 'Required' }),
  date_of_birth: z.string().min(1, 'Required'),
  classroom: z.string().min(1, 'Required'),
  nemis_no: z.string().optional(),
  birth_certificate_no: z.string().optional(),
  blood_group: z.string().optional(),
  medical_notes: z.string().optional(),
}

const guardianFields = {
  guardian_first_name: z.string().min(1, 'Required'),
  guardian_last_name: z.string().min(1, 'Required'),
  guardian_phone: z.string().min(10, 'Enter a valid phone number'),
  guardian_relationship: z.string().min(1, 'Required'),
  guardian_national_id: z.string().optional(),
}

const createSchema = z.object({ ...studentFields, ...guardianFields })
const editSchema = z.object(studentFields)
const listFromResponse = (data) => data?.results || (Array.isArray(data) ? data : [])

export default function AdmitStudentPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isEditMode = Boolean(id)

  const [classrooms, setClassrooms] = useState([])
  const [submitError, setSubmitError] = useState('')
  const [loading, setLoading] = useState(isEditMode)
  const [photoPreview, setPhotoPreview] = useState(null)
  const [photoFile, setPhotoFile] = useState(null)

  const { register, handleSubmit, formState: { errors, isSubmitting }, reset } = useForm({
    resolver: zodResolver(isEditMode ? editSchema : createSchema),
  })

  useEffect(() => {
    studentsApi.getClassrooms().then(r => setClassrooms(listFromResponse(r.data)))
  }, [])

  useEffect(() => {
    if (!isEditMode) return

    const loadStudentData = async () => {
      setLoading(true)
      setSubmitError('')

      try {
        const { data: student } = await studentsApi.getStudent(id)
        setPhotoPreview(student.photo || null)

        reset({
          admission_number: student.admission_number || '',
          first_name: student.first_name || '',
          middle_name: student.middle_name || '',
          last_name: student.last_name || '',
          gender: student.gender || '',
          date_of_birth: student.date_of_birth || '',
          classroom: student.classroom?.toString() || '',
          nemis_no: student.nemis_no || '',
          birth_certificate_no: student.birth_certificate_no || '',
          blood_group: student.blood_group || '',
          medical_notes: student.medical_notes || '',
        })
      } catch (err) {
        console.error('Failed to load student:', err)
        setSubmitError('Failed to load student data.')
      } finally {
        setLoading(false)
      }
    }

    loadStudentData()
  }, [id, isEditMode, reset])

  const handlePhotoChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.size > 5 * 1024 * 1024) {
      setSubmitError('Photo must be less than 5MB.')
      return
    }

    setSubmitError('')
    setPhotoFile(file)

    const reader = new FileReader()
    reader.onloadend = () => setPhotoPreview(reader.result)
    reader.readAsDataURL(file)
  }

  const buildStudentFormData = (values, guardianId) => {
    const formData = new FormData()
    formData.append('admission_number', values.admission_number)
    formData.append('first_name', values.first_name)
    formData.append('middle_name', values.middle_name || '')
    formData.append('last_name', values.last_name)
    formData.append('gender', values.gender)
    formData.append('date_of_birth', values.date_of_birth)
    formData.append('classroom', values.classroom)
    formData.append('nemis_no', values.nemis_no || '')
    formData.append('birth_certificate_no', values.birth_certificate_no || '')
    formData.append('blood_group', values.blood_group || '')
    formData.append('medical_notes', values.medical_notes || '')

    if (guardianId) {
      formData.append('primary_guardian', guardianId)
    }

    if (photoFile) {
      formData.append('photo', photoFile)
    }

    return formData
  }

  const onSubmit = async (values) => {
    setSubmitError('')

    try {
      if (isEditMode) {
        await studentsApi.updateStudent(id, buildStudentFormData(values))
        navigate(`/students/${id}`)
        return
      }

      const guardianRes = await studentsApi.createGuardian({
        first_name: values.guardian_first_name,
        last_name: values.guardian_last_name,
        phone: values.guardian_phone,
        relationship: values.guardian_relationship,
        national_id: values.guardian_national_id || '',
      })

      await studentsApi.createStudent(buildStudentFormData(values, guardianRes.data.id))

      navigate('/students')
    } catch (err) {
      const data = err.response?.data
      const msg = data?.admission_number?.[0] ||
        data?.detail ||
        Object.values(data || {})[0]?.[0] ||
        'Failed to save student. Please try again.'
      setSubmitError(msg)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-4 border-[var(--brand-primary)] border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm text-gray-500">Loading student data...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <button
          onClick={() => navigate(isEditMode ? `/students/${id}` : '/students')}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 mb-4 transition-colors"
        >
          <ArrowLeft size={15} /> {isEditMode ? 'Back to Student' : 'Back to Students'}
        </button>
        <PageHeader
          title={isEditMode ? 'Edit Student' : 'Admit New Student'}
          description={isEditMode ? 'Update student details below.' : 'Fill in the student and guardian details below.'}
        />
      </div>

      {submitError && (
        <div className="mb-5 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
          {submitError}
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        <Card className="p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
            {isEditMode ? (
              <Edit2 size={16} className="text-[var(--brand-primary)]" />
            ) : (
              <UserPlus size={16} className="text-[var(--brand-primary)]" />
            )}
            Student Information
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input label="Admission Number *" placeholder="ADM/2024/001"
              {...register('admission_number')} error={errors.admission_number?.message} />
            <Select label="Class *" {...register('classroom')} error={errors.classroom?.message}>
              <option value="">Select class...</option>
              {classrooms.map(c => (
                <option key={c.id} value={c.id}>{c.name} ({c.academic_year})</option>
              ))}
            </Select>
            <Input label="First Name *" placeholder="e.g. Amani"
              {...register('first_name')} error={errors.first_name?.message} />
            <Input label="Middle Name" placeholder="Optional"
              {...register('middle_name')} error={errors.middle_name?.message} />
            <Input label="Last Name *" placeholder="e.g. Kamau"
              {...register('last_name')} error={errors.last_name?.message} />
            <Select label="Gender *" {...register('gender')} error={errors.gender?.message}>
              <option value="">Select...</option>
              <option value="M">Male</option>
              <option value="F">Female</option>
            </Select>
            <Input label="Date of Birth *" type="date"
              {...register('date_of_birth')} error={errors.date_of_birth?.message} />
            <Input label="NEMIS UPI Number" placeholder="Optional"
              {...register('nemis_no')} error={errors.nemis_no?.message} />
            <Input label="Birth Certificate No." placeholder="Optional"
              {...register('birth_certificate_no')} />
            <Select label="Blood Group" {...register('blood_group')}>
              <option value="">Unknown</option>
              {['A+','A-','B+','B-','AB+','AB-','O+','O-'].map(bg => (
                <option key={bg} value={bg}>{bg}</option>
              ))}
            </Select>
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Student Photo
              </label>
              <div className="flex items-center gap-4">
                {photoPreview ? (
                  <div className="relative">
                    <img
                      src={photoPreview}
                      alt="Preview"
                      className="h-24 w-24 rounded-lg object-cover border border-gray-200"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setPhotoPreview(null)
                        setPhotoFile(null)
                      }}
                      className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-red-500 text-white flex items-center justify-center hover:bg-red-600"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ) : (
                  <div className="h-24 w-24 rounded-lg bg-gray-100 border-2 border-dashed border-gray-300 flex items-center justify-center">
                    <Camera size={32} className="text-gray-400" />
                  </div>
                )}
                <div className="flex-1">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handlePhotoChange}
                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-[var(--brand-primary-light)] file:text-[var(--brand-primary)] hover:file:opacity-90"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    JPG, PNG or GIF. Max 5MB.
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Medical Notes</label>
            <textarea
              placeholder="Any allergies, conditions, or special needs..."
              rows={2}
              {...register('medical_notes')}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm outline-none focus:ring-2 focus:ring-[var(--brand-primary-ring)] focus:border-[var(--brand-primary)] resize-none"
            />
          </div>
        </Card>

        {!isEditMode && (
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Primary Guardian / Parent</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input label="First Name *" placeholder="e.g. John"
                {...register('guardian_first_name')} error={errors.guardian_first_name?.message} />
              <Input label="Last Name *" placeholder="e.g. Kamau"
                {...register('guardian_last_name')} error={errors.guardian_last_name?.message} />
              <Input label="Phone Number *" placeholder="0722 000 000"
                {...register('guardian_phone')} error={errors.guardian_phone?.message} />
              <Select label="Relationship *" {...register('guardian_relationship')} error={errors.guardian_relationship?.message}>
                <option value="">Select...</option>
                <option value="father">Father</option>
                <option value="mother">Mother</option>
                <option value="guardian">Guardian</option>
                <option value="sibling">Sibling</option>
                <option value="other">Other</option>
              </Select>
              <Input label="National ID" placeholder="Optional"
                {...register('guardian_national_id')} />
            </div>
          </Card>
        )}

        <div className="flex gap-3 justify-end pb-6">
          <Button type="button" variant="secondary" onClick={() => navigate(isEditMode ? `/students/${id}` : '/students')}>
            Cancel
          </Button>
          <Button type="submit" loading={isSubmitting}>
            {isEditMode ? 'Update Student' : 'Admit Student'}
          </Button>
        </div>
      </form>
    </div>
  )
}
