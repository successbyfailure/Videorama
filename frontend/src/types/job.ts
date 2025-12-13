export interface Job {
  id: string
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  current_step: string | null
  result: string | null
  error: string | null
  created_at: number
  started_at: number | null
  completed_at: number | null
}

export interface ImportURLRequest {
  url: string
  library_id?: string | null
  user_metadata?: Record<string, any>
  imported_by?: string | null
  auto_mode?: boolean
}

export interface ImportURLResponse {
  success: boolean
  entry_uuid?: string
  inbox_id?: string
  inbox_type?: string
  job_id: string
}
