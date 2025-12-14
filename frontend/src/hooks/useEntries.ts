import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { entriesApi } from '@/services/api'
import type { EntryCreate, EntryUpdate } from '@/types'

interface EntriesParams {
  library_id?: string
  search?: string
  platform?: string
  favorite?: boolean
  limit?: number
  offset?: number
}

export const useEntries = (params?: EntriesParams) => {
  return useQuery({
    queryKey: ['entries', params],
    queryFn: () => entriesApi.list(params),
  })
}

export const useEntry = (uuid: string) => {
  return useQuery({
    queryKey: ['entry', uuid],
    queryFn: () => entriesApi.get(uuid),
    enabled: !!uuid,
  })
}

export const useCreateEntry = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (entry: EntryCreate) => entriesApi.create(entry),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })
}

export const useUpdateEntry = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ uuid, updates }: { uuid: string; updates: EntryUpdate }) =>
      entriesApi.update(uuid, updates),
    onSuccess: (_, { uuid }) => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['entry', uuid] })
    },
  })
}

export const useDeleteEntry = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ uuid, removeFiles }: { uuid: string; removeFiles: boolean }) =>
      entriesApi.delete(uuid, removeFiles),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })
}

export const useIncrementViewCount = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (uuid: string) => entriesApi.incrementViewCount(uuid),
    onSuccess: (_, uuid) => {
      queryClient.invalidateQueries({ queryKey: ['entry', uuid] })
    },
  })
}
