import { Input } from '@/components/atomic/input';
import { useAuth } from '@/hooks/use-auth';
import { useSetupStatus } from '@/hooks/use-setup';
import { authService } from '@/lib/auth';
import { useForm } from '@tanstack/react-form';
import { createFileRoute, redirect, useNavigate } from '@tanstack/react-router'
import { AxiosError } from 'axios';
import { Eye, EyeOff, Lock, Mail } from 'lucide-react';
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
  const navigate = useNavigate();
  const { data: setupStatus } = useSetupStatus();

  // First-run: if no admin exists yet, send the user to the setup wizard.
  useEffect(() => {
    if (setupStatus?.setup_needed) {
      navigate({ to: '/setup' });
    }
  }, [setupStatus, navigate]);

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
    <div className="min-h-screen flex items-center justify-center bg-[#1c1c1c] p-4">
      <div className="w-full max-w-4xl flex flex-col md:flex-row rounded-2xl shadow-2xl overflow-hidden">

        {/* Brand side */}
        <div className="w-full md:w-1/2 flex flex-col items-center justify-center gap-6 bg-[#242424] px-10 py-14">
          <img src="/Logofull.png" alt="Code Sense" className="w-48 object-contain" />
          <p className="text-center text-[15px] text-gray-300 leading-relaxed max-w-xs">
            Intelligent code review, engineered for security and trust.
          </p>
        </div>

        {/* Form side */}
        <div className="w-full md:w-1/2 bg-white px-8 sm:px-10 py-12 flex flex-col justify-center">
          <div className="mb-8">
            <h1 className="text-[22px] font-semibold text-gray-900">Welcome back</h1>
            <p className="text-[14px] text-gray-500 mt-1">Sign in to continue to Code Sense.</p>
          </div>

          <form
            className="space-y-5"
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
                  <label className="block text-[13px] font-medium text-gray-700 mb-1.5">
                    Email address
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                    <Input
                      type="email"
                      value={state.value}
                      onChange={(e) => handleChange(e.target.value)}
                      onBlur={handleBlur}
                      className={[
                        'pl-10 h-11 text-[14px]',
                        state.meta.errors.length > 0
                          ? 'border-red-500 focus-visible:ring-red-200'
                          : 'focus-visible:ring-[#bf0000]/30',
                      ].join(' ')}
                      placeholder="you@company.com"
                    />
                  </div>
                  {state.meta.errors[0] && (
                    <p className="text-red-600 text-[12px] mt-1.5">{state.meta.errors[0]}</p>
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
                  <label className="block text-[13px] font-medium text-gray-700 mb-1.5">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      value={state.value}
                      onChange={(e) => handleChange(e.target.value)}
                      onBlur={handleBlur}
                      className={[
                        'pl-10 pr-10 h-11 text-[14px]',
                        state.meta.errors.length > 0
                          ? 'border-red-500 focus-visible:ring-red-200'
                          : 'focus-visible:ring-[#bf0000]/30',
                      ].join(' ')}
                      placeholder="Enter your password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex={-1}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                  {state.meta.errors[0] && (
                    <p className="text-red-600 text-[12px] mt-1.5">{state.meta.errors[0]}</p>
                  )}
                </div>
              )}
            />

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoginLoading}
              className={[
                'w-full inline-flex items-center justify-center gap-2 h-11 rounded-lg text-[14px] font-semibold text-white transition-all duration-200',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#bf0000]',
                isLoginLoading
                  ? 'bg-[#bf0000]/70 cursor-wait'
                  : 'bg-[#bf0000] hover:bg-[#a00000] active:scale-[0.98] shadow-sm shadow-red-900/20',
              ].join(' ')}
            >
              {isLoginLoading ? (
                <>
                  <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <circle
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeDasharray="40"
                      strokeDashoffset="15"
                      strokeLinecap="round"
                    />
                  </svg>
                  Signing in…
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>
        </div>

      </div>
    </div>
  );
}
