'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { profileSchema } from '@/lib/validations';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuthStore } from '@/store/auth-store';
import { useEffect } from 'react';
import apiClient from '@/lib/axios';
import axios from 'axios';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';

type ProfileForm = z.infer<typeof profileSchema>;

export default function ProfilePage() {
  const { user, setAuth } = useAuthStore();
  const queryClient = useQueryClient();
  
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      username: user?.username || '',
      email: user?.email || '',
      password: '',
    },
  });
  
  useEffect(() => {
    if (user) {
      reset({
        username: user.username || '',
        email: user.email || '',
        password: '',
      });
    }
  }, [user, reset]);
  
  const onSubmit = async (data: ProfileForm) => {
    try {
      const filteredData = Object.fromEntries(
        Object.entries(data).filter(([_, v]) => v !== '')
      );
      const response = await apiClient.patch('/auth/me', filteredData);
      setAuth(response.data);
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      toast.success('Profile updated successfully');
      reset({ ...response.data, password: '' });
    } catch (error) {
      let errorMessage = 'Failed to update profile';
      if (axios.isAxiosError(error)) {
        errorMessage = error.response?.data?.detail || errorMessage;
      }
      toast.error(errorMessage);
    }
  };
  
  if (!user) {
    return <div className="container py-20 text-center text-muted-foreground">Loading...</div>;
  }
  
  return (
    <div className="container py-20">
      <div className="max-w-md mx-auto">
        <Card>
          <CardHeader>
            <CardTitle>Profile Settings</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input id="username" {...register('username')} />
                {errors.username && (
                  <p className="text-sm text-destructive">{errors.username.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" {...register('email')} />
                {errors.email && (
                  <p className="text-sm text-destructive">{errors.email.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">New Password (leave blank to keep current)</Label>
                <Input id="password" type="password" {...register('password')} />
                {errors.password && (
                  <p className="text-sm text-destructive">{errors.password.message}</p>
                )}
              </div>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? 'Saving...' : 'Save Changes'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
