'use client';

import { Button } from '@/components/ui/button';
import Link from 'next/link';
import { useAuthStore } from '@/store/auth-store';

export default function Home() {
  const { isAuthenticated, isLoading } = useAuthStore();

  return (
    <div className="flex flex-col gap-20 pb-20">
      <section className="container pt-20 text-center px-4 md:px-6">
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-6xl">
          FastAPI + Next.js Starter
        </h1>
        <p className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto">
          A powerful template with authentication, admin panel, and modern UI.
          Built with App Router, Tailwind CSS, shadcn/ui, and TanStack Query.
        </p>
        <div className="mt-10 flex items-center justify-center gap-4">
          {!isLoading && !isAuthenticated && (
            <Button size="lg" asChild>
              <Link href="/auth/signup">Get Started</Link>
            </Button>
          )}
          <Button size="lg" variant="outline" asChild>
            <Link href="/about">Learn More</Link>
          </Button>
        </div>
      </section>

      <section className="container px-4 md:px-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="p-6 border rounded-lg bg-card text-card-foreground shadow-sm">
            <h3 className="text-xl font-bold">Authentication</h3>
            <p className="mt-2 text-muted-foreground">
              Secure auth with JWT, httpOnly cookies, and role-based access.
            </p>
          </div>
          <div className="p-6 border rounded-lg bg-card text-card-foreground shadow-sm">
            <h3 className="text-xl font-bold">Admin Panel</h3>
            <p className="mt-2 text-muted-foreground">
              Manage users with a powerful table featuring pagination and search.
            </p>
          </div>
          <div className="p-6 border rounded-lg bg-card text-card-foreground shadow-sm">
            <h3 className="text-xl font-bold">Dark Mode</h3>
            <p className="mt-2 text-muted-foreground">
              Seamlessly switch between light and dark themes.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
