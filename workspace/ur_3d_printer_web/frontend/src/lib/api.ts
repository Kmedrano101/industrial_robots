/** REST API wrapper. */

import { API_BASE } from './constants';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  return res.json();
}

const withBody = (method: string) => <T>(path: string, body?: unknown) =>
  request<T>(path, { method, body: body ? JSON.stringify(body) : undefined });

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: withBody('POST'),
  put: withBody('PUT'),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),

  uploadFile: async <T>(path: string, file: File): Promise<T> => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, body.detail || res.statusText);
    }
    return res.json();
  },
};
