import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { LanguageSummary } from '../types';
import { formatDateLabel, formatNumber, formatPercent } from '../utils';

interface LanguageUsageChartProps {
  data: LanguageSummary[];
  height?: number;
}

interface LanguageChartRow {
  day: string;
  [key: string]: string | number;
}

const LANGUAGE_COLORS = [
  '#2563eb',
  '#7c3aed',
  '#0f766e',
  '#ea580c',
  '#e11d48',
  '#0891b2',
  '#475569',
];

const INFRA_AND_SHELL_LANGUAGES = [
  'bicep',
  'hcl',
  'bash',
  'powershell',
  'pwsh',
  'shellscript',
];

export function LanguageUsageChart({
  data,
  height = 320,
}: LanguageUsageChartProps) {
  if (data.length === 0) {
    return (
      <div className="empty-state">
        <strong>Language breakdown is not available yet.</strong>
        <p>
          daily_summary に totals_by_language_feature 由来のデータが入ると、使用言語の推移をそのまま表示します。
        </p>
      </div>
    );
  }

  const totalByLanguage = new Map<string, number>();
  for (const row of data) {
    totalByLanguage.set(
      row.language,
      (totalByLanguage.get(row.language) ?? 0) + row.activity_score,
    );
  }

  const topLanguages = [...totalByLanguage.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([language]) => language);
  const rankedLanguages = [...totalByLanguage.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  const totalActivity = [...totalByLanguage.values()].reduce((sum, value) => sum + value, 0);
  const observedInfraLanguages = INFRA_AND_SHELL_LANGUAGES.filter((language) =>
    totalByLanguage.has(language),
  );

  const groupedByDay = new Map<string, LanguageChartRow>();
  for (const row of data) {
    const dayEntry: LanguageChartRow = groupedByDay.get(row.day) ?? { day: row.day };
    const key = topLanguages.includes(row.language) ? row.language : 'Other';
    dayEntry[key] = Number(dayEntry[key] ?? 0) + row.activity_score;
    groupedByDay.set(row.day, dayEntry);
  }

  const chartData = [...groupedByDay.values()].sort((a, b) =>
    String(a.day).localeCompare(String(b.day)),
  );
  const seriesKeys = [...topLanguages];
  if (chartData.some((row) => Number(row.Other ?? 0) > 0)) {
    seriesKeys.push('Other');
  }

  return (
    <div className="language-chart-layout">
      <div className="stacked-chart-layout">
        {observedInfraLanguages.length > 0 && (
          <div className="legend-chip-row">
            {observedInfraLanguages.map((language) => (
              <div key={language} className="legend-chip">
                {language}
              </div>
            ))}
          </div>
        )}
        <div className="chart-frame" style={{ minHeight: height }}>
          <ResponsiveContainer width="100%" height={height}>
            <AreaChart data={chartData} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
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
                formatter={(value, name) => [
                  typeof value === 'number' ? formatNumber(value) : String(value ?? ''),
                  String(name),
                ]}
                labelFormatter={(label) => formatDateLabel(String(label))}
                contentStyle={{
                  borderRadius: '12px',
                  border: '1px solid #dbe4ff',
                  boxShadow: '0 12px 32px rgba(15, 23, 42, 0.08)',
                }}
              />
              <Legend wrapperStyle={{ paddingTop: '16px' }} />
              {seriesKeys.map((language, index) => (
                <Area
                  key={language}
                  type="monotone"
                  dataKey={language}
                  stackId="language"
                  name={language}
                  stroke={LANGUAGE_COLORS[index % LANGUAGE_COLORS.length]}
                  fill={LANGUAGE_COLORS[index % LANGUAGE_COLORS.length]}
                  fillOpacity={0.18}
                  strokeWidth={2}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <aside className="language-sidebar">
        <div className="language-sidebar-card">
          <div className="panel-header">
            <div>
              <p className="panel-eyebrow">Top mix</p>
              <h3>Top 5 languages</h3>
            </div>
            <span className="status-pill status-pill--agent">Share</span>
          </div>

          <div className="language-ranking-list">
            {rankedLanguages.map(([language, value], index) => {
              const share = totalActivity > 0 ? (value / totalActivity) * 100 : 0;
              return (
                <div key={language} className="language-ranking-item">
                  <div className="language-ranking-header">
                    <div className="review-ranking-user">
                      <span className="review-ranking-rank">#{index + 1}</span>
                      <div className="user-cell">
                        <strong>{language}</strong>
                        <span className="table-note">{formatNumber(value)} activity score</span>
                      </div>
                    </div>
                    <strong className="review-ranking-value">{formatPercent(share, 1)}</strong>
                  </div>
                  <div className="review-progress-track" aria-hidden="true">
                    <span
                      className="review-progress-fill review-progress-fill--cloud"
                      style={{ width: `${Math.min(share, 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </aside>
    </div>
  );
}
