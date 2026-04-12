import client from './client'
import type { TokenResponse, UserResponse } from '../types/api'

export async function login(email: string, password: string): Promise<TokenResponse & { user: UserResponse }> {
  const response = await client.post<TokenResponse>('/auth/login', { email, password })
  const tokens = response.data
  localStorage.setItem('access_token', tokens.access_token)
  localStorage.setItem('refresh_token', tokens.refresh_token)

  // Fetch user profile
  const userResponse = await client.get<UserResponse>('/users/me', {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  })
  return { ...tokens, user: userResponse.data }
}

export async function register(
  email: string,
  password: string,
  displayName: string,
  inviteCode?: string,
): Promise<TokenResponse> {
  const response = await client.post<TokenResponse>('/auth/register', {
    email,
    password,
    display_name: displayName,
    ...(inviteCode ? { invite_code: inviteCode } : {}),
  })
  const tokens = response.data
  localStorage.setItem('access_token', tokens.access_token)
  localStorage.setItem('refresh_token', tokens.refresh_token)
  return tokens
}

export async function logout(): Promise<void> {
  try {
    await client.post('/auth/logout')
  } catch {
    // ignore errors on logout
  } finally {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }
}

export async function refreshToken(): Promise<TokenResponse> {
  const refresh = localStorage.getItem('refresh_token')
  const response = await client.post<TokenResponse>('/auth/refresh', {
    refresh_token: refresh,
  })
  const tokens = response.data
  localStorage.setItem('access_token', tokens.access_token)
  if (tokens.refresh_token) {
    localStorage.setItem('refresh_token', tokens.refresh_token)
  }
  return tokens
}

export async function getMe(): Promise<UserResponse> {
  const response = await client.get<UserResponse>('/users/me')
  return response.data
}
