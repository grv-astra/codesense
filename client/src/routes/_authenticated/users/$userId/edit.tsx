import React, { useEffect, useState } from 'react';
import { createFileRoute, useNavigate, useParams } from '@tanstack/react-router';
import { Card, CardHeader, CardTitle } from '@/components/atomic/card';
import { useUpdateProfile, useUserProfile } from '@/hooks/use-user';
import { Button } from '@/components/atomic/button';
import { Input } from '@/components/atomic/input';
import { DotsLoader } from '@/components/atomic/loader';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/atomic/select';

export const Route = createFileRoute('/_authenticated/users/$userId/edit')({
  component: RouteComponent,
});

interface FormData {
  company: string;
  name: string;
  email: string;
  password?: string;
  confirmPassword?: string;
  role: 'manager' | 'user' | string;
}

function RouteComponent() {
  const navigate = useNavigate();
  const updateUserMutation = useUpdateProfile();

  const { userId } = useParams({ from: '/_authenticated/users/$userId/edit' });
  const { data: user, isLoading, error } = useUserProfile(userId)

  const [form, setForm] = useState<FormData>({
    company: '',
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    role: '',
  });

  const [errors, setErrors] = useState<Partial<FormData>>({});

  // Initialize form data when user data is loaded
  useEffect(() => {
    if (user) {
      setForm({
        company: user.company || '',
        name: user.name || '',
        email: user.email || '',
        password: '', // Keep empty for security
        confirmPassword: '', // Keep empty for security
        role: user.role || '',
      });
    }
  }, [user]);

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
    
    // Only validate password if it's provided (optional for updates)
    if (form.password && form.password.length > 0) {
      if (form.password.length < 6) {
        newErrors.password = 'Password must be at least 6 characters long';
      }
      if (form.password !== form.confirmPassword) {
        newErrors.confirmPassword = 'Passwords do not match';
      }
    }
    
    if (!form.role) newErrors.role = "Please select a role";

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
        // Only include password if it's provided and not empty
        ...(form.password && form.password.length > 0 && { password: form.password }),
        role: form.role as 'manager' | 'user',
      };

      await updateUserMutation.mutateAsync({ userId, data: userData });
      
      // Navigate back to users list
      navigate({ to: '/users/list' });
    } catch (error) {
      console.error('Error updating user:', error);
      // Handle error - you might want to show a toast notification
    }
  };

  const handleCancel = () => {
    navigate({ to: '/users/list' });
  };

  if (isLoading) {
    return (
      <div className="p-6 max-w-8xl mx-auto">
        <DotsLoader />
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="p-6 max-w-8xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle className='text-2xl text-destructive'>Error</CardTitle>
          </CardHeader>
          <div className="p-6">
            <p className="text-muted-foreground mb-4">
              {error ? 'Failed to load user details.' : 'User not found.'}
            </p>
            <Button
              onClick={handleCancel}
              variant="secondary"
            >
              Back to Users List
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-8xl mx-auto">
      <Card>
        <form onSubmit={handleSubmit} className="space-y-6 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold">Edit User</h2>
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
              disabled={updateUserMutation.isPending}
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
              disabled={updateUserMutation.isPending}
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
              disabled={updateUserMutation.isPending}
              className={`${
                errors.email ? 'border-destructive bg-destructive/10' : ''
              }`}
              placeholder="Enter email address"
            />
            {errors.email && <p className="text-sm text-destructive mt-1">{errors.email}</p>}
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm font-medium mb-1">
              New Password 
              <span className="text-muted-foreground font-normal"> (leave blank to keep current password)</span>
            </label>
            <Input
              type="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              disabled={updateUserMutation.isPending}
              className={`${
                errors.password ? 'border-destructive bg-destructive/10' : ''
              }`}
              placeholder="Enter new password (min 6 characters)"
            />
            {errors.password && <p className="text-sm text-destructive mt-1">{errors.password}</p>}
          </div>

          {/* Confirm Password */}
          {form.password && form.password.length > 0 && (
            <div>
              <label className="block text-sm font-medium mb-1">Confirm New Password</label>
              <Input
                type="password"
                name="confirmPassword"
                value={form.confirmPassword}
                onChange={handleChange}
                disabled={updateUserMutation.isPending}
                className={`${
                  errors.confirmPassword ? 'border-destructive bg-destructive/10' : ''
                }`}
                placeholder="Confirm your new password"
              />
              {errors.confirmPassword && <p className="text-sm text-destructive mt-1">{errors.confirmPassword}</p>}
            </div>
          )}

          {/* Role - Shadcn Select with proper value handling */}
          <div>
            <label className="block text-sm font-medium mb-1">Role</label>
            <Select 
              value={form.role || undefined} // Convert empty string to undefined for proper placeholder display
              onValueChange={handleSelectChange}
              disabled={updateUserMutation.isPending}
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

          {/* Error Message */}
          {updateUserMutation.error && (
            <div className="bg-destructive/10 border border-destructive/20 text-destructive px-4 py-3 rounded">
              Error updating user: {updateUserMutation.error.message}
            </div>
          )}

          {/* Submit Button */}
          <div className="flex gap-2">
            <Button
              type="submit"
              disabled={updateUserMutation.isPending}
              className="flex-1"
            >
              {updateUserMutation.isPending ? 'Updating User...' : 'Update User'}
            </Button>
            <Button
              type="button"
              onClick={handleCancel}
              disabled={updateUserMutation.isPending}
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