import client from './client'
import type { Circuit, CircuitCorner, CircuitCornerKnowledge, CircuitSector } from '../types/api'

export async function listCircuits(): Promise<Circuit[]> {
  const response = await client.get<Circuit[]>('/circuits')
  return response.data
}

export async function getCircuit(id: string): Promise<Circuit> {
  const response = await client.get<Circuit>(`/circuits/${id}`)
  return response.data
}

export interface CornerPayload {
  corner_number: number
  name?: string
  distance_m: number
  lat: number
  lon: number
}

export async function createCorner(circuitId: string, data: CornerPayload): Promise<CircuitCorner> {
  const response = await client.post<CircuitCorner>(`/circuits/${circuitId}/corners`, data)
  return response.data
}

export async function updateCorner(
  circuitId: string,
  cornerId: string,
  data: Partial<CornerPayload>,
): Promise<CircuitCorner> {
  const response = await client.patch<CircuitCorner>(`/circuits/${circuitId}/corners/${cornerId}`, data)
  return response.data
}

export async function deleteCorner(circuitId: string, cornerId: string): Promise<void> {
  await client.delete(`/circuits/${circuitId}/corners/${cornerId}`)
}

export interface CircuitCreatePayload {
  name: string
  country?: string
  timezone?: string
  track_length_m?: number
}

export async function createCircuit(data: CircuitCreatePayload): Promise<Circuit> {
  const response = await client.post<Circuit>('/circuits/', data)
  return response.data
}

export async function deleteCircuit(id: string): Promise<void> {
  await client.delete(`/circuits/${id}`)
}

export interface CircuitSessionSummary {
  session_id: string
  session_name?: string
  session_date?: string
  lap_numbers: number[]
}

export async function listSessionsForCircuit(circuitId: string): Promise<CircuitSessionSummary[]> {
  const response = await client.get<CircuitSessionSummary[]>(`/circuits/${circuitId}/sessions`)
  return response.data
}

export interface SectorPayload {
  sector_number: number
  trigger_lat: number
  trigger_lon: number
  trigger_heading_deg?: number
}

export async function createSector(circuitId: string, data: SectorPayload): Promise<CircuitSector> {
  const response = await client.post<CircuitSector>(`/circuits/${circuitId}/sectors`, data)
  return response.data
}

export async function updateSector(
  circuitId: string,
  sectorId: string,
  data: Partial<SectorPayload>,
): Promise<CircuitSector> {
  const response = await client.patch<CircuitSector>(`/circuits/${circuitId}/sectors/${sectorId}`, data)
  return response.data
}

export async function deleteSector(circuitId: string, sectorId: string): Promise<void> {
  await client.delete(`/circuits/${circuitId}/sectors/${sectorId}`)
}

// ─── Corner Knowledge ─────────────────────────────────────────────────────────

export interface KnowledgePayload {
  corner_number?: number
  typical_phase_of_interest?: string
  known_handling_tendency?: string
  correct_technique?: string
  incorrect_recommendations?: string[]
  coaching_notes?: string
  source?: 'manual' | 'correction'
}

export async function listCornerKnowledge(circuitId: string): Promise<CircuitCornerKnowledge[]> {
  const response = await client.get<CircuitCornerKnowledge[]>(`/circuits/${circuitId}/corner-knowledge`)
  return response.data
}

export async function createCornerKnowledge(
  circuitId: string,
  data: KnowledgePayload,
): Promise<CircuitCornerKnowledge> {
  const response = await client.post<CircuitCornerKnowledge>(`/circuits/${circuitId}/corner-knowledge`, data)
  return response.data
}

export async function updateCornerKnowledge(
  circuitId: string,
  knowledgeId: string,
  data: Partial<KnowledgePayload>,
): Promise<CircuitCornerKnowledge> {
  const response = await client.patch<CircuitCornerKnowledge>(
    `/circuits/${circuitId}/corner-knowledge/${knowledgeId}`,
    data,
  )
  return response.data
}

export async function deleteCornerKnowledge(circuitId: string, knowledgeId: string): Promise<void> {
  await client.delete(`/circuits/${circuitId}/corner-knowledge/${knowledgeId}`)
}

export async function importGeometryFromLap(
  circuitId: string,
  sessionId: string,
  lapNumber: number,
): Promise<{ point_count: number; track_length_m: number }> {
  const response = await client.post(`/circuits/${circuitId}/geometry`, {
    session_id: sessionId,
    lap_number: lapNumber,
  })
  return response.data
}
