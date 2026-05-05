import { ShieldAlert, ArrowLeft, Home, Lock, AlertTriangle } from 'lucide-react';
import { Button } from '../atomic/button';
import { Card, CardContent, CardHeader } from '../atomic/card';

export const Unauthorized = ({
  title = "Access Denied",
  message = "You don't have permission to access this resource.",
  showBackButton = true,
  showHomeButton = true,
  onBack,
  onHome,
  variant = "default" // "default", "minimal", "card"
}) => {
  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      window.history.back();
    }
  };

  const handleHome = () => {
    if (onHome) {
      onHome();
    } else {
      window.location.href = '/';
    }
  };

  // Minimal variant - just icon and text
  if (variant === "minimal") {
    return (
      <div className="flex items-center gap-2 p-3 rounded-md bg-primary-100 text-primary-700 dark:bg-primary-800 dark:text-primary-200">
        <Lock className="w-4 h-4" />
        <span className="text-sm font-medium">{message}</span>
      </div>
    );
  }

  // Card variant - compact card format
  if (variant === "card") {
    return (
      <Card>
        <CardHeader className="flex items-center gap-3">
          <div className="p-2 rounded-full bg-primary-100">
            <ShieldAlert className="w-5 h-5 text-primary-600" />
          </div>
          <h3 className="font-semibold">{title}</h3>
        </CardHeader>
        <CardContent>
          <p className="text-sm mb-4">{message}</p>
        <div className="flex gap-2">
          {showBackButton && (
            <Button
              onClick={handleBack}
              variant='outline'
            >
              <ArrowLeft className="w-3 h-3" />
              Back
            </Button>
          )}
          {showHomeButton && (
            <Button
              onClick={handleHome}
            >
              <Home className="w-3 h-3" />
              Home
            </Button>
          )}
        </div>
        </CardContent>
        
      </Card>
    );
  }

  // Default variant - full page layout
  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="text-center max-w-md w-full">
        {/* Main Card */}
        <Card className="mb-2">
          {/* Icon */}
          <CardHeader>
            <div className="mx-auto size-16 rounded-full flex items-center justify-center bg-primary-100">
              <ShieldAlert className="size-8 text-primary-600" />
            </div>

            {/* Content */}
            <h1 className="text-2xl font-bold mb-2">
              {title}
            </h1>
          </CardHeader>
          
          <CardContent>
            <p className="mb-6" style={{ color: '#6b7280' }}>
              {message}
            </p>

            {/* Error Code */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium mb-6 bg-secondary text-secondary-foreground">
              <AlertTriangle className="size-4" />
              Error 403 - Forbidden
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              {showBackButton && (
                <Button
                  onClick={handleBack}
                  variant="outline"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Go Back
                </Button>
              )}
              {showHomeButton && (
                <Button
                  onClick={handleHome}
                >
                  <Home className="w-4 h-4" />
                  Go Home
                </Button>
              )}
            </div>
          </CardContent>
          
        </Card>

        {/* Help Text */}
        <div className="text-sm">
          <p>If you believe this is an error, please contact your administrator.</p>
          <p className="mt-1">
            Need help? <a href="/support" className="font-medium hover:underline text-primary-950 dark:text-primary-300">
              Contact Support
            </a>
          </p>
        </div>
      </div>
    </div>
  );
};
