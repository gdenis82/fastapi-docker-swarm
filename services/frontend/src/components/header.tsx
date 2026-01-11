'use client';

import Link from 'next/link';
import { useAuthStore } from '@/store/auth-store';
import { Button } from '@/components/ui/button';
import { ModeToggle } from '@/components/mode-toggle';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { User } from 'lucide-react';

export function Header() {
  const { user, isAuthenticated, logout, isLoading } = useAuthStore();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center justify-between px-4 md:px-6">
        <div className="flex items-center gap-6">
          <Link href="/" className="font-bold">
            FastAPI + Next.js
          </Link>
          <nav className="hidden md:flex items-center gap-4 text-sm font-medium">
            <Link href="/about">About</Link>
            <Link href="/contacts">Contacts</Link>
            {user?.role_obj?.name === 'admin' && (
              <Link href="/admin">Admin</Link>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <ModeToggle />
          {!isLoading && (
            isAuthenticated ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon">
                    <User className="h-5 w-5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem asChild>
                    <Link href="/profile">Profile</Link>
                  </DropdownMenuItem>
                  {user?.role_obj?.name === 'admin' && (
                    <DropdownMenuItem asChild>
                      <Link href="/admin">Admin Panel</Link>
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem onClick={logout}>
                    Logout
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <div className="flex items-center gap-2">
                <Button variant="ghost" asChild>
                  <Link href="/auth/signin">Sign In</Link>
                </Button>
                <Button asChild>
                  <Link href="/auth/signup">Sign Up</Link>
                </Button>
              </div>
            )
          )}
        </div>
      </div>
    </header>
  );
}
