/** REST API wrapper. */

import { API_BASE } from './constants';

/** FastAPI's `detail` is a string for HTTPException and a list of
 *  {loc, msg} for validation errors; `new Error(array)` would turn the
 *  latter into "[object Object]". Keep the raw detail and render it. */
export function formatDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === 'object' && 'msg' in d) {
          const loc = (d as { loc?: unknown }).loc;
          const where = Array.isArray(loc) ? loc.filter((x) => x !== 'body').join('.') : loc;
          return where ? `${where}: ${(d as { msg: string }).msg}` : (d as { msg: string }).msg;
        }
        return String(d);
      })
      .join(' · ');
  }
  if (detail === undefined || detail === null) return 'Request failed';
  return typeof detail === 'object' ? JSON.stringify(detail) : String(detail);
}

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(formatDetail(detail));
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
    throw new ApiError(res.status, body.detail ?? res.statusText);
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
      throw new ApiError(res.status, body.detail ?? res.statusText);
    }
    return res.json();
  },
};
