import { X, CheckCircle, XCircle, Loader2, Clock, Trash2, XOctagon } from 'lucide-react'
import { useJobs } from '@/hooks/useJobs'
import { jobsApi } from '@/services/api'
import { useMutation, useQueryClient } from '@tanstack/react-query'

interface JobsPanelProps {
  isOpen: boolean
  onClose: () => void
}

export default function JobsPanel({ isOpen, onClose }: JobsPanelProps) {
  const { data: jobs = [] } = useJobs()
  const queryClient = useQueryClient()

  // Cancel job mutation
  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => jobsApi.cancel(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (error: any) => {
      const message =
        error?.response?.data?.detail || error?.message || 'Failed to cancel job'
      alert(message)
    },
  })

  // Delete job mutation
  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => jobsApi.delete(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (error: any) => {
      const message =
        error?.response?.data?.detail || error?.message || 'Failed to delete job'
      alert(message)
    },
  })

  if (!isOpen) return null

  const runningJobs = jobs.filter((j) => j.status === 'running')
  const completedJobs = jobs.filter((j) => j.status === 'completed')
  const failedJobs = jobs.filter((j) => j.status === 'failed')
  const cancelledJobs = jobs.filter((j) => j.status === 'cancelled')

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp * 1000)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const seconds = Math.floor(diff / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)

    if (seconds < 60) return `${seconds}s ago`
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    return date.toLocaleDateString()
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-25 z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed top-0 right-0 h-full w-96 bg-white dark:bg-gray-800 shadow-xl z-50 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Jobs Queue
          </h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
          >
            <X size={20} className="text-gray-500 dark:text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {jobs.length === 0 && (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              No jobs in queue
            </div>
          )}

          {/* Running Jobs */}
          {runningJobs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Running ({runningJobs.length})
              </h3>
              <div className="space-y-2">
                {runningJobs.map((job) => (
                  <div
                    key={job.id}
                    className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3"
                  >
                    <div className="flex items-start gap-2">
                      <Loader2 className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin flex-shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                          {job.type}
                        </div>
                        {job.current_step && (
                          <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
                            {job.current_step}
                          </div>
                        )}
                        <div className="mt-2">
                          <div className="flex items-center justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
                            <span>{Math.round(job.progress * 100)}%</span>
                            <span>{formatDate(job.created_at)}</span>
                          </div>
                          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                            <div
                              className="bg-blue-600 h-1.5 rounded-full transition-all"
                              style={{ width: `${job.progress * 100}%` }}
                            />
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => cancelMutation.mutate(job.id)}
                        disabled={cancelMutation.isPending}
                        className="p-1 hover:bg-red-100 dark:hover:bg-red-900/20 rounded text-red-600 dark:text-red-400 disabled:opacity-50"
                        title="Cancel job"
                      >
                        <XOctagon size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Failed Jobs */}
          {failedJobs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Failed ({failedJobs.length})
              </h3>
              <div className="space-y-2">
                {failedJobs.slice(0, 5).map((job) => (
                  <div
                    key={job.id}
                    className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3"
                  >
                    <div className="flex items-start gap-2">
                      <XCircle className="w-4 h-4 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                          {job.type}
                        </div>
                        {job.error && (
                          <div className="text-xs text-red-600 dark:text-red-400 mt-0.5 truncate">
                            {job.error}
                          </div>
                        )}
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {formatDate(job.created_at)}
                        </div>
                      </div>
                      <button
                        onClick={() => deleteMutation.mutate(job.id)}
                        disabled={deleteMutation.isPending}
                        className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded text-gray-600 dark:text-gray-400 disabled:opacity-50"
                        title="Delete job"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Cancelled Jobs */}
          {cancelledJobs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Cancelled ({cancelledJobs.length})
              </h3>
              <div className="space-y-2">
                {cancelledJobs.slice(0, 5).map((job) => (
                  <div
                    key={job.id}
                    className="bg-gray-50 dark:bg-gray-900/20 border border-gray-200 dark:border-gray-700 rounded-lg p-3"
                  >
                    <div className="flex items-start gap-2">
                      <XOctagon className="w-4 h-4 text-gray-600 dark:text-gray-400 flex-shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                          {job.type}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {formatDate(job.completed_at || job.created_at)}
                        </div>
                      </div>
                      <button
                        onClick={() => deleteMutation.mutate(job.id)}
                        disabled={deleteMutation.isPending}
                        className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded text-gray-600 dark:text-gray-400 disabled:opacity-50"
                        title="Delete job"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Completed Jobs */}
          {completedJobs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Completed ({completedJobs.length})
              </h3>
              <div className="space-y-2">
                {completedJobs.slice(0, 5).map((job) => (
                  <div
                    key={job.id}
                    className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3"
                  >
                    <div className="flex items-start gap-2">
                      <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                          {job.type}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {formatDate(job.completed_at || job.created_at)}
                        </div>
                      </div>
                      <button
                        onClick={() => deleteMutation.mutate(job.id)}
                        disabled={deleteMutation.isPending}
                        className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded text-gray-600 dark:text-gray-400 disabled:opacity-50"
                        title="Delete job"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
