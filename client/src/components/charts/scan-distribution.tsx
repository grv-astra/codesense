import type { ScanDistributionItem } from '@/types/dashboard';
import { Package } from 'lucide-react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="
        p-3 rounded-md text-xs font-semibold shadow-md
        bg-white border border-gray-200 text-gray-800
        dark:bg-[#1f1f1f] dark:border-[#3a3a3a] dark:text-white
      ">
        <p className="font-bold text-sm mb-1" style={{ color: payload[0].payload.color }}>
          {payload[0].name}
        </p>
        <p style={{ color: payload[0].payload.color }}>Count: {payload[0].value}</p>
      </div>
    );
  }
  return null;
};

function ScanDistribution({ data = [] }: { data?: ScanDistributionItem[] }) {
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className="
      w-full font-sans rounded-xl
      bg-white border border-gray-100 shadow-sm
      dark:bg-[#2d2d2d] dark:border-[#3a3a3a] dark:shadow-[0_1px_8px_rgba(0,0,0,0.4)]
      transition-colors duration-300
    " style={{ padding: '20px 20px 14px' }}>
      <div style={{ marginBottom: '16px' }}>
        <div className="flex items-center gap-2 font-bold text-sm text-gray-900 dark:text-gray-100 transition-colors duration-300">
          <Package className="w-4 h-4 text-gray-400 dark:text-gray-500" />
          Scan Distribution
        </div>
        <div className="text-xs mt-0.5 text-gray-400 dark:text-gray-500 transition-colors duration-300">
          ZIP uploads vs GitHub scans
        </div>
      </div>

      <div className="
        rounded-lg p-3
        bg-gray-50 border border-gray-100
        dark:bg-[#1f1f1f] dark:border-[#3a3a3a]
        transition-colors duration-300
      ">
        <div style={{ position: 'relative' }}>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={65}
                outerRadius={90}
                dataKey="value"
                strokeWidth={0}
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} cursor={false} />
            </PieChart>
          </ResponsiveContainer>

          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            textAlign: 'center',
            pointerEvents: 'none',
          }}>
            <div className="text-xl font-bold text-gray-900 dark:text-gray-100">{total.toLocaleString()}</div>
            <div className="text-xs text-gray-400 dark:text-gray-500">Total</div>
          </div>
        </div>

        <div className="flex justify-center gap-6 mt-2">
          {data.map((entry) => (
            <div key={entry.name} className="flex items-center gap-1.5">
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: entry.color, flexShrink: 0 }} />
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {entry.name}
              </span>
              <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                {total ? ((entry.value / total) * 100).toFixed(0) : 0}%
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-gray-100 dark:border-[#3a3a3a] mt-3.5 transition-colors duration-300" />

      <div className="flex items-center gap-1.5 mt-2.5 text-xs text-gray-400 dark:text-gray-600 transition-colors duration-300">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        live scan source breakdown
      </div>
    </div>
  );
}

export default ScanDistribution;
