import client from './client'
import type { LapDetail, IdealLap, TelemetryResponse, OverlayResponse } from '../types/api'

export async function listLaps(sessionId: string): Promise<LapDetail[]> {
  const response = await client.get<LapDetail[]>(`/sessions/${sessionId}/laps/`)
  return response.data
}

export async function getLap(sessionId: string, lapNumber: number): Promise<LapDetail> {
  const response = await client.get<LapDetail>(`/sessions/${sessionId}/laps/${lapNumber}`)
  return response.data
}

export async function getIdealLap(sessionId: string): Promise<IdealLap> {
  const response = await client.get<IdealLap>(`/sessions/${sessionId}/laps/ideal`)
  return response.data
}

export async function getTelemetry(
  sessionId: string,
  lapNumber: number,
  channels: string[],
  resolution?: number
): Promise<TelemetryResponse> {
  const params = new URLSearchParams()
  channels.forEach((c) => params.append('channels', c))
  if (resolution !== undefined) params.set('resolution', String(resolution))
  const response = await client.get<TelemetryResponse>(
    `/sessions/${sessionId}/laps/${lapNumber}/telemetry?${params}`
  )
  return response.data
}

export async function getOverlay(
  sessionId: string,
  lapNumbers: number[],
  channels: string[],
  resolution?: number
): Promise<OverlayResponse> {
  const params = new URLSearchParams()
  lapNumbers.forEach((n) => params.append('laps', String(n)))
  channels.forEach((c) => params.append('channels', c))
  if (resolution !== undefined) params.set('resolution', String(resolution))
  const response = await client.get<OverlayResponse>(
    `/sessions/${sessionId}/telemetry/overlay?${params}`
  )
  return response.data
}

export type { LapDetail, IdealLap, TelemetryResponse, OverlayResponse }
