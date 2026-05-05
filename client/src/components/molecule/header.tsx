import { Settings, User, ChevronDown, Menu, Sun, Moon, LogOut, UserCircle } from 'lucide-react';
import { Button } from '@/components/atomic/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/atomic/dropdown-menu';
import { useAuth } from '@/hooks/use-auth';
import { useTheme } from '@/contexts/use-theme';
import { Link } from '@tanstack/react-router';
 
interface HeaderProps {
  onMenuToggle?: () => void;
  notifications?: number;
  onSearch?: (query: string) => void;
  onProfileClick?: () => void;
  onSettingsClick?: () => void;
  onLogout?: () => void;
}

export default function Header({
  onMenuToggle,
  onProfileClick,
  onSettingsClick,
}: HeaderProps) {
  const { isDarkMode, toggleTheme } = useTheme();
  const { logout, user } = useAuth()



  return (
    <header className="h-16 w-full bg-popover border-b flex items-center justify-between px-4 lg:px-6">
      {/* Left Section */}
      <div className="flex items-center gap-4">
        {/* Mobile Menu Toggle */}
        <Button
          variant="ghost"
          size="sm"
          className="lg:hidden text-popover-foreground hover:bg-popover-foreground/10"
          onClick={onMenuToggle}
        >
          <Menu className="w-5 h-5" />
        </Button>

      </div>

      {/* Right Section */}
      <div className="flex items-center gap-2">

        {/* Theme Toggle */}
        <Button
          variant="ghost"
          size="sm"
          className="text-popover-foreground hover:bg-popover-foreground/10"
          onClick={toggleTheme}
        >
          {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </Button>

        {/* User Profile */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="flex items-center gap-2 py-6 text-popover-foreground hover:bg-popover-foreground/10">
              <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
                <User className="w-4 h-4 text-white" />
              </div>
              
              <div className="hidden md:block text-left">
                <p className="text-sm font-medium text-popover-foreground capitalize">{user?.name}</p>
                <p className="text-xs text-popover-foreground/60 capitalize">{user?.role}</p>
              </div>
              <ChevronDown className="w-4 h-4 text-popover-foreground/60" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
                  <User className="w-4 h-4 text-white" />
                </div>
                
                <div className="hidden md:block text-left">
                  <p className="text-sm font-medium text-popover-foreground capitalize">{user?.name}</p>
                  <p className="text-xs text-popover-foreground/60 capitalize">{user?.role}</p>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            
            {/* Profile Link */}
            <DropdownMenuItem className="cursor-pointer p-0">
              <Link 
                to="/profile" 
                className="w-full flex items-center px-2 py-1.5"
                onClick={onProfileClick}
              >
                <UserCircle className="w-4 h-4 mr-2" />
                Profile
              </Link>
            </DropdownMenuItem>
            
            {/* Settings Link */}
            <DropdownMenuItem className="cursor-pointer p-0">
              <Link 
                to="/settings" 
                className="w-full flex items-center px-2 py-1.5"
                onClick={onSettingsClick}
              >
                <Settings className="w-4 h-4 mr-2" />
                Settings
              </Link>
            </DropdownMenuItem>
            
            <DropdownMenuSeparator/>
            <DropdownMenuItem 
              className="text-destructive hover:bg-destructive/10 cursor-pointer"
              onClick={() => logout()}
            >
              <LogOut className="text-destructive w-4 h-4 mr-2" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}