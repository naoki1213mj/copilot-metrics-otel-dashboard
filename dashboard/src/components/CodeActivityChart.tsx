import React from 'react';
import {
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
} from 'recharts';
import type { DailySummary } from '../types';

// Props
interface CodeActivityChartProps {
  data: DailySummary[];
  height?: number;
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
export const CodeActivityChart: React.FC<CodeActivityChartProps> = ({ data, height = 300 }) => {
  const chartData = data.map((row) => ({
    ...row,
    acceptance_rate:
      row.code_generation_activity_count > 0
        ? (row.code_acceptance_activity_count / row.code_generation_activity_count) * 100
        : 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="day"
          tickFormatter={formatDate}
          interval="preserveStartEnd"
          minTickGap={28}
          tick={{ fontSize: 12 }}
        />
        <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
        <YAxis
          yAxisId="right"
          orientation="right"
          domain={[0, 100]}
          tickFormatter={(value) => `${value}%`}
          tick={{ fontSize: 12 }}
        />
        <Tooltip
          formatter={(value, name) => {
            if (typeof value === 'number') {
              if (name === 'acceptance_rate') {
                return `${value.toLocaleString('ja-JP', {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                })}%`;
              }
              return value.toLocaleString('ja-JP');
            }
            return String(value ?? '');
          }}
          labelFormatter={(label) => formatDate(String(label))}
        />
        <Legend wrapperStyle={{ paddingTop: '10px' }} />
        {/* コード生成数 */}
        <Area
          yAxisId="left"
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
          yAxisId="left"
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
          yAxisId="left"
          type="monotone"
          dataKey="agent_edit"
          stroke="#f97316"
          fill="#f97316"
          fillOpacity={0.15}
          strokeWidth={2}
          name="Agent コード変更"
        />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="acceptance_rate"
          stroke="#0f172a"
          strokeWidth={2}
          dot={{ r: 3 }}
          name="承認率"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
};
