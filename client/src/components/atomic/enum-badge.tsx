import React from 'react';

// Types
type BadgeSize = 'xs' | 'sm' | 'md' | 'lg';

type Role = 
  | 'superuser'
  | 'admin' 
  | 'user' 
  | 'manager'

type Status = 
  | 'open' 
  | 'close';

type Priority = 
  | 'critical' 
  | 'high' 
  | 'medium' 
  | 'low'
  | 'info';

type SecuritySeverity = 
  | 'critical' 
  | 'high' 
  | 'medium' 
  | 'low'
  | 'info';

type CommonState = 
  | 'completed' 
  | 'failed' 
  | 'in_progress' 
  | 'queued';

type DefaultVariant = 
  | 'neutral' 
  | 'primary' 
  | 'secondary' 
  | 'accent' 
  | 'muted';

// Base Badge Props
interface BaseBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: React.ReactNode;
  size?: BadgeSize;
  className?: string;
}

// Specific Badge Props
interface RoleBadgeProps extends Omit<BaseBadgeProps, 'children'> {
  role: Role | string;
}

interface StatusBadgeProps extends Omit<BaseBadgeProps, 'children'> {
  status: Status | string;
}

interface PriorityBadgeProps extends Omit<BaseBadgeProps, 'children'> {
  priority: Priority | string;
}

interface SecurityBadgeProps extends Omit<BaseBadgeProps, 'children'> {
  severity: SecuritySeverity | string;
}

interface StateBadgeProps extends Omit<BaseBadgeProps, 'children'> {
  state: CommonState | string;
}

interface DefaultBadgeProps extends Omit<BaseBadgeProps, 'children'> {
  value: string;
  variant?: DefaultVariant;
}

// Base Badge Component
const BaseBadge: React.FC<BaseBadgeProps> = ({ 
  children, 
  className = '', 
  size = 'sm',
  ...props 
}) => {
  const sizeClasses: Record<BadgeSize, string> = {
    xs: 'px-1.5 py-0.5 text-xs',
    sm: 'px-2 py-1 text-xs',
    md: 'px-2.5 py-1.5 text-sm',
    lg: 'px-3 py-2 text-sm'
  };

  const baseClasses = 'inline-flex items-center rounded font-medium border';
  const sizeClass = sizeClasses[size];
  
  return (
    <span 
      className={`${baseClasses} ${sizeClass} ${className} capitalize`}
      {...props}
    >
      {children}
    </span>
  );
};

// Role Badge
export const RoleBadge: React.FC<RoleBadgeProps> = ({ role, size, ...props }) => {
  const roleColors: Record<string, string> = {
    superuser: 'bg-amber-100 text-amber-800 border-amber-200',
    admin: 'bg-red-100 text-red-800 border-red-200',
    user: 'bg-blue-100 text-blue-800 border-blue-200',
    manager: 'bg-green-100 text-green-800 border-green-200',
  };

  const colorClass = roleColors[role?.toLowerCase()] || 'bg-gray-100 text-gray-800 border-gray-200';
  
  return (
    <BaseBadge className={`${colorClass} capitalize`} size={size} {...props}>
      {role}
    </BaseBadge>
  );
};

// Status Badge
export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size, ...props }) => {
  const statusColors: Record<string, string> = {
    close: 'bg-green-100 text-green-800 border-green-200',
    open: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    // open: 'bg-gray-100 text-gray-800 border-gray-200',
    // pending: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    // archived: 'bg-slate-100 text-slate-800 border-slate-200',
    // draft: 'bg-orange-100 text-orange-800 border-orange-200',
    // published: 'bg-green-100 text-green-800 border-green-200',
    // rejected: 'bg-red-100 text-red-800 border-red-200',
    // approved: 'bg-green-100 text-green-800 border-green-200',
    // reviewing: 'bg-blue-100 text-blue-800 border-blue-200'
  };

  const colorClass = statusColors[status?.toLowerCase()] || 'bg-gray-100 text-gray-800 border-gray-200';
  
  return (
    <BaseBadge className={`${colorClass} capitalize`} size={size} {...props}>
      {status}
    </BaseBadge>
  );
};

// Priority Badge
export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority, size, ...props }) => {
  const priorityColors: Record<string, string> = {
    critical: 'bg-red-200 text-red-900 border-red-300',
    high: 'bg-red-100 text-red-800 border-red-200',
    medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    low: 'bg-green-100 text-green-800 border-green-200',
    info: 'bg-blue-100 text-blue-800 border-blue-200'
  };

  const colorClass = priorityColors[priority?.toLowerCase()] || 'bg-gray-100 text-gray-800 border-gray-200';
  
  return (
    <BaseBadge className={`${colorClass} capitalize`} size={size} {...props}>
      {priority}
    </BaseBadge>
  );
};

// Security Findings Badge
export const SecurityBadge: React.FC<SecurityBadgeProps> = ({ severity, size, ...props }) => {
  const severityColors: Record<string, string> = {
    critical: 'bg-red-200 text-red-900 border-red-300',
    high: 'bg-red-100 text-red-800 border-red-200',
    medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    low: 'bg-green-100 text-green-800 border-green-200',
    info: 'bg-blue-100 text-blue-800 border-blue-200'
  };

  const colorClass = severityColors[severity?.toLowerCase()] || 'bg-gray-100 text-gray-800 border-gray-200';
  
  return (
    <BaseBadge className={`${colorClass} capitalize`} size={size} {...props}>
      {severity}
    </BaseBadge>
  );
};

// Common State Badge
export const StateBadge: React.FC<StateBadgeProps> = ({ state, size, ...props }) => {
  const stateColors: Record<string, string> = {
    completed: 'bg-green-100 text-green-800 border-green-200',
    failed: 'bg-red-100 text-red-800 border-red-200',
    in_progress: 'bg-blue-100 text-blue-800 border-blue-200',
    queued: 'bg-gray-100 text-gray-800 border-gray-200'
  };

  const colorClass = stateColors[state?.toLowerCase()] || 'bg-gray-100 text-gray-800 border-gray-200';
  
  return (
    <BaseBadge className={`${colorClass} capitalize`} size={size} {...props}>
      {state}
    </BaseBadge>
  );
};

// Default Badge (for custom values)
export const DefaultBadge: React.FC<DefaultBadgeProps> = ({ 
  value, 
  variant = 'neutral', 
  size, 
  ...props 
}) => {
  const variantColors: Record<DefaultVariant, string> = {
    neutral: 'bg-gray-100 text-gray-800 border-gray-200',
    primary: 'bg-blue-100 text-blue-800 border-blue-200',
    secondary: 'bg-purple-100 text-purple-800 border-purple-200',
    accent: 'bg-indigo-100 text-indigo-800 border-indigo-200',
    muted: 'bg-slate-100 text-slate-600 border-slate-200'
  };

  const colorClass = variantColors[variant];
  
  return (
    <BaseBadge className={`${colorClass} capitalize`} size={size} {...props}>
      {value}
    </BaseBadge>
  );
};
