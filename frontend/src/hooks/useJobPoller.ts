import { useQuery } from '@tanstack/react-query'
import { listJobs } from '../api/analysis'
import type { AnalysisJob } from '../types/api'

export function useJobPoller(sessionId: string) {
  return useQuery<AnalysisJob[]>({
    queryKey: ['sessions', sessionId, 'jobs'],
    queryFn: () => listJobs(sessionId),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const jobs = query.state.data
      if (!jobs?.length) return 3000
      const allSettled = jobs.every(
        (j: AnalysisJob) => j.status === 'done' || j.status === 'failed'
      )
      return allSettled ? false : 3000
    },
  })
}
