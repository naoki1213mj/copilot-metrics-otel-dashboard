import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { DailySummary } from '../types';

// DauChart のプロパティインターフェース
interface DauChartProps {
  data: DailySummary[];
}

/**
 * DAU（日次アクティブユーザー）チャート
 * 日次のアクティブユーザー数とユーザー初期化インタラクション数を表示する
 */
export const DauChart: React.FC<DauChartProps> = ({ data }) => {
  // XAxis の日付をMM-DD形式でフォーマットする
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

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="day"
          tickFormatter={formatDate}
          tick={{ fontSize: 12 }}
        />
        {/* DAU用のY軸 */}
        <YAxis
          yAxisId="left"
          label={{ value: 'DAU', angle: -90, position: 'insideLeft' }}
          tick={{ fontSize: 12 }}
        />
        {/* プロンプト数用のY軸 */}
        <YAxis
          yAxisId="right"
          orientation="right"
          label={{ value: 'プロンプト数', angle: 90, position: 'insideRight' }}
          tick={{ fontSize: 12 }}
        />
        <Tooltip
          formatter={(value) => {
            if (typeof value === 'number') {
              return value.toLocaleString('ja-JP');
            }
            return String(value ?? '');
          }}
          labelFormatter={(label) => formatDate(String(label))}
        />
        <Legend
          wrapperStyle={{ paddingTop: '20px' }}
          formatter={(value: string) => {
            const labels: Record<string, string> = {
              total_active_users: 'DAU（日次アクティブユーザー）',
              user_initiated_interaction_count: 'プロンプト数',
            };
            return labels[value] || value;
          }}
        />
        {/* DAU ラインチャート */}
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="total_active_users"
          stroke="#2563eb"
          dot={{ fill: '#2563eb', r: 4 }}
          activeDot={{ r: 6 }}
          strokeWidth={2}
          isAnimationActive={true}
        />
        {/* プロンプト数 ラインチャート */}
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="user_initiated_interaction_count"
          stroke="#16a34a"
          dot={{ fill: '#16a34a', r: 4 }}
          activeDot={{ r: 6 }}
          strokeWidth={2}
          isAnimationActive={true}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};
