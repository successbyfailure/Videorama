import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { promptsApi, PromptSetting, PromptSettingUpdate } from '@/services/api'

export function usePromptSettings(category?: string) {
  return useQuery<PromptSetting[]>({
    queryKey: ['promptSettings', category],
    queryFn: () => promptsApi.list(category),
  })
}

export function usePromptSetting(key: string) {
  return useQuery<PromptSetting>({
    queryKey: ['promptSettings', key],
    queryFn: () => promptsApi.get(key),
  })
}

export function useUpdatePromptSetting() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ key, updates }: { key: string; updates: PromptSettingUpdate }) =>
      promptsApi.update(key, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promptSettings'] })
    },
  })
}

export function useResetPromptSetting() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (key: string) => promptsApi.reset(key),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promptSettings'] })
    },
  })
}
