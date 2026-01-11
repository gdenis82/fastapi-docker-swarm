'use client';

import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { registerSchema } from '@/lib/validations';
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

type RegisterForm = z.infer<typeof registerSchema>;

export default function SignUpPage() {
  const router = useRouter();
  
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (values: RegisterForm) => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { confirmPassword, ...data } = values;
      await apiClient.post('/auth/register', data);
      toast.success('Registered successfully! You can now sign in.');
      router.push('/auth/signin');
    } catch (error) {
      console.error('Registration error:', error);
      let errorMessage = 'Failed to register';
      
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
          <CardTitle>Sign Up</CardTitle>
          <CardDescription>
            Create an account to get started
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                placeholder="johndoe"
                autoComplete="username"
                {...register('username')}
              />
              {errors.username && (
                <p className="text-sm text-destructive">{errors.username.message}</p>
              )}
            </div>
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
              <Label htmlFor="password">Password</Label>
              <Input 
                id="password" 
                type="password" 
                autoComplete="new-password"
                {...register('password')} 
              />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm Password</Label>
              <Input 
                id="confirmPassword" 
                type="password" 
                autoComplete="new-password"
                {...register('confirmPassword')} 
              />
              {errors.confirmPassword && (
                <p className="text-sm text-destructive">{errors.confirmPassword.message}</p>
              )}
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full mt-2" disabled={isSubmitting}>
              {isSubmitting ? 'Creating account...' : 'Sign Up'}
            </Button>

            <div className="text-sm text-center">
              Already have an account?{' '}
              <Link href="/auth/signin" className="text-primary hover:underline">
                Sign In
              </Link>
            </div>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
