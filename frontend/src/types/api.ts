// ─── Auth ────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserResponse {
  id: string
  email: string
  display_name: string
  role: string
  is_active: boolean
  created_at: string
}

// ─── Sessions ────────────────────────────────────────────────────────────────

export type SessionStatus =
  | 'pending'
  | 'processing'
  | 'ready'
  | 'failed'
  | 'ready_no_laps'
  | 'deleted'

export type SessionType = 'hpde' | 'practice' | 'qualifying' | 'race' | 'test'

export const SESSION_TYPE_LABELS: Record<SessionType, string> = {
  hpde: 'HPDE',
  practice: 'Practice',
  qualifying: 'Qualifying',
  race: 'Race',
  test: 'Test Day',
}

export interface Session {
  id: string
  owner_id: string
  name?: string
  circuit_id?: string
  vehicle_id?: string
  event_id?: string
  session_date?: string
  ambient_temp_c?: number
  notes?: string
  session_type?: SessionType
  status: SessionStatus
  created_at: string
  best_lap_time_ms?: number
  circuit_name?: string
}

// ─── Events ──────────────────────────────────────────────────────────────────

export interface Event {
  id: string
  owner_id: string
  name: string
  event_date?: string
  circuit_id?: string
  circuit_name?: string
  notes?: string
  created_at: string
}

// ─── Files ───────────────────────────────────────────────────────────────────

export interface SessionFile {
  id: string
  session_id: string
  filename: string
  file_type: string
  size_bytes: number
  uploaded_at: string
}

// ─── Laps ────────────────────────────────────────────────────────────────────

export interface LapSector {
  lap_id: string
  sector_number: number
  sector_time_ms: number
  entry_speed_kph?: number
  exit_speed_kph?: number
}

export interface LapDetail {
  id: string
  session_id: string
  lap_number: number
  lap_time_ms?: number
  is_outlap: boolean
  is_inlap: boolean
  is_valid: boolean
  start_ts?: string
  end_ts?: string
  max_speed_kph?: number
  min_speed_kph?: number
  sectors: LapSector[]
}

export interface IdealLap {
  id: string
  session_id: string
  theoretical_time_ms: number
  sector_sources: Record<string, number>  // sector_number -> lap_number
  constructed_at: string
}

// ─── Telemetry ───────────────────────────────────────────────────────────────

export interface TelemetryResponse {
  lap_number: number
  channels: string[]
  data: number[][]  // each inner array = one row, parallel to channels
}

export interface OverlayResponse {
  channels: string[]
  laps: Record<string, number[][]>  // lap_number (string) -> rows
}

// ─── Analysis ────────────────────────────────────────────────────────────────

export type JobStatus = 'pending' | 'running' | 'done' | 'failed'

export interface AnalysisJob {
  id: string
  session_id: string
  job_type: string
  status: JobStatus
  queued_at?: string
  started_at?: string
  completed_at?: string
  result_summary?: string
  error_message?: string
}

export interface CoachingInsight {
  id: string
  session_id: string
  lap_id?: string
  lap_number?: number
  analysis_job_id: string
  category: string
  insight_text: string
  confidence?: number  // 0.0–1.0
  distance_m_start?: number
  distance_m_end?: number
  created_at: string
  feedback?: 'good' | 'bad'
  feedback_note?: string
}

export interface CircuitCornerKnowledge {
  id: string
  circuit_id: string
  corner_number?: number
  typical_phase_of_interest?: string
  known_handling_tendency?: string
  correct_technique?: string
  incorrect_recommendations?: string[]
  coaching_notes?: string
  source: 'manual' | 'correction'
  created_at: string
  updated_at: string
}

// ─── Circuits ────────────────────────────────────────────────────────────────

export interface CircuitSector {
  id: string
  sector_number: number
  trigger_lat: number
  trigger_lon: number
  trigger_heading_deg?: number
}

export interface CircuitCorner {
  id: string
  corner_number: number
  name?: string
  distance_m: number
  lat: number
  lon: number
}

export interface Circuit {
  id: string
  name: string
  country: string
  track_length_m?: number
  sectors: CircuitSector[]
  corners: CircuitCorner[]
  geometry?: GeoJSON.LineString
}
