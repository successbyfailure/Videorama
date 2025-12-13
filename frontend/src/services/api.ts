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

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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

  delete: async (uuid: string) => {
    await api.delete(`/entries/${uuid}`)
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
}

export default api
