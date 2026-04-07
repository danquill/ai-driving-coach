import { create } from 'zustand'
import { LAP_COLORS } from '../utils/colors'

// ─── Types ────────────────────────────────────────────────────────────────────

interface User {
  id: string
  email: string
  display_name: string
  role: string
}

interface UploadState {
  progress: number
  status: string
  filename: string
}

interface AppState {
  // Auth slice
  accessToken: string | null
  user: User | null
  setAuth: (token: string, user: User) => void
  clearAuth: () => void

  // Analysis slice
  selectedLapNumbers: number[]
  lapColorMap: Record<number, string>
  selectedChannels: string[]
  cursorDistanceM: number | null
  toggleLap: (lapNumber: number) => void
  clearLaps: () => void
  setChannels: (channels: string[]) => void
  setCursorDistanceM: (distance: number | null) => void

  // Upload slice
  uploads: Record<string, UploadState>
  setUploadProgress: (key: string, progress: number, filename: string) => void
  setUploadStatus: (key: string, status: string) => void
  clearUpload: (key: string) => void
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useStore = create<AppState>((set, get) => ({
  // ── Auth ──────────────────────────────────────────────────────────────────
  accessToken: localStorage.getItem('access_token'),
  user: (() => {
    try {
      const raw = localStorage.getItem('user')
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })(),

  setAuth: (token, user) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('user', JSON.stringify(user))
    set({ accessToken: token, user })
  },

  clearAuth: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    set({ accessToken: null, user: null })
  },

  // ── Analysis ──────────────────────────────────────────────────────────────
  selectedLapNumbers: [],
  lapColorMap: {},
  selectedChannels: ['speed_kph', 'throttle_pct', 'brake_pct'],
  cursorDistanceM: null,

  toggleLap: (lapNumber) => {
    const { selectedLapNumbers, lapColorMap } = get()
    if (selectedLapNumbers.includes(lapNumber)) {
      // deselect
      const next = selectedLapNumbers.filter((n) => n !== lapNumber)
      const nextMap = { ...lapColorMap }
      delete nextMap[lapNumber]
      set({ selectedLapNumbers: next, lapColorMap: nextMap })
    } else {
      if (selectedLapNumbers.length >= 2) return // max 2
      // assign next available color
      const usedColors = new Set(Object.values(lapColorMap))
      const nextColor = LAP_COLORS.find((c) => !usedColors.has(c)) ?? LAP_COLORS[0]
      set({
        selectedLapNumbers: [...selectedLapNumbers, lapNumber],
        lapColorMap: { ...lapColorMap, [lapNumber]: nextColor },
      })
    }
  },

  clearLaps: () => set({ selectedLapNumbers: [], lapColorMap: {} }),

  setChannels: (channels) => set({ selectedChannels: channels }),

  setCursorDistanceM: (distance) => set({ cursorDistanceM: distance }),

  // ── Uploads ───────────────────────────────────────────────────────────────
  uploads: {},

  setUploadProgress: (key, progress, filename) =>
    set((state) => ({
      uploads: {
        ...state.uploads,
        [key]: {
          progress,
          filename,
          status: progress < 100 ? 'uploading' : 'processing',
        },
      },
    })),

  setUploadStatus: (key, status) =>
    set((state) => ({
      uploads: {
        ...state.uploads,
        [key]: { ...(state.uploads[key] ?? { progress: 100, filename: key }), status },
      },
    })),

  clearUpload: (key) =>
    set((state) => {
      const next = { ...state.uploads }
      delete next[key]
      return { uploads: next }
    }),
}))
