export interface Tag {
  id: number
  name: string
  parent_id: number | null
  created_at: number
  usage_count: number
}

export interface TagCreate {
  name: string
  parent_id?: number | null
}

export interface TagUpdate {
  name?: string
  parent_id?: number | null
}

export interface TagMerge {
  source_tag_ids: number[]
  target_tag_id: number
}
