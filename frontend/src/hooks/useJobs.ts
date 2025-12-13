import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { jobsApi } from '@/services/api'

interface JobsParams {
  job_type?: string
  status?: string
  limit?: number
}

export const useJobs = (params?: JobsParams) => {
  return useQuery({
    queryKey: ['jobs', params],
    queryFn: () => jobsApi.list(params),
    refetchInterval: 2000, // Refetch every 2 seconds for running jobs
  })
}

export const useJob = (id: string, enabled: boolean = true) => {
  return useQuery({
    queryKey: ['job', id],
    queryFn: () => jobsApi.get(id),
    enabled: enabled && !!id,
    refetchInterval: (data) => {
      // Only refetch if job is still running
      if (data?.status === 'running' || data?.status === 'pending') {
        return 1000 // 1 second
      }
      return false
    },
  })
}

export const useCleanupJobs = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (olderThan: number) => jobsApi.cleanup(olderThan),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
}
