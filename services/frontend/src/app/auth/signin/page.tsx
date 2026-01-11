'use client';

import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { loginSchema } from '@/lib/validations';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import Link from 'next/link';
import apiClient from '@/lib/axios';
import axios from 'axios';
import { toast } from 'sonner';
import Cookies from 'js-cookie';
import { useAuthStore } from '@/store/auth-store';

type LoginForm = z.infer<typeof loginSchema>;

export default function SignInPage() {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);
  
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    try {
      // Use FormData for OAuth2PasswordRequestForm compatibility on backend
      const formData = new FormData();
      formData.append('username', data.email);
      formData.append('password', data.password);
      
      const response = await apiClient.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      const { access_token } = response.data;
      
      // Access token is short-lived, stored in JS-accessible cookie for axios interceptor
      // Refresh token is handled by the browser via HttpOnly cookie
      Cookies.set('token', access_token);
      
      // Fetch user info after login
      const meResponse = await apiClient.get('/auth/me');
      setAuth(meResponse.data);
      
      toast.success('Logged in successfully');
      router.push('/');
    } catch (error) {
      console.error('Login error:', error);
      let errorMessage = 'Failed to sign in';
      
      if (axios.isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (Array.isArray(detail)) {
          errorMessage = detail[0]?.msg || 'Validation error';
        } else if (typeof detail === 'string') {
          errorMessage = detail;
        }
      }
      
      toast.error(errorMessage);
    }
  };

  return (
    <div className="container flex h-[calc(100vh-3.5rem)] items-center justify-center">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Sign In</CardTitle>
          <CardDescription>
            Enter your email and password to access your account
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="m@example.com"
                autoComplete="email"
                {...register('email')}
              />
              {errors.email && (
                <p className="text-sm text-destructive">{errors.email.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <Link
                  href="/auth/forgot-password"
                  className="text-sm text-primary hover:underline"
                >
                  Forgot password?
                </Link>
              </div>
              <Input 
                id="password" 
                type="password" 
                autoComplete="current-password"
                {...register('password')} 
              />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full mt-2" disabled={isSubmitting}>
              {isSubmitting ? 'Signing in...' : 'Sign In'}
            </Button>

            <div className="text-sm text-center">
              Don&apos;t have an account?{' '}
              <Link href="/auth/signup" className="text-primary hover:underline">
                Sign Up
              </Link>
            </div>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
