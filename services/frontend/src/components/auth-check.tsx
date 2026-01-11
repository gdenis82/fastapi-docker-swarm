'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/store/auth-store';
import { useRouter, usePathname } from 'next/navigation';

export function AuthBarrier({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, isLoading, logout } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated) {
      router.push('/auth/signin');
      return;
    }

    if (pathname.startsWith('/admin') && user?.role_obj?.name !== 'admin') {
      router.push('/');
    }
  }, [isAuthenticated, isLoading, user, pathname, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  if (pathname.startsWith('/admin') && user?.role_obj?.name !== 'admin') {
    return null;
  }

  return <>{children}</>;
}
