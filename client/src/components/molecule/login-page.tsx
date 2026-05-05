import { useForm } from '@tanstack/react-form';
import { useState } from 'react';
import { Eye, EyeOff, Mail, Lock, User } from 'lucide-react';
import { useNavigate } from '@tanstack/react-router';
import { useAuth } from '@/context/api-context';

const LoginPage = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  let navigate = useNavigate()
  const { login } = useAuth()

  const form = useForm({
    defaultValues: {
      email: '',
      password: '',
    },
    onSubmit: async ({ value }) => {
      setIsLoading(true);

      try {
        await login(value.email, value.password);
        // Navigate to dashboard or intended page
        navigate({ to: '/' });
      } catch (error) {
        console.error('Authentication error:', error);
        // Error handling is done in the auth context and axios interceptors
      } finally {
        setIsLoading(false);
      }

    },
  });

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ backgroundColor: '#2D2D2D' }}>
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">
          <div className="px-8 pt-8 pb-6 text-center" style={{ backgroundColor: '#E5E5E5' }}>
            <div className="w-20 h-20 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ backgroundColor: '#BF0000' }}>
              <User className="w-10 h-10 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-black mb-2">Welcome Back</h1>
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
                onChange: ({ value }) => {
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
                    <input
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
                      style={{
                        backgroundColor: '#FFFFFF',
                      }}
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
                onChange: ({ value }) => {
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
                    <input
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
                      style={{
                        backgroundColor: '#FFFFFF',
                      }}
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

            {/* Remember Me */}
            <div className="flex items-center justify-between">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-gray-300 focus:ring-2 focus:ring-red-200"
                  style={{ accentColor: '#BF0000' }}
                />
                <span className="ml-2 text-sm" style={{ color: '#2D2D2D' }}>
                  Remember me
                </span>
              </label>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className={`w-full py-3 px-4 rounded-lg font-medium text-white transition-all duration-200 transform hover:scale-105 focus:outline-none focus:ring-4 focus:ring-red-200 ${
                isLoading ? 'opacity-70 cursor-not-allowed' : 'hover:shadow-lg active:scale-95'
              }`}
              style={{ backgroundColor: '#BF0000' }}
            >
              {isLoading ? (
                <div className="flex items-center justify-center">
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                  Signing in...
                </div>
              ) : (
                'Sign In'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
