import type { StatCountDetails } from '@/types/dashboard';
import { useTrialStatus } from '@/hooks/use-trial';
import { Link } from '@tanstack/react-router';
import { Folder, ScanLine, ScanSearch, Users } from 'lucide-react';
import { Card } from '../atomic/card';

const DashboardCards = ({ data }: { data: StatCountDetails | undefined }) => {
  const { data: trial } = useTrialStatus();
  const hideSbom = trial?.trial_mode === true;

  const allCards = [
    {
      title: 'Users',
      icon: Users,
      count: data?.users ?? 0,
      trend: '+5%',
      trendLabel: 'than last week',
      trendPositive: true,
      href: '/users/list',
      accentColor: '#bf0000',
      gradient: 'from-red-500/30 to-red-600/5'
    },
    {
      title: 'Projects',
      icon: Folder,
      count: data?.projects ?? 0,
      trend: '+3%',
      trendLabel: 'than last month',
      trendPositive: true,
      href: '/project/list',
      accentColor: '#bf0000',
      gradient: 'from-red-500/30 to-red-600/5'
    },
    {
      title: 'Code Scans',
      icon: ScanLine,
      count: data?.scans ?? 0,
      trend: '-2%',
      trendLabel: 'than yesterday',
      trendPositive: false,
      href: '/scan/start',
      accentColor: '#bf0000',
      gradient: 'from-red-500/30 to-red-600/5'
    },
    {
      title: 'SBOM Scans',
      icon: ScanSearch,
      count: data?.sbom_scans ?? 0,
      trend: '+1%',
      trendLabel: 'than last week',
      trendPositive: true,
      href: '/scan/start',
      accentColor: '#bf0000',
      gradient: 'from-red-500/30 to-red-600/5'
    }
  ];

  const cards = hideSbom ? allCards.filter(c => c.title !== 'SBOM Scans') : allCards;

  const formatCount = (count: number) => {
    if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
    return count.toLocaleString();
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 p-3">
      {cards.map((card, index) => {
        const IconComponent = card.icon;

        return (
          <Card
            key={index}
            className="px-4 py-3 group rounded-md border-0 shadow-sm hover:shadow-md transition-shadow duration-200 relative overflow-hidden"
          >
            <Link to={card.href} className="block">
              {/* Gradient background overlay */}
              <div
                className={`absolute inset-0 bg-gradient-to-br ${card.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-300`}
              />

              <div className="relative">
                {/* Top row: label + icon */}
                <div className="flex items-start justify-between">
                  <div className='flex flex-col gap-1'>
                    <span className="text-sm font-medium ">
                      {card.title}
                    </span>
                    {/* Count */}

                    <div className="mb-4">
                      <span
                        className="text-2xl font-bold tracking-tight tabular-nums group-hover:scale-105 transition-transform duration-300 inline-block"
                      >
                        {formatCount(card.count)}
                      </span>
                    </div>
                  </div>

                  {/* Dark icon box — unchanged from new theme */}
                  <div className="p-2 rounded-md bg-red-900 dark:bg-red-800 group-hover:scale-110 transition-all duration-300 shadow-sm">
                    <IconComponent size={24} className="text-white" />
                  </div>

                </div>
                
                {/* Trend */}
                <div className="flex items-center gap-1.5">
                  <span
                    className={`text-xs font-semibold ${
                      card.trendPositive ? 'text-emerald-500' : 'text-red-400'
                    }`}
                  >
                    {card.trend}
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {card.trendLabel}
                  </span>
                </div>
              </div>

              {/* Bottom shine effect */}
              <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-gray-200 dark:via-[#e5e5e5]/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            </Link>
          </Card>
        );
      })}
    </div>
  );
};

export default DashboardCards;