import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { DailySummary } from '../types';

// Props
interface CodeActivityChartProps {
  data: DailySummary[];
}

// 日付を MM-DD 形式にフォーマットする
const formatDate = (dateString: string): string => {
  try {
    const date = new Date(dateString);
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${month}-${day}`;
  } catch {
    return dateString;
  }
};

// コード生成量・承認数・Agent 変更量の推移チャート
export const CodeActivityChart: React.FC<CodeActivityChartProps> = ({ data }) => {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="day"
          tickFormatter={formatDate}
          tick={{ fontSize: 12 }}
        />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip
          formatter={(value) => {
            if (typeof value === 'number') {
              return value.toLocaleString('ja-JP');
            }
            return String(value ?? '');
          }}
          labelFormatter={(label) => formatDate(String(label))}
        />
        <Legend wrapperStyle={{ paddingTop: '10px' }} />
        {/* コード生成数 */}
        <Area
          type="monotone"
          dataKey="code_generation_activity_count"
          stroke="#8b5cf6"
          fill="#8b5cf6"
          fillOpacity={0.15}
          strokeWidth={2}
          name="コード生成"
        />
        {/* 承認数 */}
        <Area
          type="monotone"
          dataKey="code_acceptance_activity_count"
          stroke="#10b981"
          fill="#10b981"
          fillOpacity={0.15}
          strokeWidth={2}
          name="承認"
        />
        {/* Agent によるコード変更 */}
        <Area
          type="monotone"
          dataKey="agent_edit"
          stroke="#f97316"
          fill="#f97316"
          fillOpacity={0.15}
          strokeWidth={2}
          name="Agent コード変更"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
};
