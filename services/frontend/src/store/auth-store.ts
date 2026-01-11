import { create, StateCreator } from 'zustand';
import Cookies from 'js-cookie';

export interface User {
  id: string;
  email: string;
  username: string;
  name?: string;
  role: string;
  role_id?: number;
  is_active?: boolean;
  role_name?: string;
  role_obj?: {
    id: number;
    name: string;
    description?: string;
  };
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuth: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

const authStoreCreator: StateCreator<AuthState> = (set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  setAuth: (user) => set({ user, isAuthenticated: !!user, isLoading: false }),
  setLoading: (loading) => set({ isLoading: loading }),
  logout: async () => {
    try {
      // We import apiClient dynamically to avoid circular dependencies if any
      const { default: apiClient } = await import('@/lib/axios');
      await apiClient.post('/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      Cookies.remove('token');
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
});

export const useAuthStore = create<AuthState>(authStoreCreator);
