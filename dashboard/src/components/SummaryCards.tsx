import type { DailySummary } from '../types';
import { formatNumber, formatPercent, hasNumber, toSafeNumber } from '../utils';

interface SummaryCardsProps {
  data: DailySummary[];
  variant?: 'all' | 'core' | 'official';
}

interface SummaryCardDefinition {
  label: string;
  value: string;
  subtext: string;
  tone: 'primary' | 'secondary' | 'agent' | 'cloud';
}

export function SummaryCards({ data, variant = 'all' }: SummaryCardsProps) {
  if (data.length === 0) {
    return null;
  }

  const latest = data[data.length - 1];
  const days = data.length;
  const totalPrompts = data.reduce(
    (sum, row) => sum + toSafeNumber(row.user_initiated_interaction_count),
    0,
  );
  const totalCodeGeneration = data.reduce(
    (sum, row) => sum + toSafeNumber(row.code_generation_activity_count),
    0,
  );
  const totalAccepted = data.reduce(
    (sum, row) => sum + toSafeNumber(row.code_acceptance_activity_count),
    0,
  );
  const totalActiveUsers = data.reduce(
    (sum, row) => sum + toSafeNumber(row.total_active_users),
    0,
  );
  const totalAgentMode = data.reduce(
    (sum, row) => sum + toSafeNumber(row.chat_panel_agent_mode),
    0,
  );
  const totalChatRequests = data.reduce(
    (sum, row) =>
      sum +
      toSafeNumber(row.chat_panel_agent_mode) +
      toSafeNumber(row.chat_panel_ask_mode) +
      toSafeNumber(row.chat_panel_edit_mode) +
      toSafeNumber(row.chat_panel_custom_mode),
    0,
  );

  const averageDau = Math.round(totalActiveUsers / days);
  const acceptanceRate =
    totalCodeGeneration > 0 ? (totalAccepted / totalCodeGeneration) * 100 : 0;
  const agentModeShare =
    totalChatRequests > 0 ? (totalAgentMode / totalChatRequests) * 100 : 0;

  const cards: SummaryCardDefinition[] = [
    {
      label: '平均 DAU',
      value: formatNumber(averageDau),
      subtext: `${days}日平均`,
      tone: 'primary',
    },
    {
      label: '総プロンプト数',
      value: formatNumber(totalPrompts),
      subtext: `1日平均 ${formatNumber(Math.round(totalPrompts / days))}`,
      tone: 'secondary',
    },
    {
      label: 'コード承認率',
      value: formatPercent(acceptanceRate, 1),
      subtext: `${formatNumber(totalAccepted)} / ${formatNumber(totalCodeGeneration)}`,
      tone: 'secondary',
    },
    {
      label: 'Agent mode share',
      value: formatPercent(agentModeShare, 1),
      subtext: `${formatNumber(totalAgentMode)} / ${formatNumber(totalChatRequests)} requests`,
      tone: 'agent',
    },
    {
      label: 'Monthly active agent users',
      value: hasNumber(latest.monthly_active_agent_users)
        ? formatNumber(latest.monthly_active_agent_users)
        : '—',
      subtext: hasNumber(latest.monthly_active_agent_users)
        ? `${days}日 window の最新 org-level スナップショット`
        : '新しい daily/org-level フィールド待ち',
      tone: 'agent',
    },
    {
      label: 'Coding agent active users (28d)',
      value: hasNumber(latest.copilot_coding_agent_active_users_28d)
        ? formatNumber(latest.copilot_coding_agent_active_users_28d)
        : '—',
      subtext: hasNumber(latest.copilot_coding_agent_active_users_28d)
        ? `${days}日 window 内の最新 28d アクティブユーザー`
        : '新しい daily/org-level フィールド待ち',
      tone: 'cloud',
    },
  ];

  const visibleCards = cards.filter((_card, index) => {
    if (variant === 'core') {
      return index < 4;
    }

    if (variant === 'official') {
      return index >= 4;
    }

    return true;
  });

  return (
    <div className="summary-grid">
      {visibleCards.map((card) => (
        <article key={card.label} className={`metric-card metric-card--${card.tone}`}>
          <p className="metric-label">{card.label}</p>
          <p className="metric-value">{card.value}</p>
          <p className="metric-subtext">{card.subtext}</p>
        </article>
      ))}
    </div>
  );
}
