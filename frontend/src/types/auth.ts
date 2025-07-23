// 认证相关的类型定义

// 登录请求
export interface LoginRequest {
  username: string; // 用户名或邮箱
  password: string;
  remember_me?: boolean;
}

// 注册请求
export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
  full_name?: string;
  age?: number;
}

// 令牌响应
export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_at?: string;
}

// 用户信息
export interface User {
  id: number;
  email: string;
  username: string;
  full_name?: string;
  age?: number;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string;
}

// 认证状态
export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
}

// 表单验证错误
export interface FormErrors {
  [key: string]: string[];
}