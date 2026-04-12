import client from './client'

export interface Invite {
  id: string
  code: string
  email: string | null
  used_at: string | null
  created_at: string
}

export async function listInvites(): Promise<Invite[]> {
  const response = await client.get<Invite[]>('/invites/')
  return response.data
}

export async function createInvite(email?: string): Promise<Invite> {
  const response = await client.post<Invite>('/invites/', { email: email || null })
  return response.data
}

export async function deleteInvite(id: string): Promise<void> {
  await client.delete(`/invites/${id}`)
}
