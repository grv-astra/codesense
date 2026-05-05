import React, { useState } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { Card } from '@/components/atomic/card';
import { useCreateUser } from '@/hooks/use-user';
import { useAuth } from '@/hooks/use-auth';
import { Button } from '@/components/atomic/button';
import { Input } from '@/components/atomic/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/atomic/select';
import { toast } from 'sonner';
import { AxiosError } from 'axios';
import { Unauthorized } from '@/components/molecule/unauthorized';

export const Route = createFileRoute('/_authenticated/users/new')({
  component: RouteComponent,
});

interface FormData {
  company: string;
  name: string;
  email: string;
  password: string;
  confirmPassword: string;
  role: 'manager' | 'user' | '';
}

function RouteComponent() {
  const navigate = useNavigate();
  const createUserMutation = useCreateUser();
  const { user, isLoading } = useAuth();

  const [form, setForm] = useState<FormData>({
    company: '',
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    role: '',
  });

  const [errors, setErrors] = useState<Partial<FormData>>({});

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));

    // Clear error on input change
    if (errors[name as keyof FormData]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  };

  // Handle Select component value change
  const handleSelectChange = (value: string) => {
    setForm((prev) => ({ ...prev, role: value as FormData['role'] }));
    
    // Clear error on select change
    if (errors.role) {
      setErrors((prev) => ({ ...prev, role: undefined }));
    }
  };

  const validate = (): boolean => {
    const newErrors: Partial<FormData> = {};

    if (!form.company.trim()) newErrors.company = 'Company name is required';
    if (!form.name.trim()) newErrors.name = 'Username is required';
    if (!form.email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(form.email)) {
      newErrors.email = 'Please enter a valid email address';
    }
    if (!form.password.trim()) {
      newErrors.password = 'Password is required';
    } else if (form.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters long';
    }
    if (!form.confirmPassword.trim()) {
      newErrors.confirmPassword = 'Confirm password is required';
    } else if (form.password !== form.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }
    if (!form.role) newErrors.role = "";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validate()) return;

    try {
      const userData = {
        company: form.company,
        name: form.name,
        email: form.email,
        password: form.password,
        role: form.role as 'manager' | 'user',
      };

      await createUserMutation.mutateAsync(userData);
      
      // Reset form
      setForm({
        company: '',
        name: '',
        email: '',
        password: '',
        confirmPassword: '',
        role: '',
      });
      
      navigate({ to: '/users/list' });
      toast("User Registered", {
        description: `User (${form.email}) has been added`,
      });
    } catch (err) {
      if (err instanceof AxiosError && err.response) {
        toast("User registration failed", {
          description: err.response.data.detail,
        });
      } else {
        toast("User registration failed", {
          description: "An unexpected error occurred",
        });
      }
    }
  };

  if (isLoading) {
    return <div className="p-6 max-w-8xl mx-auto">Loading...</div>;
  }

  if (user?.role !== 'admin') {
    return <Unauthorized />;
  }

  return (
    <div className="p-6 max-w-8xl mx-auto">
      <Card>
        <form onSubmit={handleSubmit} className="space-y-6 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold">Create New User</h2>
            <Button
              variant="ghost"
              type="button"
              onClick={() => navigate({ to: '/users/list' })}
            >
              ← Back to Users List
            </Button>
          </div>

          {/* Company */}
          <div>
            <label className="block text-sm font-medium mb-1">Company Name</label>
            <Input
              name="company"
              value={form.company}
              onChange={handleChange}
              disabled={createUserMutation.isPending}
              className={`${
                errors.company ? 'border-destructive bg-destructive/10' : ''
              }`}
              placeholder="Enter company name"
            />
            {errors.company && <p className="text-sm text-destructive mt-1">{errors.company}</p>}
          </div>

          {/* Username */}
          <div>
            <label className="block text-sm font-medium mb-1">Username</label>
            <Input
              name="name"
              value={form.name}
              onChange={handleChange}
              disabled={createUserMutation.isPending}
              className={`${
                errors.name ? 'border-destructive bg-destructive/10' : ''
              }`}
              placeholder="Enter username"
            />
            {errors.name && <p className="text-sm text-destructive mt-1">{errors.name}</p>}
          </div>

          {/* Email */}
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <Input
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              disabled={createUserMutation.isPending}
              className={`${
                errors.email ? 'border-destructive bg-destructive/10' : ''
              }`}
              placeholder="Enter email address"
            />
            {errors.email && <p className="text-sm text-destructive mt-1">{errors.email}</p>}
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm font-medium mb-1">Password</label>
            <Input
              type="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              disabled={createUserMutation.isPending}
              className={`${
                errors.password ? 'border-destructive bg-destructive/10' : ''
              }`}
              placeholder="Enter password (min 6 characters)"
            />
            {errors.password && <p className="text-sm text-destructive mt-1">{errors.password}</p>}
          </div>

          {/* Confirm Password */}
          <div>
            <label className="block text-sm font-medium mb-1">Confirm Password</label>
            <Input
              type="password"
              name="confirmPassword"
              value={form.confirmPassword}
              onChange={handleChange}
              disabled={createUserMutation.isPending}
              className={`${
                errors.confirmPassword ? 'border-destructive bg-destructive/10' : ''
              }`}
              placeholder="Confirm your password"
            />
            {errors.confirmPassword && <p className="text-sm text-destructive mt-1">{errors.confirmPassword}</p>}
          </div>

          {/* Role - Updated to use Shadcn Select */}
          <div>
            <label className="block text-sm font-medium mb-1">Role</label>
            <Select 
              value={form.role} 
              onValueChange={handleSelectChange}
              disabled={createUserMutation.isPending}
            >
              <SelectTrigger className={`${
                errors.role ? 'border-destructive bg-destructive/10' : ''
              }`}>
                <SelectValue placeholder="Select role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="manager">Manager</SelectItem>
                <SelectItem value="user">User</SelectItem>
              </SelectContent>
            </Select>
            {errors.role && <p className="text-sm text-destructive mt-1">{errors.role}</p>}
          </div>

          {/* Submit Button */}
          <div className="flex gap-2">
            <Button
              type="submit"
              disabled={createUserMutation.isPending}
              className="flex-1"
            >
              {createUserMutation.isPending ? 'Creating User...' : 'Create User'}
            </Button>
            <Button
              type="button"
              onClick={() => navigate({ to: '/users/list' })}
              disabled={createUserMutation.isPending}
              variant="secondary"
            >
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}