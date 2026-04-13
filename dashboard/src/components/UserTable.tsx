import type { UserSummary } from '../types';
import { formatNumber, formatPercent, isTrue, toSafeNumber } from '../utils';

interface UserTableProps {
  data: UserSummary[];
  compact?: boolean;
  windowDays?: number;
}

interface CapabilityBadge {
  label: string;
  tone: 'cloud' | 'review' | 'neutral';
}

const getCapabilityBadges = (user: UserSummary): CapabilityBadge[] => {
  const badges: CapabilityBadge[] = [];

  if (isTrue(user.used_copilot_coding_agent)) {
    badges.push({ label: 'Coding agent', tone: 'cloud' });
  }

  if (isTrue(user.used_copilot_code_review_active)) {
    badges.push({ label: 'Review active', tone: 'review' });
  }

  if (isTrue(user.used_copilot_code_review_passive)) {
    badges.push({ label: 'Review passive', tone: 'neutral' });
  }

  return badges;
};

const getReviewTouchDays = (user: UserSummary): number =>
  toSafeNumber(user.used_copilot_code_review_active_days) +
  toSafeNumber(user.used_copilot_code_review_passive_days);

export function UserTable({ data, compact = false, windowDays }: UserTableProps) {
  const visibleUsers = compact ? data.slice(0, 6) : data;

  return (
    <div className={`user-table-wrapper${compact ? ' user-table-wrapper--compact' : ''}`}>
      <table className="user-table">
        <thead>
          <tr>
            <th>ユーザー</th>
            <th>アクティブ日数</th>
            <th>プロンプト数</th>
            <th>コード生成</th>
            <th>承認率</th>
            <th>Agent</th>
            <th>Ask</th>
            <th>Plan</th>
            <th>Custom</th>
            <th>Capabilities</th>
          </tr>
        </thead>
        <tbody>
          {visibleUsers.map((user) => {
            const acceptanceRate =
              toSafeNumber(user.code_generation_activity_count) > 0
                ? (toSafeNumber(user.code_acceptance_activity_count) /
                    toSafeNumber(user.code_generation_activity_count)) *
                  100
                : 0;
            const badges = getCapabilityBadges(user);
            const reviewTouchDays = getReviewTouchDays(user);
            const agentDays = toSafeNumber(user.used_copilot_coding_agent_days);
            const engagementNote =
              reviewTouchDays > 0 || agentDays > 0
                ? `Review ${formatNumber(reviewTouchDays)}d • Agent ${formatNumber(agentDays)}d`
                : windowDays
                  ? `${windowDays}日ユーザー集計`
                  : 'API ユーザー集計';

            return (
              <tr key={user.user_login}>
                <td>
                  <div className="user-cell">
                    <strong>{user.user_login}</strong>
                    <span className="table-note">{engagementNote}</span>
                  </div>
                </td>
                <td>{formatNumber(toSafeNumber(user.active_days))}</td>
                <td>{formatNumber(toSafeNumber(user.user_initiated_interaction_count))}</td>
                <td>{formatNumber(toSafeNumber(user.code_generation_activity_count))}</td>
                <td>{formatPercent(acceptanceRate, 1)}</td>
                <td>{formatNumber(toSafeNumber(user.chat_panel_agent_mode))}</td>
                <td>{formatNumber(toSafeNumber(user.chat_panel_ask_mode))}</td>
                <td>{formatNumber(toSafeNumber(user.chat_panel_edit_mode))}</td>
                <td>{formatNumber(toSafeNumber(user.chat_panel_custom_mode))}</td>
                <td>
                  {badges.length > 0 ? (
                    <div className="badge-list">
                      {badges.map((badge) => (
                        <span
                          key={badge.label}
                          className={`status-pill status-pill--${badge.tone}`}
                        >
                          {badge.label}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="table-note">Flags pending</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
