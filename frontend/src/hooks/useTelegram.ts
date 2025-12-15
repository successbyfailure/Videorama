import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { telegramApi, TelegramContact, TelegramSettings } from '@/services/api'

export function useTelegramContacts(limit: number = 50) {
  return useQuery({
    queryKey: ['telegram-contacts', limit],
    queryFn: () => telegramApi.listContacts(limit),
  })
}

export function useAllowTelegramContact() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, allowed }: { userId: number; allowed: boolean }) =>
      telegramApi.allowContact(userId, allowed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['telegram-contacts'] })
    },
  })
}

export function useTelegramSettings() {
  return useQuery({
    queryKey: ['telegram-settings'],
    queryFn: telegramApi.getSettings,
  })
}

export function useUpdateTelegramSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: TelegramSettings) => telegramApi.updateSettings(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['telegram-settings'] })
    },
  })
}
