import axios from 'axios'
import type {
  Library,
  LibraryCreate,
  LibraryUpdate,
  Entry,
  EntryCreate,
  EntryUpdate,
  InboxItem,
  InboxApprove,
  Playlist,
  PlaylistCreate,
  PlaylistUpdate,
  Job,
  ImportURLRequest,
  ImportURLResponse,
} from '@/types'

// Simple API configuration:
// - Development: VITE_API_URL environment variable (docker-compose sets it)
// - Production: Empty string = relative URLs (works with any reverse proxy)
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ========== Libraries ==========

export const librariesApi = {
  list: async (includePrivate: boolean = false) => {
    const { data } = await api.get<Library[]>('/libraries', {
      params: { include_private: includePrivate },
    })
    return data
  },

  get: async (id: string) => {
    const { data } = await api.get<Library>(`/libraries/${id}`)
    return data
  },

  create: async (library: LibraryCreate) => {
    const { data } = await api.post<Library>('/libraries', library)
    return data
  },

  update: async (id: string, updates: LibraryUpdate) => {
    const { data } = await api.patch<Library>(`/libraries/${id}`, updates)
    return data
  },

  delete: async (id: string) => {
    await api.delete(`/libraries/${id}`)
  },

  browse: async (path?: string) => {
    const { data } = await api.get<{
      base_path: string
      current_path: string
      parent_path: string
      directories: { name: string; relative_path: string; absolute_path: string; child_count?: number }[]
    }>('/libraries/browse', { params: { path } })
    return data
  },
  reindex: async (id: string) => {
    const { data } = await api.post<{ job_id: string }>(`/libraries/${id}/reindex`)
    return data
  },
}

// ========== Entries ==========

export const entriesApi = {
  list: async (params?: {
    library_id?: string
    search?: string
    platform?: string
    favorite?: boolean
    limit?: number
    offset?: number
  }) => {
    const { data } = await api.get<Entry[]>('/entries', { params })
    return data
  },

  get: async (uuid: string) => {
    const { data } = await api.get<Entry>(`/entries/${uuid}`)
    return data
  },

  create: async (entry: EntryCreate) => {
    const { data } = await api.post<Entry>('/entries', entry)
    return data
  },

  update: async (uuid: string, updates: EntryUpdate) => {
    const { data } = await api.patch<Entry>(`/entries/${uuid}`, updates)
    return data
  },

  delete: async (uuid: string, removeFiles: boolean) => {
    await api.delete(`/entries/${uuid}`, { params: { remove_files: removeFiles } })
  },

  incrementViewCount: async (uuid: string) => {
    const { data } = await api.post<Entry>(`/entries/${uuid}/view`)
    return data
  },
}

// ========== Import ==========

export const importApi = {
  fromURL: async (request: ImportURLRequest) => {
    const { data } = await api.post<ImportURLResponse>('/import/url', request)
    return data
  },
}

// ========== Inbox ==========

export const inboxApi = {
  list: async (params?: {
    inbox_type?: string
    reviewed?: boolean
    limit?: number
    offset?: number
  }) => {
    const { data } = await api.get<InboxItem[]>('/inbox', { params })
    return data
  },

  get: async (id: string) => {
    const { data } = await api.get<InboxItem>(`/inbox/${id}`)
    return data
  },

  approve: async (id: string, approval: InboxApprove) => {
    const { data } = await api.post(`/inbox/${id}/approve`, approval)
    return data
  },

  reprobe: async (id: string) => {
    const { data } = await api.post(`/inbox/${id}/probe`)
    return data
  },

  reclassify: async (id: string) => {
    const { data } = await api.post(`/inbox/${id}/reclassify`)
    return data
  },

  redownload: async (id: string) => {
    const { data } = await api.post(`/inbox/${id}/redownload`)
    return data
  },

  reject: async (id: string) => {
    await api.delete(`/inbox/${id}`)
  },
}

// ========== Jobs ==========

export const jobsApi = {
  list: async (params?: {
    job_type?: string
    status?: string
    limit?: number
  }) => {
    const { data } = await api.get<Job[]>('/jobs', { params })
    return data
  },

  get: async (id: string) => {
    const { data } = await api.get<Job>(`/jobs/${id}`)
    return data
  },

  cancel: async (id: string) => {
    const { data } = await api.post<Job>(`/jobs/${id}/cancel`)
    return data
  },

  delete: async (id: string) => {
    await api.delete(`/jobs/${id}`)
  },

  cleanup: async (olderThan: number) => {
    const { data } = await api.delete('/jobs/cleanup', {
      params: { older_than: olderThan },
    })
    return data
  },
}

// ========== Playlists ==========

export const playlistsApi = {
  list: async (params?: {
    library_id?: string
    is_dynamic?: boolean
    limit?: number
  }) => {
    const { data } = await api.get<Playlist[]>('/playlists', { params })
    return data
  },

  get: async (id: string) => {
    const { data } = await api.get<Playlist>(`/playlists/${id}`)
    return data
  },

  create: async (playlist: PlaylistCreate) => {
    const { data } = await api.post<Playlist>('/playlists', playlist)
    return data
  },

  update: async (id: string, updates: PlaylistUpdate) => {
    const { data } = await api.patch<Playlist>(`/playlists/${id}`, updates)
    return data
  },

  delete: async (id: string) => {
    await api.delete(`/playlists/${id}`)
  },

  addEntry: async (playlistId: string, entryUuid: string) => {
    const { data } = await api.post(
      `/playlists/${playlistId}/entries/${entryUuid}`
    )
    return data
  },

  removeEntry: async (playlistId: string, entryUuid: string) => {
    await api.delete(`/playlists/${playlistId}/entries/${entryUuid}`)
  },

  getEntries: async (playlistId: string) => {
    const { data } = await api.get<Entry[]>(`/playlists/${playlistId}/entries`)
    return data
  },
}

// ========== Settings ==========

export interface Settings {
  app_name: string
  version: string
  debug: boolean
  storage_base_path: string
  vhs_base_url: string
  vhs_timeout: number
  vhs_verify_ssl: boolean
  openai_api_key: string | null
  openai_base_url: string
  openai_model: string
  tmdb_api_key: string | null
  spotify_client_id: string | null
  spotify_client_secret: string | null
  telegram_bot_token: string | null
  telegram_admin_ids?: string | null
}

export interface SettingsUpdate {
  app_name?: string
  debug?: boolean
  storage_base_path?: string
  vhs_base_url?: string
  vhs_timeout?: number
  vhs_verify_ssl?: boolean
  openai_api_key?: string
  openai_base_url?: string
  openai_model?: string
  tmdb_api_key?: string
  spotify_client_id?: string
  spotify_client_secret?: string
  telegram_bot_token?: string
  telegram_admin_ids?: string
}

export const settingsApi = {
  get: async () => {
    const { data } = await api.get<Settings>('/app-settings')
    return data
  },

  update: async (updates: SettingsUpdate) => {
    const { data } = await api.put<Settings>('/app-settings', updates)
    return data
  },
}

// ========== Telegram Admin ==========

export interface TelegramContact {
  user_id: number
  username?: string
  first_name?: string
  last_name?: string
  role: string
  allowed: boolean
  last_interaction_at?: number
}

export interface TelegramSettings {
  [key: string]: string | null
}

export const telegramApi = {
  listContacts: async (limit: number = 50) => {
    const { data } = await api.get<TelegramContact[]>('/telegram/contacts', {
      params: { limit },
    })
    return data
  },
  allowContact: async (userId: number, allowed: boolean) => {
    const { data } = await api.post<{ user_id: number; allowed: boolean }>(
      `/telegram/contacts/${userId}/allow`,
      null,
      { params: { allowed } }
    )
    return data
  },
  getSettings: async () => {
    const { data } = await api.get<TelegramSettings>('/telegram/settings')
    return data
  },
  updateSettings: async (payload: TelegramSettings) => {
    const { data } = await api.put<TelegramSettings>('/telegram/settings', payload)
    return data
  },
}

// ========== Prompts (LLM Settings) ==========

export interface PromptSetting {
  key: string
  value: string
  category: string | null
  description: string | null
  is_secret: boolean
}

export interface PromptSettingUpdate {
  value: string
}

export const promptsApi = {
  list: async (category?: string) => {
    const { data } = await api.get<PromptSetting[]>('/settings', {
      params: category ? { category } : undefined,
    })
    return data
  },

  get: async (key: string) => {
    const { data } = await api.get<PromptSetting>(`/settings/${key}`)
    return data
  },

  update: async (key: string, updates: PromptSettingUpdate) => {
    const { data } = await api.patch<PromptSetting>(`/settings/${key}`, updates)
    return data
  },

  reset: async (key: string) => {
    const { data } = await api.post<PromptSetting>(`/settings/${key}/reset`)
    return data
  },
}

// ========== Tags ==========

export const tagsApi = {
  list: async (params?: {
    search?: string
    parent_id?: number
    limit?: number
  }) => {
    const { data } = await api.get<import('@/types').Tag[]>('/tags', { params })
    return data
  },

  get: async (id: number) => {
    const { data } = await api.get<import('@/types').Tag>(`/tags/${id}`)
    return data
  },

  create: async (tag: import('@/types').TagCreate) => {
    const { data } = await api.post<import('@/types').Tag>('/tags', tag)
    return data
  },

  update: async (id: number, updates: import('@/types').TagUpdate) => {
    const { data } = await api.patch<import('@/types').Tag>(`/tags/${id}`, updates)
    return data
  },

  delete: async (id: number) => {
    await api.delete(`/tags/${id}`)
  },

  merge: async (mergeData: import('@/types').TagMerge) => {
    const { data } = await api.post<import('@/types').Tag>('/tags/merge', mergeData)
    return data
  },
}

export default api
