import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { DailySummary } from '../types';
import { formatDateLabel, formatNumber, hasNumber } from '../utils';

interface CloudAgentActivityChartProps {
  data: DailySummary[];
  height?: number;
}

export function CloudAgentActivityChart({
  data,
  height = 320,
}: CloudAgentActivityChartProps) {
  const hasAnyData = data.some(
    (row) =>
      hasNumber(row.copilot_coding_agent_active_users_1d) ||
      hasNumber(row.copilot_coding_agent_active_users_7d) ||
      hasNumber(row.copilot_coding_agent_active_users_28d),
  );

  if (!hasAnyData) {
    return (
      <div className="empty-state">
        <strong>Copilot coding agent activity data is not available yet.</strong>
        <p>
          daily_summary.json に公式フィールドが追加されると、1d / 7d / 28d の比較チャートをそのまま表示します。
        </p>
      </div>
    );
  }

  const chartData = data.map((row) => ({
    day: row.day,
    active_users_1d: hasNumber(row.copilot_coding_agent_active_users_1d)
      ? row.copilot_coding_agent_active_users_1d
      : null,
    active_users_7d: hasNumber(row.copilot_coding_agent_active_users_7d)
      ? row.copilot_coding_agent_active_users_7d
      : null,
    active_users_28d: hasNumber(row.copilot_coding_agent_active_users_28d)
      ? row.copilot_coding_agent_active_users_28d
      : null,
  }));

  return (
    <div className="chart-frame" style={{ minHeight: height }}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="day"
            tickFormatter={formatDateLabel}
            interval="preserveStartEnd"
            minTickGap={28}
            tick={{ fontSize: 12 }}
          />
          <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
          <Tooltip
            formatter={(value) =>
              typeof value === 'number' ? formatNumber(value) : String(value ?? '')
            }
            labelFormatter={(label) => formatDateLabel(String(label))}
            contentStyle={{
              borderRadius: '12px',
              border: '1px solid #dbe4ff',
              boxShadow: '0 12px 32px rgba(15, 23, 42, 0.08)',
            }}
          />
          <Legend wrapperStyle={{ paddingTop: '16px' }} />
          <Line
            type="monotone"
            dataKey="active_users_1d"
            name="1d active users"
            stroke="#2563eb"
            strokeWidth={2.5}
            dot={{ r: 3 }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="active_users_7d"
            name="7d active users"
            stroke="#7c3aed"
            strokeWidth={2.5}
            dot={{ r: 3 }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="active_users_28d"
            name="28d active users"
            stroke="#0f766e"
            strokeWidth={2.5}
            dot={{ r: 3 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
