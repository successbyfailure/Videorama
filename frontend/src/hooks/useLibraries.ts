import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { librariesApi } from '@/services/api'
import type { LibraryCreate, LibraryUpdate } from '@/types'

export const useLibraries = (includePrivate: boolean = false) => {
  return useQuery({
    queryKey: ['libraries', includePrivate],
    queryFn: () => librariesApi.list(includePrivate),
  })
}

export const useLibrary = (id: string) => {
  return useQuery({
    queryKey: ['library', id],
    queryFn: () => librariesApi.get(id),
    enabled: !!id,
  })
}

export const useCreateLibrary = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (library: LibraryCreate) => librariesApi.create(library),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['libraries'] })
    },
  })
}

export const useUpdateLibrary = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: LibraryUpdate }) =>
      librariesApi.update(id, updates),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['libraries'] })
      queryClient.invalidateQueries({ queryKey: ['library', id] })
    },
  })
}

export const useDeleteLibrary = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => librariesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['libraries'] })
    },
  })
}
