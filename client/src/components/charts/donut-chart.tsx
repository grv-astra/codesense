import type { SystemStatus } from '@/types/dashboard';
import { Clock } from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

const DonutChart = ({ data }: { data?: SystemStatus }) => {

  const counts = data?.counts || {};
  const total = data?.total_scans || 0;

  const chartData = Object.entries(counts).map(([status, value]) => ({
    name: status.charAt(0).toUpperCase() + status.slice(1),
    value,
    color:
      status === 'success'   ? '#8b0000' :
      status === 'completed' ? '#bf0000' :
      status === 'failed'    ? '#ff4444' :
                               '#ff7777'
  }));

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0];
      return (
        <div className="
          p-3 rounded-md text-xs font-semibold shadow-md
          bg-white border border-gray-200 text-gray-800
          dark:bg-[#1f1f1f] dark:border-[#3a3a3a] dark:text-white
        ">
          <div className="flex items-center gap-1.5 font-bold text-sm mb-1">
            <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: dataPoint.payload.color }} />
            {dataPoint.name}
          </div>
          <p style={{ color: dataPoint.payload.color }}>{dataPoint.value} scans</p>
          <p className="text-gray-400 dark:text-gray-500">{((dataPoint.value / total) * 100).toFixed(1)}% of total</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="
      w-full font-sans rounded-xl
      bg-white border border-gray-200 shadow-sm
      dark:bg-[#2d2d2d] dark:border-[#3a3a3a] dark:shadow-[0_1px_8px_rgba(0,0,0,0.4)]
      transition-colors duration-300
    " style={{ padding: '20px 20px 14px' }}>

      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <div className="flex items-center gap-2 font-bold text-base text-gray-900 dark:text-gray-100 transition-colors duration-300">
          <Clock className="w-4 h-4 text-gray-400 dark:text-gray-500" />
          Scan Status
        </div>
        <div className="text-xs mt-0.5 text-green-500 font-medium">
          ({total.toLocaleString()}) total scans recorded.
        </div>
      </div>

      {/* Inner chart panel */}
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
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={65}
                outerRadius={90}
                paddingAngle={5}
                dataKey="value"
                strokeWidth={0}
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} cursor={false} />
            </PieChart>
          </ResponsiveContainer>

          {/* Center label */}
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

        {/* Legend */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 mt-2 px-2">
          {chartData.map((item, index) => (
            <div key={index} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
              <span className="text-xs text-gray-500 dark:text-gray-400">{item.name}</span>
              <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 ml-auto">{item.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-gray-200 dark:border-[#3a3a3a] mt-3.5 transition-colors duration-300" />

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

export default DonutChart;
