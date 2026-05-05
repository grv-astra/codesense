
import { DotsLoader } from '@/components/atomic/loader'
import AnalysisTrend from '@/components/charts/analysis-by-trend'
import DashboardCards from '@/components/charts/cards'
import CountLanguage from '@/components/charts/count-by-language'
import ChartComponent from '@/components/charts/count-by-severity'
import CveidList from '@/components/charts/cveid-list'
import DonutChart from '@/components/charts/donut-chart'
import ScanDistribution from '@/components/charts/scan-distribution'
import ScanProjects from '@/components/charts/scan-projects'
import { Unauthorized } from '@/components/molecule/unauthorized'
import { authService } from '@/lib/auth'
import { generalService } from '@/services/general.service'
import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
 
export const Route = createFileRoute('/_authenticated/')({
  beforeLoad: () => {
    authService.requireAuth();
  },
  component: Index,
})
 
function Index() {
  let { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => generalService.fetchDashboard(),
  });

  if (isLoading) return <DotsLoader />

  if (isError) {
    return <Unauthorized variant='default' />
  }

  return (
    <div className="p-2">
      <div className="h-full w-full overflow-hidden">
        <DashboardCards data={data?.top_counts} />
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
          <AnalysisTrend data={data?.findings_trend} />
           <DonutChart data={data?.system_status}/>
        </div>
        <div className="grid grid-cols-2 gap-4 p-3">
            <CveidList data={data?.top_cwe} />
           <ScanProjects data={data?.scans_by_project} />
        </div>
        
      </div>
     
    </div>
  )
}
 
