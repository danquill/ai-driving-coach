import client from './client'
import type { Event } from '../types/api'

export interface CreateEventData {
  name: string
  event_date?: string
  circuit_id?: string
  notes?: string
}

export interface UpdateEventData {
  name?: string
  event_date?: string
  circuit_id?: string
  notes?: string
}

export async function listEvents(): Promise<Event[]> {
  const response = await client.get<Event[]>('/events')
  return response.data
}

export async function createEvent(data: CreateEventData): Promise<Event> {
  const response = await client.post<Event>('/events', data)
  return response.data
}

export async function updateEvent(id: string, data: UpdateEventData): Promise<Event> {
  const response = await client.patch<Event>(`/events/${id}`, data)
  return response.data
}

export async function deleteEvent(id: string): Promise<void> {
  await client.delete(`/events/${id}`)
}

export async function assignSessions(eventId: string, sessionIds: string[]): Promise<void> {
  await client.patch(`/events/${eventId}/sessions`, { session_ids: sessionIds })
}
