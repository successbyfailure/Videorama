export interface Library {
  id: string
  name: string
  icon: string
  default_path: string
  additional_paths: string[]
  auto_organize: boolean
  path_template: string | null
  auto_tag_from_path: boolean
  is_private: boolean
  llm_confidence_threshold: number
  watch_folders: string[]
  scan_interval: number
  entry_count?: number
}

export interface LibraryCreate {
  id: string
  name: string
  icon?: string
  default_path: string
  additional_paths?: string[]
  auto_organize?: boolean
  path_template?: string | null
  auto_tag_from_path?: boolean
  is_private?: boolean
  llm_confidence_threshold?: number
  watch_folders?: string[]
  scan_interval?: number
}

export interface LibraryUpdate {
  name?: string
  icon?: string
  default_path?: string
  additional_paths?: string[]
  auto_organize?: boolean
  path_template?: string | null
  auto_tag_from_path?: boolean
  is_private?: boolean
  llm_confidence_threshold?: number
  watch_folders?: string[]
  scan_interval?: number
}
