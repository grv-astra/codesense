import type { FindingsTrendItem } from '@/types/dashboard';
import { XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="
        p-3 rounded-md text-xs font-semibold shadow-md
        bg-white border border-gray-200 text-gray-800
        dark:bg-[#1f1f1f] dark:border-[#3a3a3a] dark:text-white
      ">
        <p className="font-bold text-sm mb-1 text-gray-600 dark:text-gray-400">{label}</p>
        {payload.map((entry: any) => (
          <p key={entry.dataKey} style={{ color: entry.color }} className="capitalize">
            {entry.dataKey}: {entry.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

function AnalysisTrend({ data = [] }: { data?: FindingsTrendItem[] }) {
  const severityColors = {
    critical: '#dc2626',
    high: '#ea580c',
    medium: '#f59e0b',
    low: '#3b82f6',
  };

  const latestTotal = data[data.length - 1]?.total ?? 0;

  return (
    <div className="
      w-full font-sans rounded-xl
      bg-white border border-gray-200 shadow-sm
      dark:bg-[#2d2d2d] dark:border-[#3a3a3a] dark:shadow-[0_1px_8px_rgba(0,0,0,0.4)]
      transition-colors duration-300
    " style={{ padding: '20px 20px 14px' }}>
      <div style={{ marginBottom: '16px' }}>
        <div className="font-bold text-base text-gray-900 dark:text-gray-100 transition-colors duration-300">
          Findings Trend Analysis
        </div>
        <div className="text-xs mt-0.5 text-green-500 font-medium">
          ({latestTotal.toLocaleString()}) findings on the latest day shown.
        </div>
      </div>

      <div className="
        rounded-lg p-3
        bg-gray-50 border border-gray-100
        dark:bg-[#1f1f1f] dark:border-[#3a3a3a]
        transition-colors duration-300
      ">
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="colorCritical" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={severityColors.critical} stopOpacity={0.8} />
                <stop offset="95%" stopColor={severityColors.critical} stopOpacity={0.1} />
              </linearGradient>
              <linearGradient id="colorHigh" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={severityColors.high} stopOpacity={0.8} />
                <stop offset="95%" stopColor={severityColors.high} stopOpacity={0.1} />
              </linearGradient>
              <linearGradient id="colorMedium" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={severityColors.medium} stopOpacity={0.8} />
                <stop offset="95%" stopColor={severityColors.medium} stopOpacity={0.1} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ stroke: 'rgba(128,128,128,0.15)', strokeWidth: 1 }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '12px' }}
              formatter={(value) => (
                <span className="text-gray-500 dark:text-gray-400 capitalize">{value}</span>
              )}
            />
            <Area type="monotone" dataKey="critical" stackId="1" stroke={severityColors.critical} fill="url(#colorCritical)" strokeWidth={1.5} />
            <Area type="monotone" dataKey="high" stackId="1" stroke={severityColors.high} fill="url(#colorHigh)" strokeWidth={1.5} />
            <Area type="monotone" dataKey="medium" stackId="1" stroke={severityColors.medium} fill="url(#colorMedium)" strokeWidth={1.5} />
            <Area type="monotone" dataKey="low" stackId="1" stroke={severityColors.low} fill={severityColors.low} fillOpacity={0.2} strokeWidth={1.5} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="border-t border-gray-200 dark:border-[#3a3a3a] mt-3.5 transition-colors duration-300" />

      <div className="flex items-center gap-1.5 mt-2.5 text-xs text-gray-400 dark:text-gray-600 transition-colors duration-300">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        last 7 days from findings collection
      </div>
    </div>
  );
}

export default AnalysisTrend;
