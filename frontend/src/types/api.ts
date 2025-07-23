// Common API response type
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

// Error response type
export interface ApiError {
  message: string;
  status: number;
  errors?: Record<string, string[]>;
}

// Pagination response type
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
} 