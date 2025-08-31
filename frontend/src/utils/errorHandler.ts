export interface ApiError {
  response?: {
    data?: {
      detail?: string | Array<{ msg: string; type: string; loc: string[] }>;
      message?: string;
    };
    status?: number;
  };
  message?: string;
}

export const extractErrorMessage = (error: ApiError): string => {
  // 1. 优先使用后端的具体错误信息
  if (error.response?.data?.detail) {
    if (Array.isArray(error.response.data.detail)) {
      // FastAPI 验证错误数组格式
      return error.response.data.detail
        .map((err: { msg?: string; message?: string }) => err.msg || err.message)
        .join(', ');
    } else {
      // 单个错误字符串格式
      return error.response.data.detail;
    }
  }
  
  // 2. 备选的 message 字段
  if (error.response?.data?.message) {
    return error.response.data.message;
  }
  
  // 3. 根据状态码提供友好的错误信息 (与后端StatusCode保持一致)
  if (error.response?.status) {
    const statusMessages: Record<number, string> = {
      400: '请求参数错误',
      401: '认证失败，请重新登录',
      403: '权限不足，无法执行此操作',
      404: '请求的资源不存在',
      409: '资源冲突，操作无法完成',
      500: '服务器内部错误，请稍后重试',
    };
    return statusMessages[error.response.status] || '请求失败';
  }
  
  // 4. 网络错误等其他情况
  if (error.message) {
    if (error.message.includes('Network Error')) {
      return '网络连接失败，请检查网络连接';
    }
    if (error.message.includes('timeout')) {
      return '请求超时，请重试';
    }
  }
  
  return error.message || '未知错误';
};

// 专门用于认证错误的处理
export const extractAuthErrorMessage = (error: ApiError): string => {
  const message = extractErrorMessage(error);
  
  // 认证相关的错误映射 (与后端ErrorMessages保持一致)
  const authErrorMap: Record<string, string> = {
    '用户名或密码不正确': '用户名或密码不正确',
    '用户不存在': '用户不存在',
    '该邮箱已被注册': '该邮箱已被注册',
    '该用户名已被使用': '该用户名已被使用',
    '用户未激活': '账户未激活，请联系管理员',
    '无效的刷新令牌': '登录已过期，请重新登录',
    '认证错误': '认证失败，请重新登录',
    '权限不足': '权限不足，无法执行此操作',
    'Invalid credentials': '用户名或密码不正确',
    'User not found': '用户不存在',
    'Account locked': '账户已被锁定',
    'Account disabled': '账户已被禁用',
    'Email not verified': '邮箱未验证',
    'Token expired': '登录已过期，请重新登录',
    'Invalid token': '登录状态无效，请重新登录',
  };
  
  return authErrorMap[message] || message;
};