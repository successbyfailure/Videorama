import { useState } from 'react'
import { Download, Eye, Loader2, CheckCircle, XCircle } from 'lucide-react'
import Button from '@/components/Button'
import { useLibraries } from '@/hooks/useLibraries'
import api from '@/services/api'

interface ProbeResult {
  success: boolean
  url: string
  title?: string
  duration?: number
  thumbnail?: string
  uploader?: string
  platform?: string
  description?: string
  formats?: any[]
  error?: string
}

const FORMAT_OPTIONS = [
  { value: 'video_max', label: 'Video - Best Quality' },
  { value: 'video_1080', label: 'Video - 1080p' },
  { value: 'video_med', label: 'Video - 720p' },
  { value: 'video_low', label: 'Video - 480p' },
  { value: 'audio_max', label: 'Audio - Best Quality' },
  { value: 'audio_med', label: 'Audio - Medium Quality' },
  { value: 'audio_low', label: 'Audio - Low Quality' },
]

export default function URLImport() {
  const { data: libraries } = useLibraries(true)
  const [url, setUrl] = useState('')
  const [isProbing, setIsProbing] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [probeResult, setProbeResult] = useState<ProbeResult | null>(null)
  const [selectedLibrary, setSelectedLibrary] = useState<string>('')
  const [selectedFormat, setSelectedFormat] = useState('video_max')
  const [autoMode, setAutoMode] = useState(true)
  const [importResult, setImportResult] = useState<any>(null)

  const handleProbe = async () => {
    if (!url) return

    setIsProbing(true)
    setProbeResult(null)
    setImportResult(null)

    try {
      const response = await api.post<ProbeResult>('/import/probe', { url })
      setProbeResult(response.data)
    } catch (error: any) {
      setProbeResult({
        success: false,
        url,
        error: error.response?.data?.detail || error.message || 'Failed to probe URL',
      })
    } finally {
      setIsProbing(false)
    }
  }

  const handleImport = async (skipProbe = false) => {
    if (!url) return

    setIsImporting(true)
    setImportResult(null)

    try {
      const response = await api.post('/import/url', {
        url,
        library_id: selectedLibrary || null,
        format: selectedFormat,
        auto_mode: autoMode,
      })
      setImportResult(response.data)
      if (response.data.success) {
        // Reset form on success
        setUrl('')
        setProbeResult(null)
      }
    } catch (error: any) {
      setImportResult({
        success: false,
        error: error.response?.data?.detail || error.message || 'Import failed',
      })
    } finally {
      setIsImporting(false)
    }
  }

  const handleDirectImport = () => {
    setProbeResult(null)
    handleImport(true)
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'Unknown'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="space-y-6">
      {/* URL Input Section */}
      <div>
        <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-2">
          Video URL
        </label>
        <input
          id="url"
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=..."
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          disabled={isProbing || isImporting}
        />
        <p className="mt-1 text-sm text-gray-500">
          Supports YouTube, Vimeo, SoundCloud, Bandcamp, and many more
        </p>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <Button
          onClick={handleProbe}
          disabled={!url || isProbing || isImporting}
          variant="secondary"
          className="flex items-center gap-2"
        >
          {isProbing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Probing...
            </>
          ) : (
            <>
              <Eye className="w-4 h-4" />
              Preview
            </>
          )}
        </Button>

        <Button
          onClick={handleDirectImport}
          disabled={!url || isProbing || isImporting}
          variant="primary"
          className="flex items-center gap-2"
        >
          {isImporting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Importing...
            </>
          ) : (
            <>
              <Download className="w-4 h-4" />
              Import Now
            </>
          )}
        </Button>
      </div>

      {/* Probe Result - Preview */}
      {probeResult && probeResult.success && (
        <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
          <h3 className="text-lg font-semibold mb-4">Preview</h3>
          <div className="grid md:grid-cols-2 gap-6">
            {/* Thumbnail */}
            {probeResult.thumbnail && (
              <div>
                <img
                  src={probeResult.thumbnail}
                  alt={probeResult.title}
                  className="w-full rounded-lg"
                />
              </div>
            )}

            {/* Metadata */}
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-gray-500">Title</label>
                <p className="text-gray-900">{probeResult.title}</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-500">Duration</label>
                  <p className="text-gray-900">{formatDuration(probeResult.duration)}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">Platform</label>
                  <p className="text-gray-900 capitalize">{probeResult.platform}</p>
                </div>
              </div>

              {probeResult.uploader && (
                <div>
                  <label className="text-sm font-medium text-gray-500">Uploader</label>
                  <p className="text-gray-900">{probeResult.uploader}</p>
                </div>
              )}

              {probeResult.description && (
                <div>
                  <label className="text-sm font-medium text-gray-500">Description</label>
                  <p className="text-gray-900 text-sm line-clamp-3">
                    {probeResult.description}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Import Options */}
          <div className="mt-6 pt-6 border-t border-gray-200 space-y-4">
            <h4 className="font-medium text-gray-900">Import Options</h4>

            <div className="grid md:grid-cols-2 gap-4">
              {/* Library Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Library
                </label>
                <select
                  value={selectedLibrary}
                  onChange={(e) => setSelectedLibrary(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Auto-detect</option>
                  {libraries?.map((lib: any) => (
                    <option key={lib.id} value={lib.id}>
                      {lib.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Format Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Format
                </label>
                <select
                  value={selectedFormat}
                  onChange={(e) => setSelectedFormat(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  {FORMAT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Auto Mode Toggle */}
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="autoMode"
                checked={autoMode}
                onChange={(e) => setAutoMode(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
              />
              <label htmlFor="autoMode" className="text-sm text-gray-700">
                Auto-import (skip manual review if confidence is high)
              </label>
            </div>

            {/* Import Button */}
            <Button
              onClick={() => handleImport()}
              disabled={isImporting}
              variant="primary"
              className="w-full flex items-center justify-center gap-2"
            >
              {isImporting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Importing...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  Import with these options
                </>
              )}
            </Button>
          </div>
        </div>
      )}

      {/* Probe Error */}
      {probeResult && !probeResult.success && (
        <div className="border border-red-200 rounded-lg p-4 bg-red-50">
          <div className="flex items-start gap-3">
            <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-medium text-red-800">Preview Failed</h3>
              <p className="text-sm text-red-700 mt-1">{probeResult.error}</p>
              <p className="text-sm text-red-600 mt-2">
                You can still try importing directly - the URL might work even if preview failed.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Import Result */}
      {importResult && (
        <div
          className={`border rounded-lg p-4 ${
            importResult.success
              ? 'border-green-200 bg-green-50'
              : 'border-red-200 bg-red-50'
          }`}
        >
          <div className="flex items-start gap-3">
            {importResult.success ? (
              <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            ) : (
              <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1">
              <h3
                className={`text-sm font-medium ${
                  importResult.success ? 'text-green-800' : 'text-red-800'
                }`}
              >
                {importResult.success ? 'Import Started' : 'Import Failed'}
              </h3>
              <p
                className={`text-sm mt-1 ${
                  importResult.success ? 'text-green-700' : 'text-red-700'
                }`}
              >
                {importResult.success
                  ? `Job ID: ${importResult.job_id}. ${
                      importResult.entry_uuid
                        ? `Entry created: ${importResult.entry_uuid}`
                        : importResult.inbox_id
                        ? `Sent to inbox for review (${importResult.inbox_type})`
                        : 'Processing...'
                    }`
                  : importResult.error || 'An error occurred during import'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
