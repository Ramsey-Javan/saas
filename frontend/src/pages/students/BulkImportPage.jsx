import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, Download, FileText, CheckCircle, XCircle, ArrowLeft } from 'lucide-react'
import { studentsApi } from '@/api/students'
import { PageHeader, Card, Button, Spinner } from '@/components/ui'

export default function BulkImportPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.csv')) {
        setError('Please select a CSV file')
        return
      }
      setFile(selectedFile)
      setError('')
      setResult(null)
    }
  }

  const downloadTemplate = async () => {
    try {
      const response = await studentsApi.downloadImportTemplate()
      const blob = response.data
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'student_import_template.csv'
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError('Failed to download template')
    }
  }

  const handleUpload = async () => {
    if (!file) return
    
    setUploading(true)
    setError('')
    setResult(null)
    
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await studentsApi.bulkImport(formData)
      setResult(response.data)
    } catch (err) {
      if (err.response?.status === 207) {
        // Partial success
        setResult(err.response.data)
      } else {
        setError(err.response?.data?.error || 'Failed to import students')
      }
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="max-w-3xl">
      <button
        onClick={() => navigate('/students')}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 mb-4 transition-colors"
      >
        <ArrowLeft size={15} /> Back to Students
      </button>

      <PageHeader
        title="Bulk Import Students"
        description="Upload a CSV file to admit multiple students at once"
      />

      {error && (
        <div className="mb-5 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-2">
          <XCircle size={16} /> {error}
        </div>
      )}

      {result && (
        <div className="mb-5 space-y-3">
          <div className="px-4 py-3 rounded-lg bg-green-50 border border-green-200 text-green-700 text-sm flex items-center gap-2">
            <CheckCircle size={16} />
            Successfully imported {result.success_count} students
          </div>
          
          {result.errors && result.errors.length > 0 && (
            <Card className="p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                <XCircle size={16} className="text-red-500" />
                {result.total_errors} errors occurred
              </h3>
              <div className="max-h-64 overflow-y-auto space-y-1">
                {result.errors.map((err, idx) => (
                  <div key={idx} className="text-xs text-red-600 py-1 border-b border-red-100 last:border-0">
                    Row {err.row}: {err.error}
                  </div>
                ))}
              </div>
            </Card>
          )}
          
          <Button onClick={() => navigate('/students')} className="mt-4">
            View Imported Students
          </Button>
        </div>
      )}

      <Card className="p-6">
        <div className="space-y-6">
          {/* Template Download */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-2">1. Download Template</h3>
            <p className="text-sm text-gray-500 mb-3">
              Download our CSV template and fill in student details
            </p>
            <Button variant="secondary" onClick={downloadTemplate} className="gap-2">
              <Download size={16} /> Download CSV Template
            </Button>
          </div>

          <div className="border-t border-gray-100" />

          {/* File Upload */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-2">2. Upload CSV File</h3>
            <p className="text-sm text-gray-500 mb-3">
              Select your filled CSV file to import
            </p>
            
            <div className="border-2 border-dashed border-gray-200 rounded-lg p-8 text-center">
              <input
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                className="hidden"
                id="csv-upload"
              />
              <label
                htmlFor="csv-upload"
                className="cursor-pointer flex flex-col items-center"
              >
                <FileText size={48} className="text-gray-300 mb-3" />
                <span className="text-sm font-medium text-gray-700">
                  {file ? file.name : 'Click to select CSV file'}
                </span>
                <span className="text-xs text-gray-500 mt-1">
                  Only .csv files are accepted
                </span>
              </label>
            </div>

            {file && (
              <div className="mt-4 flex items-center justify-between p-3 bg-[var(--brand-primary-light)] rounded-lg">
                <div className="flex items-center gap-2">
                  <Upload size={16} className="text-[var(--brand-primary)]" />
                  <span className="text-sm text-[var(--brand-primary)]">{file.name}</span>
                </div>
                <button
                  onClick={() => {
                    setFile(null)
                    setResult(null)
                    setError('')
                  }}
                  className="text-xs text-[var(--brand-primary)] hover:underline"
                >
                  Remove
                </button>
              </div>
            )}
          </div>

          {/* Upload Button */}
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="secondary"
              onClick={() => navigate('/students')}
              disabled={uploading}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="gap-2"
            >
              {uploading ? (
                <>
                  <Spinner size={16} /> Importing...
                </>
              ) : (
                <>
                  <Upload size={16} /> Import Students
                </>
              )}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
