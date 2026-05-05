import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, Users, SearchCode, Cog, UserCircle2, LayoutDashboard, FolderOpen, FilePlus2, FileText, UserCog, UserPlus, Database, } from 'lucide-react';
import { Badge } from '@/components/atomic/badge';
import { Button } from '@/components/atomic/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/atomic/collapsible';
import { useNavigate, useRouterState } from '@tanstack/react-router';
import { useMyPermissionsQuery } from '@/hooks/use-auth';
import type { AllPermissions } from '@/types/auth';
import { hasAnyPermission } from '@/utils/permissions';
import { DotsLoader } from '../atomic/loader';


interface MenuItem {
  id: string;
  title: string;
  icon: React.ReactNode;
  badge?: {
    text: string;
    variant: 'default' | 'secondary' | 'destructive' | 'outline' | 'success' | 'hot';
  };
  children?: MenuItem[];
  href?: string;
  requiredPermissions?: (keyof AllPermissions)[];
  requireAll?: boolean;
  requiredRoles?: string[];     
  alwaysVisible?: boolean;
}

interface SidebarProps {
  menuItems?: MenuItem[];
  activeItem?: string;
  onItemClick?: (item: MenuItem) => void;
}

const defaultMenuItems: MenuItem[] = [
  {
    id: 'dashboard',
    title: 'Dashboard',
    icon: <LayoutDashboard className="w-4 h-4" />,
    href: '/',
    alwaysVisible: true
  },
  {
    id: 'projects',
    title: 'Projects',
    icon: <FolderOpen className="w-4 h-4" />,
    requiredPermissions: ['view_projects', 'create_project', 'view_findings', 'view_scans'],
    requireAll: false,
    children: [
      { 
        id: 'new-project', 
        title: 'Create Project', 
        icon: <FilePlus2 className="w-4 h-4" />, 
        href: '/project/new',
        requiredPermissions: ['create_project']
      },
      { 
        id: 'project-list', 
        title: 'Project List', 
        icon: <FileText className="w-4 h-4" />, 
        href: '/project/list',
        requiredPermissions: ['view_projects']
      },
      {
        id: 'new-scan',
        title: 'Start Scan',
        icon: <SearchCode className="w-4 h-4" />,
        href: '/scan/start',
        requiredPermissions: ['create_scan']
      },
    ]
  },
  {
    id: 'users',
    title: 'Users',
    icon: <UserCog className="w-4 h-4" />,
    requiredRoles: ['superuser', 'admin', 'manager'], 
    children: [
      { 
        id: 'new-user', 
        title: 'Create User', 
        icon: <UserPlus className="w-4 h-4" />, 
        href: '/users/new',
        requiredRoles: ['superuser', 'admin'],
      },
      { 
        id: 'user-list', 
        title: 'Users List', 
        icon: <Users className="w-4 h-4" />, 
        href: '/users/list',
        requiredRoles: ['superuser', 'admin', 'manager'],
      }
    ]
  },
  {
    id: 'settings',
    title: 'Settings',
    icon: <Cog className="w-4 h-4" />,
    href: '/settings',
    alwaysVisible: true
  },
  {
    id: 'profile',
    title: 'Profile',
    icon: <UserCircle2 className="w-4 h-4" />,
    href: '/profile',
    alwaysVisible: true
  },
];

const badgeVariants = {
  success: 'bg-brand-red hover:bg-brand-red/90 text-white',
  hot: 'bg-brand-red hover:bg-brand-red/90 text-white',
  default: 'bg-primary hover:bg-primary/90 text-white',
  secondary: 'bg-brand-dark hover:bg-brand-dark/90 text-brand-light',
  destructive: 'bg-brand-red hover:bg-brand-red/90 text-white',
  outline: 'border border-brand-light bg-transparent hover:bg-brand-light/10 text-brand-light'
};

// Shared menu item base styles — no translate, clean left-border accent on hover
const menuItemBase = (isActive: boolean, depth: number) => `
  group relative w-full justify-start px-3 py-2 h-auto font-normal text-left
  rounded-md transition-all duration-200 ease-out
  ${depth > 0 ? 'pl-9' : ''}
  ${isActive
    ? 'bg-sidebar-primary text-sidebar-primary-foreground shadow-sm'
    : `text-sidebar-foreground
       hover:bg-sidebar-primary/10
       hover:translate-x-1
       dark:hover:bg-sidebar-primary/15`
  }
`.trim().replace(/\s+/g, ' ');

// Left accent bar shown on hover / active
const AccentBar = ({ isActive }: { isActive: boolean }) => (
  <span
    className={`
      absolute left-0 top-1/2 -translate-y-1/2 w-[3px] rounded-r-full
      transition-all duration-200 ease-out
      ${isActive
        ? 'h-5 bg-sidebar-primary-foreground opacity-80'
        : 'h-0 bg-sidebar-primary opacity-0 group-hover:h-4 group-hover:opacity-60'
      }
    `}
  />
);

export default function Sidebar({ 
  menuItems = defaultMenuItems,
  onItemClick 
}: SidebarProps) {

  const { location } = useRouterState();
  const activeItem = useMemo(() => {
    const allItems = menuItems.flatMap(i => [i, ...(i.children || [])]);
    const found = allItems.find(i => i.href === location.pathname);
    return found?.id || "dashboard";
  }, [location.pathname, menuItems]);

  const [openItems, setOpenItems] = useState<string[]>(['projects']);
  const navigate = useNavigate();
  const { data: userRole, isLoading } = useMyPermissionsQuery();

  const filteredMenuItems = useMemo(() => {
    if (isLoading || !userRole) {
      return menuItems.filter(item => item.alwaysVisible);
    }

    const filterItems = (items: MenuItem[]): MenuItem[] => {
      return items.filter(item => {
        if (item.alwaysVisible) return true;

        if (item.requiredRoles && item.requiredRoles.length > 0) {
          if (!item.requiredRoles.includes(userRole.role)) return false;
        }

        if (!item.requiredPermissions || item.requiredPermissions.length === 0) return true;

        const hasPermission = item.requireAll
          ? item.requiredPermissions.every(p => userRole.permissions[p] === true)
          : hasAnyPermission(userRole.permissions, item.requiredPermissions);

        if (!hasPermission) return false;

        if (item.children) {
          const filteredChildren = filterItems(item.children);
          return filteredChildren.length > 0 || item.href;
        }

        return true;
      }).map(item => ({
        ...item,
        ...(item.children ? { children: filterItems(item.children) } : {})
      }));
    };

    return filterItems(menuItems);
  }, [menuItems, userRole, isLoading]);

  const toggleItem = (itemId: string) => {
    setOpenItems(prev =>
      prev.includes(itemId) ? prev.filter(id => id !== itemId) : [...prev, itemId]
    );
  };

  const handleItemClick = (item: MenuItem) => {
    if (!item.children) {
      onItemClick?.(item);
      if (item.href) navigate({ to: item.href });
    }
  };

  const renderMenuItem = (item: MenuItem, depth = 0) => {
    const isOpen = openItems.includes(item.id);
    const isActive = activeItem === item.id;
    const hasChildren = item.children && item.children.length > 0;

    return (
      <div key={item.id} className="w-full">
        {hasChildren ? (
          <Collapsible open={isOpen} onOpenChange={() => toggleItem(item.id)}>
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className={menuItemBase(isActive, depth)}
                onClick={() => handleItemClick(item)}
              >
                <AccentBar isActive={isActive} />
                <div className="flex items-center gap-2.5 flex-1 min-w-0">
                  {/* Icon wrapper with subtle background on hover/active */}
                  <span className={`
                    flex-shrink-0 flex items-center justify-center w-7 h-7 rounded-md
                    transition-colors duration-200
                    ${isActive
                      ? 'bg-white/10'
                      : 'bg-transparent group-hover:bg-sidebar-primary/10 dark:group-hover:bg-sidebar-primary/20'
                    }
                  `}>
                    {item.icon}
                  </span>
                  <span className="text-sm font-medium tracking-wide truncate">{item.title}</span>
                  {item.badge && (
                    <Badge className={`text-xs px-1.5 py-0 ml-1 ${badgeVariants[item.badge.variant]}`}>
                      {item.badge.text}
                    </Badge>
                  )}
                </div>
                <span className={`
                  flex-shrink-0 ml-auto transition-transform duration-200 ease-out opacity-50
                  ${isOpen ? 'rotate-0' : '-rotate-90'}
                `}>
                  <ChevronDown className="w-3.5 h-3.5" />
                </span>
              </Button>
            </CollapsibleTrigger>

            {/* Subtle left-border rail for child group */}
            <CollapsibleContent className="relative">
              <span className="absolute left-[22px] top-0 bottom-0 w-px bg-sidebar-border opacity-50" />
              <div className="space-y-0.5 py-0.5">
                {item.children?.map(child => renderMenuItem(child, depth + 1))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        ) : (
          <Button
            variant="ghost"
            className={menuItemBase(isActive, depth)}
            onClick={() => handleItemClick(item)}
          >
            <AccentBar isActive={isActive} />
            <div className="flex items-center gap-2.5 flex-1 min-w-0">
              <span className={`
                flex-shrink-0 flex items-center justify-center w-7 h-7 rounded-md
                transition-colors duration-200
                ${isActive
                  ? 'bg-white/10'
                  : 'bg-transparent group-hover:bg-sidebar-primary/10 dark:group-hover:bg-sidebar-primary/20'
                }
              `}>
                {item.icon}
              </span>
              <span className="text-sm font-medium tracking-wide truncate">{item.title}</span>
              {item.badge && (
                <Badge className={`text-xs px-1.5 py-0 ml-auto ${badgeVariants[item.badge.variant]}`}>
                  {item.badge.text}
                </Badge>
              )}
            </div>
          </Button>
        )}
      </div>
    );
  };

  const HeaderContent = () => (
    <div className="p-4 h-16 border-b border-sidebar-border flex items-center gap-2.5">
      <div className="w-8 h-8 flex-shrink-0">
        <img src="/CSlogo.png" alt="Logo" className="w-full h-full object-contain" />
      </div>
      <span className="text-sidebar-foreground font-custom text-base font-semibold tracking-widest uppercase">
        Code Sense
      </span>
    </div>
  );

  if (isLoading) {
    return (
      <div className="w-64 h-screen bg-sidebar flex flex-col">
        <HeaderContent />
        <div className="flex-1 flex items-center justify-center">
          <DotsLoader />
        </div>
      </div>
    );
  }

  return (
    <div className="w-64 h-screen bg-sidebar flex flex-col">
      <HeaderContent />

      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-sidebar-border scrollbar-track-transparent">
        <div className="p-3 pt-4">
          {/* Section label */}
          <p className="text-[10px] uppercase tracking-[0.12em] text-sidebar-foreground/40 font-semibold mb-2 px-2">
            Navigation
          </p>

          <nav className="space-y-0.5">
            {filteredMenuItems.length > 0 ? (
              filteredMenuItems.map(item => renderMenuItem(item))
            ) : (
              <p className="text-sidebar-foreground/40 text-sm py-4 px-2">
                No menu items available
              </p>
            )}
          </nav>
        </div>
      </div>
    </div>
  );
}