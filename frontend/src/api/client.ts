const API_BASE_URL = '/api/v1';

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('access_token');
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errMessage = 'Request failed';
    let errData = null;
    try {
      errData = await response.json();
      if (Array.isArray(errData?.detail)) {
        errMessage = errData.detail.map((d: any) => d.msg || JSON.stringify(d)).join(' | ');
      } else if (typeof errData?.detail === 'string') {
        errMessage = errData.detail;
      } else if (errData?.message) {
        errMessage = errData.message;
      } else {
        errMessage = JSON.stringify(errData);
      }
    } catch {
      errMessage = response.statusText;
    }
    throw new ApiError(response.status, errMessage, errData);
  }

  return response.json();
}

export const api = {
  get: <T>(url: string) => request<T>(url, { method: 'GET' }),
  post: <T>(url: string, body?: any) => request<T>(url, { method: 'POST', body: JSON.stringify(body) }),
  postForm: <T>(url: string, formData: FormData) => request<T>(url, { method: 'POST', body: formData }),
  put: <T>(url: string, body?: any) => request<T>(url, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T>(url: string, body?: any) => request<T>(url, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(url: string) => request<T>(url, { method: 'DELETE' }),
};
