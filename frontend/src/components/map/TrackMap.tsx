import { useEffect, useMemo, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import type { Circuit } from '../../types/api'
import { useStore } from '../../store'
import { speedToColor } from '../../utils/telemetry'

interface TrackMapProps {
  circuit: Circuit | null
  lapRows: Record<number, number[][]>
  selectedLaps: number[]
  channels: string[]
  lapColorMap: Record<number, string>
  colorMode?: 'lap' | 'speed'
}

function buildLineGeoJSON(rows: number[][], latIdx: number, lonIdx: number): GeoJSON.Feature {
  return {
    type: 'Feature',
    properties: {},
    geometry: {
      type: 'LineString',
      coordinates: rows.map((row) => [row[lonIdx], row[latIdx]]),
    },
  }
}

export function TrackMap({ circuit, lapRows, selectedLaps, channels, lapColorMap, colorMode = 'lap' }: TrackMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<Map<number, maplibregl.Marker>>(new Map())
  const prevLayerIdsRef = useRef<string[]>([])

  // Keep latest props in refs for the cursor effect (which must NOT re-trigger the draw effect)
  const selectedLapsRef = useRef(selectedLaps)
  const lapRowsRef = useRef(lapRows)
  const channelsRef = useRef(channels)
  const colorModeRef = useRef(colorMode)
  selectedLapsRef.current = selectedLaps
  lapRowsRef.current = lapRows
  channelsRef.current = channels
  colorModeRef.current = colorMode

  const cursorDistanceM = useStore((s) => s.cursorDistanceM)
  const cursorDistanceMRef = useRef(cursorDistanceM)
  cursorDistanceMRef.current = cursorDistanceM
  const hasTelemetry = selectedLaps.length > 0

  // A stable key that only changes when the actual data that affects drawing changes.
  // This prevents the draw effect from re-firing on every render.
  const drawKey = useMemo(() => {
    const lapKeys = selectedLaps.map((n) => {
      const rows = lapRows[n]
      return `${n}:${rows?.length ?? 0}`
    }).join(',')
    const colorKey = selectedLaps.map((n) => lapColorMap[n] ?? '').join(',')
    return `${lapKeys}|${colorKey}|${channels.join(',')}|${circuit?.id ?? ''}|${colorMode}`
  }, [selectedLaps, lapRows, lapColorMap, channels, circuit?.id, colorMode])

  // ── Init map ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [0, 51.5],
      zoom: 14,
      attributionControl: false,
    })
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    mapRef.current = map
    return () => {
      markersRef.current.forEach((m) => m.remove())
      markersRef.current.clear()
      map.remove()
      mapRef.current = null
    }
  }, [])

  // ── Draw traces + create markers (only when drawKey changes) ─────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const doWork = () => {
      const laps = selectedLapsRef.current
      const rows = lapRowsRef.current
      const chs = channelsRef.current
      const latIdx = chs.indexOf('lat')
      const lonIdx = chs.indexOf('lon')

      // Remove previous layers/sources
      for (const id of prevLayerIdsRef.current) {
        try { if (map.getLayer(id)) map.removeLayer(id) } catch {}
      }
      for (const id of prevLayerIdsRef.current) {
        try { if (map.getSource(id)) map.removeSource(id) } catch {}
      }
      try { if (map.getLayer('sector-labels')) map.removeLayer('sector-labels') } catch {}
      try { if (map.getSource('sector-source')) map.removeSource('sector-source') } catch {}
      prevLayerIdsRef.current = []

      // Remove old markers
      markersRef.current.forEach((m) => m.remove())
      markersRef.current.clear()

      if (laps.length === 0 || latIdx === -1 || lonIdx === -1) {
        if (circuit?.geometry) {
          const sid = 'circuit-src'
          const lid = 'circuit-line'
          map.addSource(sid, { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: circuit.geometry } })
          map.addLayer({ id: lid, type: 'line', source: sid, paint: { 'line-width': 2, 'line-color': '#457b9d' } })
          prevLayerIdsRef.current.push(lid, sid)
        }
        return
      }

      const allCoords: [number, number][] = []

      // Pre-compute global speed range for speed-color mode
      const speedIdx = chs.indexOf('speed_kph')
      const useSpeedColor = colorModeRef.current === 'speed' && speedIdx !== -1
      let globalMinSpeed = 0
      let globalMaxSpeed = 200
      if (useSpeedColor) {
        let lo = Infinity, hi = -Infinity
        for (const lapNum of laps) {
          for (const row of rows[lapNum] ?? []) {
            const s = row[speedIdx]
            if (s != null) { if (s < lo) lo = s; if (s > hi) hi = s }
          }
        }
        if (lo !== Infinity) { globalMinSpeed = lo; globalMaxSpeed = hi }
      }

      for (let i = 0; i < laps.length; i++) {
        const lapNum = laps[i]
        const lapData = rows[lapNum]
        if (!lapData || lapData.length < 2) continue

        const isCmp = i === 1
        const color = lapColorMap[lapNum] ?? '#ffffff'
        const sid = `trk-s-${lapNum}`
        const lid = `trk-l-${lapNum}`

        try {
          if (useSpeedColor) {
            // Build speed-gradient stops (downsampled to ~500 points)
            const step = Math.max(1, Math.floor(lapData.length / 500))
            const stops: (number | string)[] = []
            for (let j = 0; j < lapData.length - 1; j += step) {
              const progress = j / (lapData.length - 1)
              const [r, g, b] = speedToColor(lapData[j][speedIdx] ?? globalMinSpeed, globalMinSpeed, globalMaxSpeed)
              stops.push(progress, `rgb(${r},${g},${b})`)
            }
            // Always include endpoint
            const last = lapData[lapData.length - 1]
            const [r, g, b] = speedToColor(last[speedIdx] ?? globalMinSpeed, globalMinSpeed, globalMaxSpeed)
            stops.push(1.0, `rgb(${r},${g},${b})`)

            map.addSource(sid, {
              type: 'geojson',
              lineMetrics: true,
              data: buildLineGeoJSON(lapData, latIdx, lonIdx),
            })
            map.addLayer({
              id: lid,
              type: 'line',
              source: sid,
              layout: { 'line-join': 'round', 'line-cap': 'round' },
              paint: {
                'line-width': isCmp ? 2 : 3,
                'line-opacity': isCmp ? 0.7 : 1,
                'line-gradient': ['interpolate', ['linear'], ['line-progress'], ...stops] as maplibregl.ExpressionSpecification,
              },
            })
          } else {
            map.addSource(sid, { type: 'geojson', data: buildLineGeoJSON(lapData, latIdx, lonIdx) })
            map.addLayer({
              id: lid,
              type: 'line',
              source: sid,
              layout: { 'line-join': 'round', 'line-cap': 'round' },
              paint: {
                'line-color': color,
                'line-width': isCmp ? 2 : 3,
                'line-opacity': isCmp ? 0.7 : 1,
                ...(isCmp ? { 'line-dasharray': [4, 3] } : {}),
              },
            })
          }
          prevLayerIdsRef.current.push(lid, sid)
        } catch {
          // Source/layer may already exist during rapid re-renders
        }

        for (const row of lapData) allCoords.push([row[lonIdx], row[latIdx]])

        // Create cursor marker
        const sz = isCmp ? 8 : 11
        const el = document.createElement('div')
        el.style.cssText = `width:${sz}px;height:${sz}px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 0 6px ${color}99;pointer-events:none;display:none;`
        const marker = new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat([0, 0]).addTo(map)
        markersRef.current.set(lapNum, marker)
      }

      // Sectors
      if (circuit?.sectors?.length) {
        map.addSource('sector-source', {
          type: 'geojson',
          data: {
            type: 'FeatureCollection',
            features: circuit.sectors.map((s) => ({
              type: 'Feature',
              properties: { label: `S${s.sector_number}` },
              geometry: { type: 'Point', coordinates: [s.trigger_lon, s.trigger_lat] },
            })),
          },
        })
        map.addLayer({
          id: 'sector-labels', type: 'symbol', source: 'sector-source',
          layout: { 'text-field': ['get', 'label'], 'text-size': 12, 'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'], 'text-anchor': 'center' },
          paint: { 'text-color': '#fff', 'text-halo-color': '#0a0a0f', 'text-halo-width': 2 },
        })
      }

      // Fit bounds
      if (allCoords.length > 1) {
        const bounds = allCoords.reduce((b, c) => b.extend(c), new maplibregl.LngLatBounds(allCoords[0], allCoords[0]))
        map.fitBounds(bounds, { padding: 40, maxZoom: 16, duration: 600 })
      }

      // Immediately position cursors if there's an active cursor distance
      updateCursorMarkers(cursorDistanceMRef.current)
    }

    // If map style is ready, draw immediately. Otherwise wait for load.
    // But if we have no channel data yet (overlay still loading), skip —
    // the effect will re-fire when drawKey changes once data arrives.
    const hasData = channelsRef.current.length > 0
    if (map.isStyleLoaded()) {
      doWork()
    } else if (hasData) {
      map.once('load', doWork)
      return () => { map.off('load', doWork) }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drawKey])

  // Shared function to update all cursor markers — called from both draw and cursor effects
  function updateCursorMarkers(distanceM: number | null) {
    const chs = channelsRef.current
    const distIdx = chs.indexOf('distance_m')
    const latIdx = chs.indexOf('lat')
    const lonIdx = chs.indexOf('lon')
    if (distIdx === -1 || latIdx === -1 || lonIdx === -1) return

    for (const lapNum of selectedLapsRef.current) {
      const marker = markersRef.current.get(lapNum)
      if (!marker) continue
      const el = marker.getElement()

      if (distanceM === null) {
        el.style.display = 'none'
        continue
      }

      const rows = lapRowsRef.current[lapNum]
      if (!rows?.length) { el.style.display = 'none'; continue }

      // Normalize: cursorDistanceM is zero-based (from chart), but rows use
      // cumulative session distance. Offset by this lap's first distance sample.
      const lapOffset = rows[0][distIdx]
      const targetDist = distanceM + lapOffset

      let bestIdx = 0
      let bestDiff = Infinity
      for (let j = 0; j < rows.length; j++) {
        const d = Math.abs(rows[j][distIdx] - targetDist)
        if (d < bestDiff) { bestDiff = d; bestIdx = j }
      }
      const row = rows[bestIdx]
      if (row) {
        marker.setLngLat([row[lonIdx], row[latIdx]])
        el.style.display = 'block'
      }
    }
  }

  // ── Move markers on cursor — reads from refs, only depends on cursorDistanceM ──
  useEffect(() => {
    updateCursorMarkers(cursorDistanceM)
  }, [cursorDistanceM])

  return (
    <div className="relative w-full h-full rounded-lg overflow-hidden border border-[#1e1e2e]">
      <div ref={containerRef} className="w-full h-full" />
      {!hasTelemetry && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#0a0a0f]/60 backdrop-blur-sm">
          <p className="text-xs text-[#6b7280]">Select laps to see GPS trace</p>
        </div>
      )}
    </div>
  )
}
