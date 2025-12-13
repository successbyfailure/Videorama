export interface Entry {
  uuid: string
  library_id: string
  title: string
  subfolder: string | null
  original_url: string | null
  platform: string | null
  import_source: string | null
  imported_by: string | null
  view_count: number
  favorite: boolean
  rating: number | null
  added_at: number
  updated_at: number | null
  import_job_id: string | null
  files?: EntryFile[]
  properties?: Record<string, any>
  auto_tags?: EntryAutoTag[]
  user_tags?: EntryUserTag[]
}

export interface EntryFile {
  id: string
  entry_uuid: string
  file_path: string
  content_hash: string
  file_type: string
  format: string | null
  size: number
  duration: number | null
  width: number | null
  height: number | null
  is_available: boolean
  created_at: number
}

export interface EntryAutoTag {
  id: number
  entry_uuid: string
  tag_id: number
  source: string
  confidence: number | null
  added_at: number
  tag?: Tag
}

export interface EntryUserTag {
  id: number
  entry_uuid: string
  tag_id: number
  priority: number
  added_at: number
  tag?: Tag
}

export interface Tag {
  id: number
  name: string
  parent_id: number | null
}

export interface EntryCreate {
  library_id: string
  title: string
  subfolder?: string | null
  original_url?: string | null
  platform?: string | null
  import_source?: string | null
  imported_by?: string | null
}

export interface EntryUpdate {
  title?: string
  subfolder?: string | null
  favorite?: boolean
  rating?: number | null
}
