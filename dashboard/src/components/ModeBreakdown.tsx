import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { DailySummary } from '../types';
import { formatDateLabel, formatPercent, toSafeNumber } from '../utils';

interface ModeBreakdownProps {
  data: DailySummary[];
  height?: number;
}

interface ModeBreakdownDatum {
  day: string;
  agent_ratio: number;
  ask_ratio: number;
  plan_ratio: number;
  custom_ratio: number;
}

interface ModeMeta {
  label: string;
  color: string;
}

const MODE_META: ModeMeta[] = [
  { label: 'Agent', color: '#6366f1' },
  { label: 'Ask', color: '#0ea5e9' },
  { label: 'Plan', color: '#f59e0b' },
  { label: 'Custom', color: '#ec4899' },
];

export function ModeBreakdown({ data, height = 320 }: ModeBreakdownProps) {
  const chartData: ModeBreakdownDatum[] = data.map((item) => {
    const total =
      toSafeNumber(item.chat_panel_agent_mode) +
      toSafeNumber(item.chat_panel_ask_mode) +
      toSafeNumber(item.chat_panel_edit_mode) +
      toSafeNumber(item.chat_panel_custom_mode);

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
      agent_ratio: (toSafeNumber(item.chat_panel_agent_mode) / total) * 100,
      ask_ratio: (toSafeNumber(item.chat_panel_ask_mode) / total) * 100,
      plan_ratio: (toSafeNumber(item.chat_panel_edit_mode) / total) * 100,
      custom_ratio: (toSafeNumber(item.chat_panel_custom_mode) / total) * 100,
    };
  });

  return (
    <div className="stacked-chart-layout">
      <div className="legend-chip-row">
        {MODE_META.map((mode) => (
          <div key={mode.label} className="legend-chip">
            <span className="legend-chip-dot" style={{ backgroundColor: mode.color }} />
            {mode.label}
          </div>
        ))}
      </div>
      <div className="chart-frame" style={{ minHeight: height }}>
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={chartData} margin={{ top: 16, right: 24, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="day"
              tickFormatter={formatDateLabel}
              interval="preserveStartEnd"
              minTickGap={28}
              tick={{ fontSize: 12 }}
            />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(value) => `${value}%`}
              tick={{ fontSize: 12 }}
            />
            <Tooltip
              formatter={(value, name) => [
                typeof value === 'number' ? formatPercent(value, 1) : String(value ?? ''),
                String(name),
              ]}
              labelFormatter={(label) => `日付: ${formatDateLabel(String(label))}`}
              contentStyle={{
                borderRadius: '12px',
                border: '1px solid #dbe4ff',
                boxShadow: '0 12px 32px rgba(15, 23, 42, 0.08)',
              }}
              cursor={{ fill: 'rgba(99, 102, 241, 0.08)' }}
            />
            <Bar dataKey="agent_ratio" stackId="mode" fill="#6366f1" name="Agent" />
            <Bar dataKey="ask_ratio" stackId="mode" fill="#0ea5e9" name="Ask" />
            <Bar dataKey="plan_ratio" stackId="mode" fill="#f59e0b" name="Plan" />
            <Bar dataKey="custom_ratio" stackId="mode" fill="#ec4899" name="Custom" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
