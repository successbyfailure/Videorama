import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tagsApi } from '@/services/api'
import type { TagCreate, TagUpdate, TagMerge } from '@/types'

interface TagsParams {
  search?: string
  parent_id?: number
  limit?: number
}

export const useTags = (params?: TagsParams) => {
  return useQuery({
    queryKey: ['tags', params],
    queryFn: () => tagsApi.list(params),
  })
}

export const useTag = (id: number) => {
  return useQuery({
    queryKey: ['tag', id],
    queryFn: () => tagsApi.get(id),
    enabled: !!id,
  })
}

export const useCreateTag = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (tag: TagCreate) => tagsApi.create(tag),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tags'] })
    },
  })
}

export const useUpdateTag = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, updates }: { id: number; updates: TagUpdate }) =>
      tagsApi.update(id, updates),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['tags'] })
      queryClient.invalidateQueries({ queryKey: ['tag', id] })
    },
  })
}

export const useDeleteTag = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => tagsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tags'] })
    },
  })
}

export const useMergeTags = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (mergeData: TagMerge) => tagsApi.merge(mergeData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tags'] })
    },
  })
}
