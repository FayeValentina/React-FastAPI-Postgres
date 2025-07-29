import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import api from '../services/api';

interface ApiState<T = unknown> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

interface ApiStore {
  // Store for different API endpoints
  apiStates: Record<string, ApiState>;
  
  // Actions
  setLoading: (url: string, loading: boolean) => void;
  setData: <T>(url: string, data: T) => void;
  setError: (url: string, error: Error | null) => void;
  clearState: (url: string) => void;
  
  // API call wrapper
  fetchData: <T>(url: string) => Promise<T>;
}

export const useApiStore = create<ApiStore>()(
  devtools(
    (set, get) => ({
      apiStates: {},
      
      setLoading: (url: string, loading: boolean) =>
        set((state) => ({
          apiStates: {
            ...state.apiStates,
            [url]: {
              ...state.apiStates[url],
              loading,
            },
          },
        }), false, 'setLoading'),
      
      setData: <T>(url: string, data: T) =>
        set((state) => ({
          apiStates: {
            ...state.apiStates,
            [url]: {
              ...state.apiStates[url],
              data,
              loading: false,
              error: null,
            },
          },
        }), false, 'setData'),
      
      setError: (url: string, error: Error | null) =>
        set((state) => ({
          apiStates: {
            ...state.apiStates,
            [url]: {
              ...state.apiStates[url],
              error,
              loading: false,
              data: null,
            },
          },
        }), false, 'setError'),
      
      clearState: (url: string) =>
        set((state) => {
          const newStates = { ...state.apiStates };
          delete newStates[url];
          return { apiStates: newStates };
        }, false, 'clearState'),
      
      fetchData: async <T>(url: string): Promise<T> => {
        const { setLoading, setData, setError } = get();
        
        setLoading(url, true);
        
        try {
          const response = await api.get<T>(url);
          setData(url, response);
          return response as T;
        } catch (error) {
          const apiError = error as Error;
          setError(url, apiError);
          throw apiError;
        }
      },
    }),
    {
      name: 'api-store',
    }
  )
);

