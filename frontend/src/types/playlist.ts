export interface Playlist {
  id: string
  library_id: string | null
  name: string
  description: string | null
  is_dynamic: boolean
  dynamic_query: string | null
  created_at: number
  updated_at: number | null
  entry_count?: number
}

export interface PlaylistCreate {
  library_id?: string | null
  name: string
  description?: string | null
  is_dynamic?: boolean
  dynamic_query?: string | null
}

export interface PlaylistUpdate {
  name?: string
  description?: string | null
  dynamic_query?: string | null
}
