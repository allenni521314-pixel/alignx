import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import { client } from '../lib/api';
import axios from 'axios';

interface User {
  id: string;
  email: string;
  name?: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  error: string | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  sendEmailCode: (email: string, displayName?: string) => Promise<{ debugCode?: string; delivery: string }>;
  emailLogin: (email: string, code: string, displayName?: string) => Promise<void>;
  refetch: () => Promise<void>;
  isAdmin: boolean;
}

const AUTH_TOKEN_KEY = 'alignx_token';
const AUTH_USER_KEY = 'alignx_user';

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Get the backend API base URL.
 * In production the backend is co-located at the same origin;
 * during local development it may run on a different port.
 */
function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL || '';
}

function getRequestErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length) return detail.map((item) => item.msg || item.message || String(item)).join('；');
    if (err.response?.status) return `请求失败（${err.response.status}），请稍后重试`;
  }

  return err instanceof Error && err.message ? err.message : fallback;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const checkAuthStatus = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // First check if we have an AlignX email-auth token in localStorage
      const storedToken = localStorage.getItem(AUTH_TOKEN_KEY);
      const storedUser = localStorage.getItem(AUTH_USER_KEY);

      if (storedToken && storedUser) {
        try {
          const parsedUser = JSON.parse(storedUser);
          // Verify token is still valid by calling /api/v1/auth/me
          const res = await axios.get(`${getApiBaseUrl()}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${storedToken}` },
          });
          if (res.data) {
            setUser({
              id: res.data.id || parsedUser.id,
              email: res.data.email || parsedUser.email,
              name: res.data.name || parsedUser.name,
              role: res.data.role || parsedUser.role || 'user',
            });
            return;
          }
        } catch {
          // Token expired or invalid, clear storage
          localStorage.removeItem(AUTH_TOKEN_KEY);
          localStorage.removeItem(AUTH_USER_KEY);
        }
      }

      // Fallback: check platform OIDC auth
      try {
        const res = await client.auth.me();
        if (res?.data) {
          setUser({
            id: res.data.id || res.data.sub || '',
            email: res.data.email || '',
            name: res.data.name || res.data.nickname || '',
            role: res.data.role || 'user',
          });
          return;
        }
      } catch {
        // Not authenticated via OIDC either
      }

      setUser(null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const sendEmailCode = useCallback(async (email: string, displayName = '') => {
    setError(null);
    try {
      const res = await axios.post(`${getApiBaseUrl()}/api/v1/auth/email/send-code`, {
        email,
        display_name: displayName,
      });
      return {
        debugCode: res.data?.debug_code || undefined,
        delivery: res.data?.delivery || 'email',
      };
    } catch (err) {
      const message = getRequestErrorMessage(err, '验证码发送失败，请稍后重试');
      setError(message);
      throw new Error(message);
    }
  }, []);

  const emailLogin = useCallback(async (email: string, code: string, displayName = '') => {
    setError(null);
    let res;
    try {
      res = await axios.post(`${getApiBaseUrl()}/api/v1/auth/email/login`, {
        email,
        code,
        display_name: displayName,
      });
    } catch (err) {
      const message = getRequestErrorMessage(err, '登录失败，请稍后重试');
      setError(message);
      throw new Error(message);
    }

    const { token, user: userData } = res.data;

    localStorage.setItem(AUTH_TOKEN_KEY, token);
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(userData));

    // Also set the token for the SDK client (for entity operations)
    try {
      // Set authorization header for future SDK requests
      (window as any).__alignx_token = token;
    } catch {
      // Ignore
    }

    setUser({
      id: userData.id,
      email: userData.email,
      name: userData.name,
      role: userData.role || 'user',
    });
  }, []);

  const login = useCallback(async () => {
    try {
      setError(null);
      // Redirect to login page instead of OIDC
      window.location.href = '/login';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      setError(null);

      // Clear AlignX auth data
      localStorage.removeItem(AUTH_TOKEN_KEY);
      localStorage.removeItem(AUTH_USER_KEY);

      // Also try OIDC logout
      try {
        await client.auth.logout();
      } catch {
        // Ignore OIDC logout errors
      }

      setUser(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Logout failed');
    }
  }, []);

  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  const value: AuthContextType = {
    user,
    loading,
    error,
    login,
    logout,
    sendEmailCode,
    emailLogin,
    refetch: checkAuthStatus,
    isAdmin: user?.role === 'admin' || user?.role === 'super_admin',
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
