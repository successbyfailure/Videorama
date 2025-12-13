import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi, Settings, SettingsUpdate } from '@/services/api'

export function useSettings() {
  return useQuery<Settings>({
    queryKey: ['settings'],
    queryFn: settingsApi.get,
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (updates: SettingsUpdate) => settingsApi.update(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}
