import client from './client'
import type { UserResponse } from '../types/api'

export async function listUsers(): Promise<UserResponse[]> {
  const response = await client.get<UserResponse[]>('/users')
  return response.data
}

export async function adminUpdateUser(
  userId: string,
  data: { role?: string; is_active?: boolean },
): Promise<UserResponse> {
  const response = await client.patch<UserResponse>(`/users/${userId}`, data)
  return response.data
}
