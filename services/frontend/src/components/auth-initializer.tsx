'use client';

import { useEffect, useRef } from 'react';
import { useAuthStore } from '@/store/auth-store';
import apiClient from '@/lib/axios';
import Cookies from 'js-cookie';

export function AuthInitializer({ children }: { children: React.ReactNode }) {
  const { setAuth, setLoading } = useAuthStore();
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    const initAuth = async () => {
      const token = Cookies.get('token');
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const response = await apiClient.get('/auth/me');
        setAuth(response.data);
      } catch (error: any) {
        console.error('Failed to initialize auth:', error.response?.status, error.message);
        setLoading(false);
      }
    };

    initAuth();
  }, [setAuth, setLoading]);

  return <>{children}</>;
}
