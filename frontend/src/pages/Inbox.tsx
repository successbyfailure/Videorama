import { useState } from 'react'
import { Check, X, AlertCircle, Copy, Zap, RefreshCw, Wand2 } from 'lucide-react'
import Card from '@/components/Card'
import Button from '@/components/Button'
import {
  useInboxItems,
  useApproveInboxItem,
  useRejectInboxItem,
} from '@/hooks/useInbox'
import { useLibraries } from '@/hooks/useLibraries'
import { inboxApi } from '@/services/api'
import { useQueryClient } from '@tanstack/react-query'

export default function Inbox() {
  const [selectedType, setSelectedType] = useState<string | undefined>()
  const [showReviewed, setShowReviewed] = useState(false)
  const [edits, setEdits] = useState<
    Record<
      string,
      {
        title: string
        tags: string
        properties: string
        subfolder: string
      }
    >
  >({})
  const [metaPreview, setMetaPreview] = useState<Record<string, any>>({})
  const [librarySelection, setLibrarySelection] = useState<Record<string, string>>({})
  const queryClient = useQueryClient()

  const { data: inboxItems, isLoading } = useInboxItems({
    inbox_type: selectedType,
    reviewed: showReviewed || undefined,
    limit: 50,
  })
  const { data: libraries } = useLibraries(true)
  const approveItem = useApproveInboxItem()
  const rejectItem = useRejectInboxItem()

  const getEditState = (itemId: string) => edits[itemId]
  const getSelectedLibrary = (itemId: string, suggested?: string | null) =>
    librarySelection[itemId] ?? suggested ?? ''

  const initEditState = (itemId: string, entryData: any, suggested: any) => {
    if (edits[itemId]) return edits[itemId]

    const classification = suggested?.classification || suggested || {}
    const suggestedProps =
      classification?.properties ||
      suggested?.properties ||
      suggested?.enriched?.properties ||
      entryData?.metadata?.properties ||
      {}

    const suggestedTags =
      classification?.tags || suggested?.tags || entryData?.tags || []

    const subfolder =
      classification?.subfolder ||
      entryData?.metadata?.subfolder ||
      entryData?.subfolder ||
      ''

    const newState = {
      title: entryData?.title || '',
      tags: Array.isArray(suggestedTags) ? suggestedTags.join(', ') : '',
      properties:
        Object.keys(suggestedProps).length > 0
          ? JSON.stringify(suggestedProps, null, 2)
          : '',
      subfolder: typeof subfolder === 'string' ? subfolder : '',
    }

    setEdits((prev) => ({ ...prev, [itemId]: newState }))
    setMetaPreview((prev) => ({ ...prev, [itemId]: { metadata: entryData?.metadata, enriched: entryData?.enriched, suggested } }))
    return newState
  }

  const handleApprove = async (
    id: string,
    libraryId: string,
    editState?: { title: string; tags: string; properties: string }
  ) => {
    const override: any = { library_id: libraryId }

    if (editState) {
      const tags = editState.tags
        ? editState.tags
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean)
        : []

      let properties: Record<string, any> = {}
      if (editState.properties?.trim()) {
        try {
          properties = JSON.parse(editState.properties)
        } catch (e) {
          alert('Properties must be valid JSON')
          return
        }
      }

      override.metadata_override = {
        title: editState.title || undefined,
        tags,
        properties,
        subfolder: editState.subfolder || undefined,
      }
    }

    try {
      await approveItem.mutateAsync({
        id,
        approval: override,
      })
    } catch (error: any) {
      const message =
        error?.response?.data?.detail || error?.message || 'Failed to approve item'
      alert(message)
    }
  }

  const handleReject = async (id: string) => {
    if (!confirm('Are you sure you want to reject this item?')) return

    try {
      await rejectItem.mutateAsync(id)
    } catch (error: any) {
      const message =
        error?.response?.data?.detail || error?.message || 'Failed to reject item'
      alert(message)
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'duplicate':
        return <Copy className="text-yellow-600" size={20} />
      case 'low_confidence':
        return <Zap className="text-orange-600" size={20} />
      case 'failed':
        return <AlertCircle className="text-red-600" size={20} />
      default:
        return <AlertCircle className="text-blue-600" size={20} />
    }
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'duplicate':
        return 'Duplicate'
      case 'low_confidence':
        return 'Low Confidence'
      case 'failed':
        return 'Failed'
      default:
        return 'Needs Review'
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Inbox
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Review and process pending items
        </p>
      </div>

      {/* Filters */}
      <Card padding="medium">
        <div className="flex items-center gap-4 flex-wrap">
          <select
            value={selectedType || ''}
            onChange={(e) => setSelectedType(e.target.value || undefined)}
            className="input-field max-w-xs"
          >
            <option value="">All Types</option>
            <option value="low_confidence">Low Confidence</option>
            <option value="duplicate">Duplicate</option>
            <option value="failed">Failed</option>
            <option value="needs_review">Needs Review</option>
          </select>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={showReviewed}
              onChange={(e) => setShowReviewed(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Show reviewed
            </span>
          </label>
        </div>
      </Card>

      {/* Inbox Items */}
      {isLoading ? (
        <div className="text-center py-12">Loading inbox...</div>
      ) : inboxItems && inboxItems.length > 0 ? (
        <div className="space-y-4">
          {inboxItems.map((item) => {
            const entryData = item.entry_data || {}
            const suggestedMetadata = item.suggested_metadata || {}
            const mergedEntryData = metaPreview[item.id]?.entry_data || entryData
            const mergedSuggested = metaPreview[item.id]?.suggested || suggestedMetadata
            const mergedMetadata = metaPreview[item.id]?.metadata || mergedEntryData?.metadata
            const hasSourceUrl = !!mergedEntryData.original_url
            const state =
              getEditState(item.id) || initEditState(item.id, mergedEntryData, mergedSuggested)

            return (
              <Card key={item.id} padding="medium">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 mt-1">{getTypeIcon(item.type)}</div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded text-xs font-medium">
                        {getTypeLabel(item.type)}
                      </span>
                      {item.confidence !== null && (
                        <span className="text-sm text-gray-600 dark:text-gray-400">
                          Confidence: {(item.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                      {item.reviewed && (
                        <span className="px-2 py-1 bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 rounded text-xs font-medium">
                          Reviewed
                        </span>
                      )}
                    </div>

                    <h3 className="font-semibold text-gray-900 dark:text-white mb-1">
                      {mergedEntryData.title || 'Untitled'}
                    </h3>

                    {mergedEntryData.original_url && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 mb-2 truncate">
                        {mergedEntryData.original_url}
                      </p>
                    )}

                    {(metaPreview[item.id]?.error_message || item.error_message) && (
                      <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-700 dark:text-red-300">
                        {metaPreview[item.id]?.error_message || item.error_message}
                      </div>
                    )}

                    {!item.reviewed && (
                      <div className="mt-3 space-y-2">
                        <div>
                          <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                            Title
                          </label>
                          <input
                            className="input-field w-full text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-800"
                            value={
                              state?.title ?? mergedEntryData?.title ?? ''
                            }
                            onChange={(e) =>
                              setEdits((prev) => ({
                                ...prev,
                                [item.id]: { ...(state || {}), title: e.target.value },
                              }))
                            }
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                            Subfolder (within library)
                          </label>
                          <input
                            className="input-field w-full text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-800"
                            value={
                              state?.subfolder ??
                              mergedSuggested?.subfolder ??
                              mergedEntryData?.subfolder ??
                              ''
                            }
                            onChange={(e) =>
                              setEdits((prev) => ({
                                ...prev,
                                [item.id]: { ...(state || {}), subfolder: e.target.value },
                              }))
                            }
                            placeholder="videos/2024"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                            Tags (comma separated)
                          </label>
                          <input
                            className="input-field w-full text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-800"
                            value={state?.tags || ''}
                            onChange={(e) =>
                              setEdits((prev) => ({
                                ...prev,
                                [item.id]: { ...(state || {}), tags: e.target.value },
                              }))
                            }
                            placeholder="rock, live, 2024"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                            Properties (JSON)
                          </label>
                          <textarea
                            className="input-field w-full text-sm font-mono text-gray-900 dark:text-white bg-white dark:bg-gray-800"
                            rows={3}
                            value={state?.properties || ''}
                            onChange={(e) =>
                              setEdits((prev) => ({
                                ...prev,
                                [item.id]: { ...(state || {}), properties: e.target.value },
                              }))
                            }
                            placeholder='{"platform":"youtube","artist":"..."}'
                          />
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    {!item.reviewed && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {hasSourceUrl ? (
                          <>
                            <Button
                              size="small"
                              variant="secondary"
                              onClick={async () => {
                            try {
                              const res = await inboxApi.reprobe(item.id)
                              setMetaPreview((prev) => ({
                                ...prev,
                                [item.id]: {
                                  ...(prev[item.id] || {}),
                                  metadata: res.metadata,
                                  entry_data: res.entry_data,
                                  error_message: null,
                                },
                              }))
                              setEdits((prev) => ({
                                ...prev,
                                [item.id]: {
                                  ...(state || {}),
                                  title:
                                    res.metadata?.title ||
                                    res.metadata?.fulltitle ||
                                    res.entry_data?.title ||
                                    mergedEntryData?.original_url ||
                                    '',
                                },
                              }))
                              queryClient.invalidateQueries({ queryKey: ['inbox'] })
                              alert('Probe updated')
                            } catch (err: any) {
                              alert(
                                err?.response?.data?.detail || err?.message || 'Probe failed'
                              )
                                }
                              }}
                              leftIcon={<RefreshCw size={14} />}
                            >
                              Re-probe VHS
                            </Button>
                            <Button
                              size="small"
                              variant="secondary"
                              onClick={async () => {
                                try {
                              const res = await inboxApi.redownload(item.id)
                              setMetaPreview((prev) => ({
                                ...prev,
                                [item.id]: {
                                  ...(prev[item.id] || {}),
                                  entry_data: res.entry_data,
                                  error_message: null,
                                },
                              }))
                              queryClient.invalidateQueries({ queryKey: ['inbox'] })
                              alert('Re-downloaded')
                            } catch (err: any) {
                              alert(
                                err?.response?.data?.detail ||
                                  err?.message ||
                                      'Redownload failed'
                                  )
                                }
                              }}
                              leftIcon={<RefreshCw size={14} />}
                            >
                              Re-download
                            </Button>
                          </>
                        ) : (
                          <div className="text-xs text-gray-600 dark:text-gray-400 px-2 py-1">
                            No source URL stored; re-probe and re-download not available.
                          </div>
                        )}
                        <Button
                          size="small"
                          variant="secondary"
                          onClick={async () => {
                            try {
                              const res = await inboxApi.reclassify(item.id)
                              // update suggested library/confidence
                              item.suggested_library = res.suggested_library
                              item.confidence = res.confidence
                              queryClient.invalidateQueries({ queryKey: ['inbox'] })
                              alert('Re-classified')
                            } catch (err: any) {
                              alert(err?.response?.data?.detail || err?.message || 'Reclassify failed')
                            }
                          }}
                          leftIcon={<Wand2 size={14} />}
                        >
                          Re-classify AI
                        </Button>
                      </div>
                    )}

                    {/* Metadata preview */}
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                      <div className="border border-gray-200 dark:border-gray-700 rounded p-2 text-xs">
                        <div className="font-semibold mb-1">Probe metadata</div>
                        <pre className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                          {JSON.stringify(metaPreview[item.id]?.metadata || mergedEntryData?.metadata || {}, null, 2)}
                        </pre>
                      </div>
                      <div className="border border-gray-200 dark:border-gray-700 rounded p-2 text-xs">
                        <div className="font-semibold mb-1">Suggested / Enriched</div>
                        <pre className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                          {JSON.stringify(
                            metaPreview[item.id]?.suggested || item.suggested_metadata || {},
                            null,
                            2
                          )}
                        </pre>
                      </div>
                    </div>
                  </div>

                  {!item.reviewed && (
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <select
                        className="input-field text-sm w-40"
                        value={getSelectedLibrary(item.id, item.suggested_library)}
                        onChange={(e) =>
                          setLibrarySelection((prev) => ({ ...prev, [item.id]: e.target.value }))
                        }
                      >
                        <option value="">Select library...</option>
                        {libraries?.map((lib) => (
                          <option key={lib.id} value={lib.id}>
                            {lib.icon} {lib.name}
                          </option>
                        ))}
                      </select>

                      <Button
                        size="small"
                        onClick={() => {
                          const libId = getSelectedLibrary(item.id, item.suggested_library)
                          if (!libId) {
                            alert('Select a library before approving')
                            return
                          }
                          handleApprove(item.id, libId, state)
                        }}
                        isLoading={approveItem.isPending}
                      >
                        <Check size={16} className="mr-1" />
                        Approve
                      </Button>

                      <Button
                        size="small"
                        variant="danger"
                        onClick={() => handleReject(item.id)}
                        isLoading={rejectItem.isPending}
                      >
                        <X size={16} />
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      ) : (
        <Card padding="large">
          <div className="text-center py-12">
            <AlertCircle size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              Inbox is empty
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              {showReviewed
                ? 'No items match your filters'
                : 'All items have been reviewed'}
            </p>
          </div>
        </Card>
      )}
    </div>
  )
}
