import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import api from '../services/api';

interface ApiState<T = unknown> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  timestamp?: number;
}

interface ApiStore {
  // Store for different API endpoints
  apiStates: Record<string, ApiState>;
  
  // Actions
  setLoading: (url: string, loading: boolean) => void;
  setData: <T>(url: string, data: T) => void;
  setError: (url: string, error: Error | null) => void;
  clearState: (url: string) => void;
  clearOldStates: (maxStates?: number) => void;
  
  // API call wrappers
  fetchData: <T>(url: string) => Promise<T>;
  postData: <T>(url: string, data: unknown) => Promise<T>;
  patchData: <T>(url: string, data: unknown) => Promise<T>;
  deleteData: <T>(url: string) => Promise<T>;
  
  // Convenience methods
  updateData: <T>(url: string, data: unknown) => Promise<T>;
  getApiState: (url: string) => ApiState;
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
              timestamp: Date.now(),
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
      
      clearOldStates: (maxStates: number = 50) => {
        set((state) => {
          const entries = Object.entries(state.apiStates);
          if (entries.length <= maxStates) {
            return state;
          }
          
          // Sort by timestamp (newest first), fallback to keeping existing order
          const sortedEntries = entries.sort((a, b) => 
            (b[1].timestamp || 0) - (a[1].timestamp || 0)
          );
          
          // Keep only the most recent maxStates entries
          const newStates = Object.fromEntries(sortedEntries.slice(0, maxStates));
          return { apiStates: newStates };
        }, false, 'clearOldStates');
      },
      
      fetchData: async <T>(url: string): Promise<T> => {
        const { setLoading, setData, setError, clearOldStates } = get();
        
        setLoading(url, true);
        
        try {
          const response = await api.get<T>(url) as T;
          setData(url, response);
          
          // Periodically clean old states to prevent memory leaks
          if (Math.random() < 0.1) { // 10% chance to trigger cleanup
            clearOldStates();
          }
          
          return response;
        } catch (error) {
          const apiError = error as Error;
          setError(url, apiError);
          throw apiError;
        }
      },
      
      postData: async <T>(url: string, data: unknown): Promise<T> => {
        const { setLoading, setData, setError } = get();
        
        setLoading(url, true);
        
        try {
          const response = await api.post<T>(url, data) as T;
          setData(url, response);
          return response;
        } catch (error) {
          const apiError = error as Error;
          setError(url, apiError);
          throw apiError;
        }
      },
      
      patchData: async <T>(url: string, data: unknown): Promise<T> => {
        const { setLoading, setData, setError } = get();
        
        setLoading(url, true);
        
        try {
          const response = await api.patch<T>(url, data) as T;
          setData(url, response);
          return response;
        } catch (error) {
          const apiError = error as Error;
          setError(url, apiError);
          throw apiError;
        }
      },
      
      deleteData: async <T>(url: string): Promise<T> => {
        const { setLoading, setData, setError } = get();
        
        setLoading(url, true);
        
        try {
          const response = await api.delete<T>(url) as T;
          setData(url, response);
          return response;
        } catch (error) {
          const apiError = error as Error;
          setError(url, apiError);
          throw apiError;
        }
      },
      
      updateData: async <T>(url: string, data: unknown): Promise<T> => {
        return get().patchData<T>(url, data);
      },
      
      getApiState: (url: string): ApiState => {
        const state = get().apiStates[url];
        return state || { data: null, loading: false, error: null };
      },
    }),
    {
      name: 'api-store',
    }
  )
);

