import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { DailySummary } from '../types';

// Props インターフェース
interface ModeBreakdownProps {
  data: DailySummary[];
}

interface ModeBreakdownDatum {
  day: string;
  agent_ratio: number;
  ask_ratio: number;
  plan_ratio: number;
  custom_ratio: number;
}

// 日付を MM-DD 形式にフォーマットする関数
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

const formatPercentage = (value: number): string =>
  `${value.toLocaleString('ja-JP', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;

// ModeBreakdown コンポーネント
// 公式ダッシュボードの「Requests per chat mode」に準拠: Agent / Ask / Plan / Custom Agent
// API フィールド chat_panel_edit_mode は Plan モードのデータ（フィールド名だけ旧称のまま）
export const ModeBreakdown: React.FC<ModeBreakdownProps> = ({ data }) => {
  const chartData: ModeBreakdownDatum[] = data.map((item) => {
    const total =
      item.chat_panel_agent_mode +
      item.chat_panel_ask_mode +
      item.chat_panel_edit_mode +
      item.chat_panel_custom_mode;

    if (total === 0) {
      return {
        day: item.day,
        agent_ratio: 0,
        ask_ratio: 0,
        plan_ratio: 0,
        custom_ratio: 0,
      };
    }

    return {
      day: item.day,
      agent_ratio: (item.chat_panel_agent_mode / total) * 100,
      ask_ratio: (item.chat_panel_ask_mode / total) * 100,
      plan_ratio: (item.chat_panel_edit_mode / total) * 100,
      custom_ratio: (item.chat_panel_custom_mode / total) * 100,
    };
  });

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="day"
          tickFormatter={formatDate}
          tick={{ fontSize: 12 }}
        />
        <YAxis
          domain={[0, 100]}
          tickFormatter={(value) => `${value}%`}
          label={{ value: '構成比', angle: -90, position: 'insideLeft' }}
          tick={{ fontSize: 12 }}
        />
        <Tooltip
          formatter={(value, name) => [
            typeof value === 'number' ? formatPercentage(value) : String(value ?? ''),
            String(name),
          ]}
          labelFormatter={(label) => `日付: ${formatDate(String(label))}`}
          contentStyle={{
            backgroundColor: '#f9fafb',
            border: '1px solid #e5e7eb',
            borderRadius: '0.375rem',
          }}
          cursor={{ fill: 'rgba(0, 0, 0, 0.1)' }}
        />
        <Legend
          wrapperStyle={{ paddingTop: '20px' }}
          formatter={(value: string) => {
            // ラベルを日本語に変換
            const labelMap: { [key: string]: string } = {
              'Agent': 'Agent',
              'Ask': 'Ask',
              'Plan': 'Plan',
              'Custom Agent': 'Custom Agent',
            };
            return labelMap[value] || value;
          }}
        />
        {/* Agent (Indigo) */}
        <Bar
          dataKey="agent_ratio"
          stackId="mode"
          fill="#6366f1"
          name="Agent"
        />
        {/* Ask (Sky) */}
        <Bar
          dataKey="ask_ratio"
          stackId="mode"
          fill="#0ea5e9"
          name="Ask"
        />
        {/* Plan (Amber) — API フィールドは chat_panel_edit_mode */}
        <Bar
          dataKey="plan_ratio"
          stackId="mode"
          fill="#f59e0b"
          name="Plan"
        />
        {/* Custom Agent (Pink) */}
        <Bar
          dataKey="custom_ratio"
          stackId="mode"
          fill="#ec4899"
          name="Custom Agent"
        />
      </BarChart>
    </ResponsiveContainer>
  );
};


