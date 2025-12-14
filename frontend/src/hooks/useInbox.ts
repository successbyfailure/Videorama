import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { inboxApi } from '@/services/api'
import type { InboxApprove } from '@/types'

interface InboxParams {
  inbox_type?: string
  reviewed?: boolean
  limit?: number
  offset?: number
}

export const useInboxItems = (params?: InboxParams) => {
  return useQuery({
    queryKey: ['inbox', params],
    queryFn: () => inboxApi.list(params),
    refetchInterval: 3000, // Refetch every 3 seconds
  })
}

export const useInboxItem = (id: string) => {
  return useQuery({
    queryKey: ['inbox-item', id],
    queryFn: () => inboxApi.get(id),
    enabled: !!id,
  })
}

export const useApproveInboxItem = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, approval }: { id: string; approval: InboxApprove }) =>
      inboxApi.approve(id, approval),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inbox'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })
}

export const useRejectInboxItem = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => inboxApi.reject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inbox'] })
    },
  })
}
