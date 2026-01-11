'use client';

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/axios';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { useAuthStore, User } from '@/store/auth-store';
import { useRouter } from 'next/navigation';

export default function AdminPage() {
  const { user } = useAuthStore();
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [role, setRole] = useState('all');
  const [sort, setSort] = useState('username:asc');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 500);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading } = useQuery<{ users: User[], total: number }>({
    queryKey: ['admin-users', page, limit, debouncedSearch, role, sort],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString(),
        search: debouncedSearch,
        sort,
      });
      if (role !== 'all') params.append('role', role);
      
      const response = await apiClient.get(`/admin/users?${params.toString()}`);
      return response.data;
    },
    enabled: !!user && user.role_obj?.name === 'admin',
    staleTime: 0,
  });

  if (!user || user.role_obj?.name !== 'admin') {
    return null;
  }

  const toggleSort = (field: string) => {
    const [currentField, order] = sort.split(':');
    if (currentField === field) {
      setSort(`${field}:${order === 'asc' ? 'desc' : 'asc'}`);
    } else {
      setSort(`${field}:asc`);
    }
  };

  const displayName = (u: User) => {
    return u.username || 'N/A';
  };

  return (
    <div className="container py-10 space-y-6">
      <h1 className="text-3xl font-bold">Admin Dashboard</h1>
      
      <div className="flex flex-wrap gap-4 items-end">
        <div className="flex-1 min-w-[200px] space-y-2">
          <Input
            placeholder="Search users..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="w-[150px] space-y-2">
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger>
              <SelectValue placeholder="Role" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Roles</SelectItem>
              <SelectItem value="admin">Admin</SelectItem>
              <SelectItem value="user">User</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="w-[100px] space-y-2">
          <Select value={limit.toString()} onValueChange={(v) => { setLimit(Number(v)); setPage(1); }}>
            <SelectTrigger>
              <SelectValue placeholder="Limit" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10</SelectItem>
              <SelectItem value="25">25</SelectItem>
              <SelectItem value="50">50</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead onClick={() => toggleSort('username')} className="cursor-pointer">
                Username {sort.startsWith('username') && (sort.endsWith('asc') ? ' \u2191' : ' \u2193')}
              </TableHead>
              <TableHead onClick={() => toggleSort('email')} className="cursor-pointer">
                Email {sort.startsWith('email') && (sort.endsWith('asc') ? ' \u2191' : ' \u2193')}
              </TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center">Loading...</TableCell>
              </TableRow>
            ) : data?.users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center">No users found</TableCell>
              </TableRow>
            ) : (
              data?.users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>{displayName(u)}</TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell>{u.role_name}</TableCell>
                  <TableCell>{u.is_active ? 'Active' : 'Inactive'}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm">Edit</Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex justify-between items-center">
        <div className="text-sm text-muted-foreground">
          Showing {((page - 1) * limit) + 1} to {Math.min(page * limit, data?.total || 0)} of {data?.total || 0} users
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => p + 1)}
            disabled={!data || page * limit >= data.total}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
