import { Button } from '@/components/atomic/button';
import { Input } from '@/components/atomic/input';
import { useAuth } from '@/hooks/use-auth';
import { authService } from '@/lib/auth';
import { useForm } from '@tanstack/react-form';
import { createFileRoute, redirect } from '@tanstack/react-router'
import { AxiosError } from 'axios';
import { Eye, EyeOff, Lock, Mail, User } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

export const Route = createFileRoute('/_auth/login')({
  beforeLoad: () => {
    if (authService.isAuth()) {
      throw redirect({ to: '/' });
    }
  },
  component: RouteComponent,
})

function RouteComponent() {
  const [showPassword, setShowPassword] = useState(false);
  const { login, isLoginLoading, loginError } = useAuth()

  const form = useForm({
    defaultValues: {
      email: '',
      password: '',
    },
    onSubmit: async ({ value }) => {
      login(value);
    },
  });

  useEffect(() => {
    if (loginError) {
      if (loginError instanceof AxiosError && loginError.response) {
        toast("Login Failed", {
          description: loginError.response.data.detail,
        });
      } else {
        toast("Login Failed", {
          description: "An unexpected error occurred",
        });
      }
    }
  }, [loginError, toast]);

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ backgroundColor: '#2D2D2D' }}>

      <div className="flex rounded-2xl shadow-2xl overflow-hidden">

        {/* Logo Side */}
        <div className="flex flex-col items-center justify-between p-10 bg-[#2b2b2b]">
          <img src="/Logofull.png" alt="Logo" className="object-contain w-2xl p-10" />
          <div className='text-xl font-medium'>Intelligent code review, engineered for security and trust.</div>
        </div>

        {/* Login Form Side */}
        <div className="w-full max-w-md text-black bg-white">
          <div className="px-8 py-6 text-center" style={{ backgroundColor: '#E5E5E5' }}>
            <div className="w-20 h-20 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ backgroundColor: '#BF0000' }}>
              <User className="size-10 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-black mb-2">Login</h1>
          </div>

          {/* Form */}
          <form
            className="px-8 py-8 space-y-6"
            onSubmit={(e) => {
              e.preventDefault();
              form.handleSubmit();
            }}
          >
            {/* Email */}
            <form.Field
              name="email"
              validators={{
                onSubmit: ({ value }) => {
                  if (!value) return 'Email is required';
                  if (!/\S+@\S+\.\S+/.test(value)) return 'Email is invalid';
                },
              }}
              children={({ state, handleChange, handleBlur }) => (
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: '#2D2D2D' }}>
                    Email Address
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Mail className="h-5 w-5" style={{ color: '#BF0000' }} />
                    </div>
                    <Input
                      type="email"
                      value={state.value}
                      onChange={(e) => handleChange(e.target.value)}
                      onBlur={handleBlur}
                      className={`w-full pl-10 pr-4 py-3 border-2 rounded-lg focus:outline-none focus:ring-2 transition-all duration-200 ${
                        state.meta.errors.length > 0
                          ? 'border-red-500 focus:border-red-500 focus:ring-red-200'
                          : 'border-gray-300 focus:ring-red-200'
                      }`}
                      placeholder="Enter your email"
                      style={{ backgroundColor: '#FFFFFF' }}
                    />
                  </div>
                  {state.meta.errors[0] && (
                    <p className="text-red-500 text-sm mt-1">{state.meta.errors[0]}</p>
                  )}
                </div>
              )}
            />

            {/* Password */}
            <form.Field
              name="password"
              validators={{
                onSubmit: ({ value }) => {
                  if (!value) return 'Password is required';
                },
              }}
              children={({ state, handleChange, handleBlur }) => (
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: '#2D2D2D' }}>
                    Password
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Lock className="h-5 w-5" style={{ color: '#BF0000' }} />
                    </div>
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      value={state.value}
                      onChange={(e) => handleChange(e.target.value)}
                      onBlur={handleBlur}
                      className={`w-full pl-10 pr-12 py-3 border-2 rounded-lg focus:outline-none focus:ring-2 transition-all duration-200 ${
                        state.meta.errors.length > 0
                          ? 'border-red-500 focus:border-red-500 focus:ring-red-200'
                          : 'border-gray-300 focus:ring-red-200'
                      }`}
                      placeholder="Enter your password"
                      style={{ backgroundColor: '#FFFFFF' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center"
                    >
                      {showPassword ? (
                        <EyeOff className="h-5 w-5 text-gray-400 hover:text-gray-600 transition-colors" />
                      ) : (
                        <Eye className="h-5 w-5 text-gray-400 hover:text-gray-600 transition-colors" />
                      )}
                    </button>
                  </div>
                  {state.meta.errors[0] && (
                    <p className="text-red-500 text-sm mt-1">{state.meta.errors[0]}</p>
                  )}
                </div>
              )}
            />

            {/* Submit */}
            <Button
              type="submit"
              disabled={isLoginLoading}
              className={`w-full py-5 px-4 ${
                isLoginLoading ? 'opacity-70 cursor-not-allowed' : 'hover:shadow-lg active:scale-95'
              }`}
            >
              {isLoginLoading ? (
                <div className="flex items-center justify-center">
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                  Signing in...
                </div>
              ) : (
                'Sign In'
              )}
            </Button>
          </form>
        </div>

      </div>

    </div>
  );
}