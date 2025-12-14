export interface InboxItem {
  id: string
  job_id: string | null
  type: 'duplicate' | 'low_confidence' | 'failed' | 'needs_review'
  entry_data: Record<string, any>
  suggested_library: string | null
  suggested_metadata: Record<string, any> | null
  confidence: number | null
  error_message: string | null
  reviewed: boolean
  created_at: number
  reviewed_at: number | null
}

export interface InboxApprove {
  library_id: string
  metadata_override?: Record<string, any>
}
