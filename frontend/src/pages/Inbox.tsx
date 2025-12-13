import { useState } from 'react'
import { Check, X, AlertCircle, Copy, Zap } from 'lucide-react'
import Card from '@/components/Card'
import Button from '@/components/Button'
import {
  useInboxItems,
  useApproveInboxItem,
  useRejectInboxItem,
} from '@/hooks/useInbox'
import { useLibraries } from '@/hooks/useLibraries'

export default function Inbox() {
  const [selectedType, setSelectedType] = useState<string | undefined>()
  const [showReviewed, setShowReviewed] = useState(false)

  const { data: inboxItems, isLoading } = useInboxItems({
    inbox_type: selectedType,
    reviewed: showReviewed || undefined,
    limit: 50,
  })
  const { data: libraries } = useLibraries(true)
  const approveItem = useApproveInboxItem()
  const rejectItem = useRejectInboxItem()

  const handleApprove = async (id: string, libraryId: string) => {
    await approveItem.mutateAsync({
      id,
      approval: { library_id: libraryId },
    })
  }

  const handleReject = async (id: string) => {
    if (confirm('Are you sure you want to reject this item?')) {
      await rejectItem.mutateAsync(id)
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
            const entryData = JSON.parse(item.entry_data || '{}')

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
                      {entryData.title || 'Untitled'}
                    </h3>

                    {entryData.original_url && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 mb-2 truncate">
                        {entryData.original_url}
                      </p>
                    )}

                    {item.error_message && (
                      <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-700 dark:text-red-300">
                        {item.error_message}
                      </div>
                    )}

                    {item.suggested_library && (
                      <div className="mt-2">
                        <span className="text-sm text-gray-600 dark:text-gray-400">
                          Suggested library:{' '}
                          <span className="font-medium">
                            {libraries?.find((l) => l.id === item.suggested_library)
                              ?.name || item.suggested_library}
                          </span>
                        </span>
                      </div>
                    )}
                  </div>

                  {!item.reviewed && (
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {item.suggested_library ? (
                        <Button
                          size="small"
                          onClick={() =>
                            handleApprove(item.id, item.suggested_library!)
                          }
                          isLoading={approveItem.isPending}
                        >
                          <Check size={16} className="mr-1" />
                          Approve
                        </Button>
                      ) : (
                        <select
                          className="input-field text-sm"
                          onChange={(e) => {
                            if (e.target.value) {
                              handleApprove(item.id, e.target.value)
                            }
                          }}
                          defaultValue=""
                        >
                          <option value="">Select library...</option>
                          {libraries?.map((lib) => (
                            <option key={lib.id} value={lib.id}>
                              {lib.icon} {lib.name}
                            </option>
                          ))}
                        </select>
                      )}

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
