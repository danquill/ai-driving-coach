import client from './client'
import type { Session, SessionFile } from '../types/api'

export interface CreateSessionData {
  name?: string
  circuit_id?: string
  session_date?: string
  notes?: string
  session_type?: string
}

export async function listSessions(): Promise<Session[]> {
  const response = await client.get<Session[]>('/sessions')
  return response.data
}

export async function getSession(id: string): Promise<Session> {
  const response = await client.get<Session>(`/sessions/${id}`)
  return response.data
}

export async function getDemoSession(): Promise<Session> {
  const response = await client.get<Session>('/sessions/demo')
  return response.data
}

export async function createSession(data: CreateSessionData): Promise<Session> {
  const response = await client.post<Session>('/sessions', data)
  return response.data
}

export async function updateSession(
  id: string,
  data: Partial<CreateSessionData>
): Promise<Session> {
  const response = await client.patch<Session>(`/sessions/${id}`, data)
  return response.data
}

export function uploadFile(
  sessionId: string,
  file: File,
  onProgress?: (pct: number) => void
): Promise<SessionFile> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const formData = new FormData()
    formData.append('file', file)

    const token = localStorage.getItem('access_token')

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText))
        } catch {
          reject(new Error('Invalid response'))
        }
      } else {
        reject(new Error(`Upload failed: ${xhr.status}`))
      }
    })

    xhr.addEventListener('error', () => reject(new Error('Network error')))
    xhr.addEventListener('abort', () => reject(new Error('Upload aborted')))

    xhr.open('POST', `/api/v1/sessions/${sessionId}/upload`)
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    }
    xhr.send(formData)
  })
}

export async function deleteSession(id: string): Promise<void> {
  await client.delete(`/sessions/${id}`)
}

export async function listFiles(sessionId: string): Promise<SessionFile[]> {
  const response = await client.get<SessionFile[]>(`/sessions/${sessionId}/files`)
  return response.data
}
