import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { playlistsApi } from '@/services/api'
import type { PlaylistCreate, PlaylistUpdate } from '@/types'

interface PlaylistsParams {
  library_id?: string
  is_dynamic?: boolean
  limit?: number
}

export const usePlaylists = (params?: PlaylistsParams) => {
  return useQuery({
    queryKey: ['playlists', params],
    queryFn: () => playlistsApi.list(params),
  })
}

export const usePlaylist = (id: string) => {
  return useQuery({
    queryKey: ['playlist', id],
    queryFn: () => playlistsApi.get(id),
    enabled: !!id,
  })
}

export const useCreatePlaylist = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (playlist: PlaylistCreate) => playlistsApi.create(playlist),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
    },
  })
}

export const useUpdatePlaylist = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: PlaylistUpdate }) =>
      playlistsApi.update(id, updates),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
      queryClient.invalidateQueries({ queryKey: ['playlist', id] })
    },
  })
}

export const useDeletePlaylist = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => playlistsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] })
    },
  })
}

export const useAddEntryToPlaylist = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      playlistId,
      entryUuid,
    }: {
      playlistId: string
      entryUuid: string
    }) => playlistsApi.addEntry(playlistId, entryUuid),
    onSuccess: (_, { playlistId }) => {
      queryClient.invalidateQueries({ queryKey: ['playlist', playlistId] })
    },
  })
}

export const useRemoveEntryFromPlaylist = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      playlistId,
      entryUuid,
    }: {
      playlistId: string
      entryUuid: string
    }) => playlistsApi.removeEntry(playlistId, entryUuid),
    onSuccess: (_, { playlistId }) => {
      queryClient.invalidateQueries({ queryKey: ['playlist', playlistId] })
    },
  })
}
