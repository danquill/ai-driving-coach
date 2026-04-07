import { useQuery } from '@tanstack/react-query'
import { getOverlay } from '../api/laps'
import { useStore } from '../store'
import type { OverlayResponse } from '../types/api'

export function useTelemetryOverlay(sessionId: string) {
  const selectedLapNumbers = useStore((s) => s.selectedLapNumbers)
  const selectedChannels = useStore((s) => s.selectedChannels)

  // Always include distance_m, lat/lon for map, and lat_g/lon_g for traction circle
  const channels = Array.from(
    new Set(['distance_m', 'lat', 'lon', 'lat_g', 'lon_g', ...selectedChannels])
  )

  const { data, isLoading, error } = useQuery<OverlayResponse>({
    queryKey: ['overlay', sessionId, selectedLapNumbers, channels],
    queryFn: () => getOverlay(sessionId, selectedLapNumbers, channels),
    enabled: !!sessionId && selectedLapNumbers.length > 0,
    staleTime: 60_000,
  })

  return {
    data: data ?? null,
    isLoading: isLoading && selectedLapNumbers.length > 0,
    error,
  }
}
