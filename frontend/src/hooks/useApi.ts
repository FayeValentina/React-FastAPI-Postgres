import { useState, useCallback } from 'react';
import api from '../services/api';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

export function useApi<T>(url: string) {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  const fetchData = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true }));
    try {
      const data = await api.get<T>(url);
      setState({ data: data as unknown as T, loading: false, error: null });
    } catch (error) {
      setState({ data: null, loading: false, error: error as Error });
    }
  }, [url]);

  return {
    ...state,
    fetchData,
  };
}

export default useApi; 