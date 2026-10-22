import { ApiError, apiRequest } from './client';

export type Role = 'CLIENT' | 'BANK_EMPLOYEE';
export type User = { id: number; role: Role; company_id: number | null };

function parseUser(value: unknown): User {
  if (value === null || typeof value !== 'object' || !('id' in value) || !('role' in value)
      || !('company_id' in value) || !Number.isSafeInteger(value.id) || Number(value.id) <= 0
      || (value.role !== 'CLIENT' && value.role !== 'BANK_EMPLOYEE')
      || (value.company_id !== null && (!Number.isSafeInteger(value.company_id) || Number(value.company_id) <= 0))) {
    throw new ApiError(0, 'contract');
  }
  return { id: value.id as number, role: value.role, company_id: value.company_id as number | null };
}

export const authApi = {
  // Bootstrap owns its 401 handling, so an obsolete response cannot clear a newer login.
  async me(): Promise<User> { return parseUser(await apiRequest('/api/me', { public: true })); },
  async login(login: string, password: string) {
    const data = await apiRequest('/api/auth/login', { method: 'POST', body: { login, password }, public: true });
    const user = parseUser(data);
    if (data === null || typeof data !== 'object' || !('csrf_token' in data)
        || typeof data.csrf_token !== 'string' || !data.csrf_token) throw new ApiError(0, 'contract');
    return { user, csrf: data.csrf_token };
  },
  async logout() { await apiRequest('/api/auth/logout', { method: 'POST' }); },
};
