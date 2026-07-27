
import { DotsLoader } from '@/components/atomic/loader'
import AnalysisTrend from '@/components/charts/analysis-by-trend'
import DashboardCards from '@/components/charts/cards'
import LicenseStatusCard from '@/components/molecule/license-status-card'
import RecentActivity from '@/components/charts/recent-activity'
import CountLanguage from '@/components/charts/count-by-language'
import ChartComponent from '@/components/charts/count-by-severity'
import CveidList from '@/components/charts/cveid-list'
import DonutChart from '@/components/charts/donut-chart'
import ScanDistribution from '@/components/charts/scan-distribution'
import ScanProjects from '@/components/charts/scan-projects'
import { Unauthorized } from '@/components/molecule/unauthorized'
import { authService } from '@/lib/auth'
import { generalService } from '@/services/general.service'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'

export const Route = createFileRoute('/_authenticated/')({
  beforeLoad: () => {
    authService.requireAuth();
  },
  component: Index,
})

function Index() {
  const [trendDays, setTrendDays] = useState<7 | 30 | 90>(7);
  let { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard', trendDays],
    queryFn: () => generalService.fetchDashboard(trendDays),
    placeholderData: keepPreviousData,
  });

  if (isLoading) return <DotsLoader />

  if (isError) {
    return <Unauthorized variant='default' />
  }

  return (
    <div className="p-2">
      <div className="h-full w-full overflow-hidden">
        <div className="px-3 pt-3">
          <LicenseStatusCard />
        </div>
        <DashboardCards data={data?.top_counts} trend={data?.top_counts_trend} />
        <div className="grid grid-cols-4 gap-4 p-3">
          <div className="col-span-2">
            <ChartComponent data={data?.count_by_severity}/>
          </div>
          <div className="col-span-2">
            <CountLanguage data={data?.language_distribution} />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4 p-3">
           <ScanDistribution data={data?.scan_distribution} />
          <AnalysisTrend data={data?.findings_trend} rangeDays={trendDays} onRangeChange={setTrendDays} />
           <DonutChart data={data?.system_status}/>
        </div>
        <div className="grid grid-cols-3 gap-4 p-3">
            <CveidList data={data?.top_cwe} />
           <ScanProjects data={data?.scans_by_project} />
           <RecentActivity data={data?.recent_scans} />
        </div>
        
      </div>
     
    </div>
  )
}
 
