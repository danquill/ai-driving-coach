import { useQuery } from '@tanstack/react-query'
import { getOverlay } from '../api/laps'
import { useStore } from '../store'
import type { OverlayResponse } from '../types/api'

// All channels fetched for every overlay request — chart visibility is controlled
// in the UI independently of what data is fetched.
const ALL_OVERLAY_CHANNELS = [
  'distance_m', 'lat', 'lon',
  'speed_kph', 'throttle_pct', 'brake_pct',
  'steering_deg', 'gear', 'rpm',
  'lat_g', 'lon_g',
]

export function useTelemetryOverlay(sessionId: string) {
  const selectedLapNumbers = useStore((s) => s.selectedLapNumbers)

  const { data, isLoading, error } = useQuery<OverlayResponse>({
    queryKey: ['overlay', sessionId, selectedLapNumbers],
    queryFn: () => getOverlay(sessionId, selectedLapNumbers, ALL_OVERLAY_CHANNELS),
    enabled: !!sessionId && selectedLapNumbers.length > 0,
    staleTime: 60_000,
  })

  return {
    data: data ?? null,
    isLoading: isLoading && selectedLapNumbers.length > 0,
    error,
  }
}
