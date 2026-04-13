import type { DailySummary } from '../types';
import { formatNumber, formatPercent, hasNumber, toSafeNumber } from '../utils';

interface AgentAdoptionOverviewProps {
  data: DailySummary[];
}

interface AdoptionMetricProps {
  label: string;
  value: string;
  note: string;
}

function AdoptionMetric({ label, value, note }: AdoptionMetricProps) {
  return (
    <div className="mini-metric-card">
      <span className="mini-metric-label">{label}</span>
      <strong className="mini-metric-value">{value}</strong>
      <span className="mini-metric-note">{note}</span>
    </div>
  );
}

export function AgentAdoptionOverview({ data }: AgentAdoptionOverviewProps) {
  if (data.length === 0) {
    return null;
  }

  const latest = data[data.length - 1];
  const totalAgentEdit = data.reduce((sum, row) => sum + toSafeNumber(row.agent_edit), 0);
  const agentDays = data.filter((row) => toSafeNumber(row.chat_panel_agent_mode) > 0).length;
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
  const agentShare = totalChatRequests > 0 ? (totalAgentMode / totalChatRequests) * 100 : 0;
  const hasCloudMetrics =
    hasNumber(latest.copilot_coding_agent_active_users_1d) ||
    hasNumber(latest.copilot_coding_agent_active_users_7d) ||
    hasNumber(latest.copilot_coding_agent_active_users_28d);
  const windowDays = data.length;

  return (
    <div className="panel-grid">
      <article className="insight-panel">
        <div className="panel-header">
          <div>
            <p className="panel-eyebrow">IDE usage</p>
            <h3>Copilot in the IDE</h3>
          </div>
          <span className="status-pill status-pill--agent">Agent mode</span>
        </div>

        <div className="panel-hero-value">
          {hasNumber(latest.monthly_active_agent_users)
            ? formatNumber(latest.monthly_active_agent_users)
            : '—'}
        </div>
        <p className="panel-hero-subtext">
          Monthly active agent users
          {hasNumber(latest.monthly_active_agent_users)
            ? '（最新の公式 org-level 値）'
            : ' は新しい daily_summary データ待ちです'}
        </p>

        <div className="mini-metric-grid">
          <AdoptionMetric
            label="Agent mode share"
            value={formatPercent(agentShare, 1)}
            note={`${windowDays}日チャットリクエスト構成比`}
          />
          <AdoptionMetric
            label="Agent edit volume"
            value={formatNumber(totalAgentEdit)}
            note={`${windowDays}日累計の追加+削除行`}
          />
          <AdoptionMetric
            label="Days with agent traffic"
            value={formatNumber(agentDays)}
            note={`${data.length}日中`}
          />
        </div>
      </article>

      <article className="insight-panel">
        <div className="panel-header">
          <div>
            <p className="panel-eyebrow">Official cloud signal</p>
            <h3>Copilot coding agent</h3>
          </div>
          <span className="status-pill status-pill--cloud">Cloud agent</span>
        </div>

        {hasCloudMetrics ? (
          <div className="mini-metric-grid mini-metric-grid--wide">
            <AdoptionMetric
              label="Active users (1d)"
              value={
                hasNumber(latest.copilot_coding_agent_active_users_1d)
                  ? formatNumber(latest.copilot_coding_agent_active_users_1d)
                  : '—'
              }
              note="最新の公式 1日アクティブ"
            />
            <AdoptionMetric
              label="Active users (7d)"
              value={
                hasNumber(latest.copilot_coding_agent_active_users_7d)
                  ? formatNumber(latest.copilot_coding_agent_active_users_7d)
                  : '—'
              }
              note="最新の公式 7日アクティブ"
            />
            <AdoptionMetric
              label="Active users (28d)"
              value={
                hasNumber(latest.copilot_coding_agent_active_users_28d)
                  ? formatNumber(latest.copilot_coding_agent_active_users_28d)
                  : '—'
              }
              note="最新の公式 28日アクティブ"
            />
          </div>
        ) : (
          <div className="empty-state compact-empty-state">
            <strong>Copilot coding agent の新しい org-level フィールド待ち</strong>
            <p>
              daily_summary.json に copilot_coding_agent_active_users_1d / 7d / 28d が入ると自動で反映されます。
            </p>
          </div>
        )}
      </article>
    </div>
  );
}
