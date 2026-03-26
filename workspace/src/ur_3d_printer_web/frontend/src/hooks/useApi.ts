import { useState, useCallback } from 'react';
import { api, ApiError } from '../lib/api';

interface ApiHookState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useApiPost<TReq, TRes>(path: string) {
  const [state, setState] = useState<ApiHookState<TRes>>({
    data: null,
    loading: false,
    error: null,
  });

  const execute = useCallback(
    async (body?: TReq): Promise<TRes | null> => {
      setState({ data: null, loading: true, error: null });
      try {
        const data = await api.post<TRes>(path, body);
        setState({ data, loading: false, error: null });
        return data;
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Unknown error';
        setState({ data: null, loading: false, error: message });
        return null;
      }
    },
    [path],
  );

  return { ...state, execute };
}

export function useApiUpload<TRes>(path: string) {
  const [state, setState] = useState<ApiHookState<TRes>>({
    data: null,
    loading: false,
    error: null,
  });

  const execute = useCallback(
    async (file: File): Promise<TRes | null> => {
      setState({ data: null, loading: true, error: null });
      try {
        const data = await api.uploadFile<TRes>(path, file);
        setState({ data, loading: false, error: null });
        return data;
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Unknown error';
        setState({ data: null, loading: false, error: message });
        return null;
      }
    },
    [path],
  );

  return { ...state, execute };
}
