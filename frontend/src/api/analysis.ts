import client from './client'
import type { AnalysisJob, CoachingInsight } from '../types/api'

export async function triggerAnalysis(sessionId: string, jobType: string): Promise<AnalysisJob> {
  const response = await client.post<AnalysisJob>(`/sessions/${sessionId}/analyze`, {
    job_type: jobType,
  })
  return response.data
}

export async function listJobs(sessionId: string): Promise<AnalysisJob[]> {
  const response = await client.get<AnalysisJob[]>(`/sessions/${sessionId}/jobs`)
  return response.data
}

export async function getInsights(sessionId: string): Promise<CoachingInsight[]> {
  const response = await client.get<CoachingInsight[]>(`/sessions/${sessionId}/insights`)
  return response.data
}

export async function deleteInsight(sessionId: string, insightId: string): Promise<void> {
  await client.delete(`/sessions/${sessionId}/insights/${insightId}`)
}

export async function deleteAllInsights(sessionId: string): Promise<void> {
  await client.delete(`/sessions/${sessionId}/insights`)
}
