import { useState } from 'react'
import { Search, Download, Loader2, CheckCircle, XCircle } from 'lucide-react'
import Button from '@/components/Button'
import { useLibraries } from '@/hooks/useLibraries'
import api from '@/services/api'

interface SearchResult {
  id: string
  title: string
  url: string
  duration?: number
  thumbnail?: string
  uploader?: string
  platform?: string
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

// Helper to get thumbnail URL
function getThumbnailUrl(result: SearchResult): string | null {
  // If thumbnail is already provided, use it
  if (result.thumbnail) return result.thumbnail

  // Generate thumbnail for YouTube videos
  if (result.platform === 'youtube' && result.id) {
    return `https://i.ytimg.com/vi/${result.id}/mqdefault.jpg`
  }

  return null
}

export default function SearchImport() {
  const { data: libraries } = useLibraries(true)
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [results, setResults] = useState<SearchResult[]>([])
  const [searchError, setSearchError] = useState<string | null>(null)
  const [importingId, setImportingId] = useState<string | null>(null)
  const [importResults, setImportResults] = useState<Map<string, any>>(new Map())

  const handleSearch = async () => {
    if (!query) return

    setIsSearching(true)
    setSearchError(null)
    setResults([])

    try {
      const response = await api.post('/import/search', {
        query,
        limit: 20,
      })

      if (response.data.success) {
        setResults(response.data.results)
      } else {
        setSearchError(response.data.error || 'Search failed')
      }
    } catch (error: any) {
      setSearchError(
        error.response?.data?.detail || error.message || 'Failed to search'
      )
    } finally {
      setIsSearching(false)
    }
  }

  const handleImport = async (result: SearchResult, library?: string, format?: string) => {
    setImportingId(result.id)

    try {
      const response = await api.post('/import/url', {
        url: result.url,
        library_id: library || null,
        format: format || 'video_max',
        auto_mode: true,
      })

      // Store result
      const newResults = new Map(importResults)
      newResults.set(result.id, response.data)
      setImportResults(newResults)
    } catch (error: any) {
      const newResults = new Map(importResults)
      newResults.set(result.id, {
        success: false,
        error: error.response?.data?.detail || error.message || 'Import failed',
      })
      setImportResults(newResults)
    } finally {
      setImportingId(null)
    }
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'Unknown'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const getImportStatus = (resultId: string) => {
    return importResults.get(resultId)
  }

  return (
    <div className="space-y-6">
      {/* Search Input */}
      <div>
        <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-2">
          Search Query
        </label>
        <div className="flex gap-3">
          <input
            id="search"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search for videos, music, podcasts..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isSearching}
          />
          <Button
            onClick={handleSearch}
            disabled={!query || isSearching}
            variant="primary"
            className="flex items-center gap-2"
          >
            {isSearching ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Searching...
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                Search
              </>
            )}
          </Button>
        </div>
        <p className="mt-1 text-sm text-gray-500">
          Search across YouTube, SoundCloud, Bandcamp, and more
        </p>
      </div>

      {/* Search Error */}
      {searchError && (
        <div className="border border-yellow-200 rounded-lg p-4 bg-yellow-50">
          <div className="flex items-start gap-3">
            <XCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-medium text-yellow-800">Search Failed</h3>
              <p className="text-sm text-yellow-700 mt-1">{searchError}</p>
              <p className="text-sm text-yellow-600 mt-2">
                Make sure VHS is running and search is enabled.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-4">
            Results ({results.length})
          </h3>
          <div className="space-y-4">
            {results.map((result) => {
              const importStatus = getImportStatus(result.id)
              const isImporting = importingId === result.id

              const thumbnailUrl = getThumbnailUrl(result)

              return (
                <div
                  key={result.id}
                  className="border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
                >
                  <div className="flex gap-4">
                    {/* Thumbnail */}
                    {thumbnailUrl && (
                      <div className="flex-shrink-0">
                        <img
                          src={thumbnailUrl}
                          alt={result.title}
                          className="w-40 h-24 object-cover rounded"
                        />
                      </div>
                    )}

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <h4 className="font-medium text-gray-900 truncate">
                        {result.title}
                      </h4>
                      <div className="mt-1 flex items-center gap-4 text-sm text-gray-500">
                        {result.uploader && <span>{result.uploader}</span>}
                        {result.duration && <span>{formatDuration(result.duration)}</span>}
                        {result.platform && (
                          <span className="capitalize">{result.platform}</span>
                        )}
                      </div>

                      {/* Import Status */}
                      {importStatus && (
                        <div className="mt-2">
                          {importStatus.success ? (
                            <div className="flex items-center gap-2 text-sm text-green-600">
                              <CheckCircle className="w-4 h-4" />
                              <span>
                                {importStatus.entry_uuid
                                  ? 'Imported successfully'
                                  : importStatus.inbox_id
                                  ? 'Sent to inbox for review'
                                  : 'Import started'}
                              </span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 text-sm text-red-600">
                              <XCircle className="w-4 h-4" />
                              <span>{importStatus.error || 'Import failed'}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Import Button */}
                    <div className="flex-shrink-0 flex items-start">
                      <Button
                        onClick={() => handleImport(result)}
                        disabled={isImporting || !!importStatus?.success}
                        variant="secondary"
                        size="small"
                        className="flex items-center gap-2"
                      >
                        {isImporting ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Importing...
                          </>
                        ) : importStatus?.success ? (
                          <>
                            <CheckCircle className="w-4 h-4" />
                            Imported
                          </>
                        ) : (
                          <>
                            <Download className="w-4 h-4" />
                            Import
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* No Results */}
      {!isSearching && !searchError && results.length === 0 && query && (
        <div className="text-center py-12 text-gray-500">
          <Search className="w-12 h-12 mx-auto mb-4 text-gray-400" />
          <p>No results found for "{query}"</p>
          <p className="text-sm mt-1">Try a different search term</p>
        </div>
      )}

      {/* Empty State */}
      {!query && results.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          <Search className="w-12 h-12 mx-auto mb-4 text-gray-400" />
          <p>Enter a search term to find videos</p>
        </div>
      )}
    </div>
  )
}
