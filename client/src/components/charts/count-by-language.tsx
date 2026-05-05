import type { LanguageDistributionItem } from '@/types/dashboard';
import { Code } from 'lucide-react';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="
        p-3 rounded-md text-xs font-semibold shadow-md
        bg-white border border-gray-200 text-gray-800
        dark:bg-[#1f1f1f] dark:border-[#3a3a3a] dark:text-white
      ">
        <p className="font-bold text-sm mb-1">{payload[0].payload.language}</p>
        <p style={{ color: '#bf0000' }}>Vulnerabilities: {payload[0].value}</p>
        <p className="text-gray-500 dark:text-gray-400">Scans: {payload[0].payload.scans}</p>
      </div>
    );
  }
  return null;
};

function CountLanguage({ data = [] }: { data?: LanguageDistributionItem[] }) {
  return (
    <div className="
      w-full font-sans rounded-xl
      bg-white border border-gray-100 shadow-sm
      dark:bg-[#2d2d2d] dark:border-[#3a3a3a] dark:shadow-[0_1px_8px_rgba(0,0,0,0.4)]
      transition-colors duration-300
    " style={{ padding: '20px 20px 14px' }}>
      <div style={{ marginBottom: '16px' }}>
        <div className="flex items-center gap-2 font-bold text-sm text-gray-900 dark:text-gray-100 transition-colors duration-300">
          <Code className="w-4 h-4 text-gray-400 dark:text-gray-500" />
          Vulnerabilities by Language
        </div>
        <div className="text-xs mt-0.5 text-gray-400 dark:text-gray-500 transition-colors duration-300">
          Derived from stored scan metrics and findings
        </div>
      </div>

      <div className="
        rounded-lg p-3
        bg-gray-50 border border-gray-100
        dark:bg-[#1f1f1f] dark:border-[#3a3a3a]
        transition-colors duration-300
      ">
        <ResponsiveContainer width="100%" height={250}>
          <BarChart
            data={data}
            margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
            barCategoryGap="35%"
          >
            <XAxis
              dataKey="language"
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
              cursor={{ fill: 'rgba(128,128,128,0.06)' }}
            />
            <Bar dataKey="vulnerabilities" fill="#bf0000" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="border-t border-gray-100 dark:border-[#3a3a3a] mt-3.5 transition-colors duration-300" />

      <div className="flex items-center gap-1.5 mt-2.5 text-xs text-gray-400 dark:text-gray-600 transition-colors duration-300">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        live data from database
      </div>
    </div>
  );
}

export default CountLanguage;
