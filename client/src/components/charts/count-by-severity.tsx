import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts';
import type { SeverityData } from '@/types/dashboard';

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const entry = payload[0];
    return (
      <div className="
        p-3 rounded-md text-xs font-semibold shadow-md
        bg-white border border-gray-200 text-gray-800
        dark:bg-[#1f1f1f] dark:border-[#3a3a3a] dark:text-white
      ">
        <p style={{ margin: 0, color: entry.color }}>
          {`${entry.payload.type}: ${entry.value}`}
        </p>
      </div>
    );
  }
  return null;
};

const ChartComponent = ({ data }: { data?: SeverityData }) => {
  const severityData = data ?? { critical: 0, high: 0, medium: 0, low: 0 };
  const chartData = [
    { type: 'Critical', value: severityData.critical },
    { type: 'High',     value: severityData.high },
    { type: 'Medium',   value: severityData.medium },
    { type: 'Low',      value: severityData.low },
  ];

  const colors: Record<string, string> = {
    Critical: '#7e0e0e',
    High:     '#be0707',
    Medium:   '#ffc000',
    Low:      '#04c73b',
  };

  return (
    <div className="
      w-full font-sans rounded-xl
      bg-white border border-gray-100 shadow-sm
      dark:bg-[#2d2d2d] dark:border-[#3a3a3a] dark:shadow-[0_1px_8px_rgba(0,0,0,0.4)]
      transition-colors duration-300
    " style={{ padding: '20px 20px 14px', height: '405px' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <div className="font-bold text-sm text-gray-900 dark:text-gray-100 transition-colors duration-300">
          Severity Counts
        </div>
        <div className="text-xs mt-0.5 text-gray-400 dark:text-gray-500 transition-colors duration-300">
          Live severity counts from findings
        </div>
      </div>

      {/* Inner chart panel */}
      <div className="
        rounded-lg p-3
        bg-gray-50 border border-gray-100
        dark:bg-[#1f1f1f] dark:border-[#3a3a3a]
        transition-colors duration-300
      ">
        <div style={{ height: '250px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 0, right: 16, left: 10, bottom: 0 }}
              barCategoryGap="30%"
            >
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: '#9ca3af' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="type"
                tick={{ fontSize: 12, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
                width={55}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ fill: 'rgba(128,128,128,0.06)' }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={colors[entry.type]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-gray-100 dark:border-[#3a3a3a] mt-3.5 transition-colors duration-300" />

      {/* Footer */}
      <div className="flex items-center gap-1.5 mt-2.5 text-xs text-gray-400 dark:text-gray-600 transition-colors duration-300">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        live data from database
      </div>
    </div>
  );
};

export default ChartComponent;
