import { useCallback } from 'react';
import { useApiState } from '../stores/api-store';

export function useApi<T>(url: string) {
  const apiState = useApiState<T>(url);

  const fetchData = useCallback(async () => {
    try {
      await apiState.fetchData();
    } catch (error) {
      // Error is already handled in the store
      console.error('API fetch error:', error);
    }
  }, [apiState]);

  return {
    data: apiState.data,
    loading: apiState.loading,
    error: apiState.error,
    fetchData,
  };
}

export default useApi; 