import { useMutation, useQueryClient } from '@tanstack/react-query'
import { importApi } from '@/services/api'
import type { ImportURLRequest } from '@/types'

export const useImportFromURL = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: ImportURLRequest) => importApi.fromURL(request),
    onSuccess: () => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['inbox'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })
}
