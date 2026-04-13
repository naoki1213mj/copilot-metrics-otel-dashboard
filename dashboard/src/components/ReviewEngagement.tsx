import type { UserSummary } from '../types';
import { formatNumber, formatPercent, isTrue, toSafeNumber } from '../utils';

interface ReviewEngagementProps {
  data: UserSummary[];
  compact?: boolean;
  windowDays?: number;
}

interface ReviewMetricCardProps {
  label: string;
  value: string;
  subtext: string;
  tone: 'cloud' | 'review' | 'neutral';
}

interface CoverageMetric {
  label: string;
  days: number;
  totalDays: number;
  tone: 'cloud' | 'review' | 'neutral';
  detail: string;
}

interface TopReviewer {
  user_login: string;
  reviewDays: number;
  activeReviewDays: number;
  passiveReviewDays: number;
  agentDays: number;
  activeDays: number;
  prompts: number;
}

const getActiveReviewDays = (user: UserSummary): number =>
  toSafeNumber(user.used_copilot_code_review_active_days);

const getPassiveReviewDays = (user: UserSummary): number =>
  toSafeNumber(user.used_copilot_code_review_passive_days);

const getCodingAgentDays = (user: UserSummary): number =>
  toSafeNumber(user.used_copilot_coding_agent_days);

const getReviewTouchDays = (user: UserSummary): number =>
  getActiveReviewDays(user) + getPassiveReviewDays(user);

function ReviewMetricCard({ label, value, subtext, tone }: ReviewMetricCardProps) {
  return (
    <article className={`review-card review-card--${tone}`}>
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
      <p className="metric-subtext">{subtext}</p>
    </article>
  );
}

export function ReviewEngagement({
  data,
  compact = false,
  windowDays,
}: ReviewEngagementProps) {
  const hasOfficialFlags = data.some(
    (user) =>
      typeof user.used_copilot_coding_agent === 'boolean' ||
      typeof user.used_copilot_code_review_active === 'boolean' ||
      typeof user.used_copilot_code_review_passive === 'boolean',
  );

  if (!hasOfficialFlags) {
    return (
      <div className="empty-state">
        <strong>Code review engagement flags are not available yet.</strong>
        <p>
          user_summary.json に used_copilot_coding_agent / used_copilot_code_review_active /
          used_copilot_code_review_passive が追加されると、利用者数サマリーを表示します。
        </p>
      </div>
    );
  }

  const hasDayCoverage = data.some(
    (user) =>
      typeof user.used_copilot_coding_agent_days === 'number' ||
      typeof user.used_copilot_code_review_active_days === 'number' ||
      typeof user.used_copilot_code_review_passive_days === 'number',
  );

  const totalUsers = data.length;
  const totalActiveDays = data.reduce((sum, user) => sum + toSafeNumber(user.active_days), 0);
  const codingAgentUsers = data.filter((user) => isTrue(user.used_copilot_coding_agent)).length;
  const activeReviewUsers = data.filter((user) => isTrue(user.used_copilot_code_review_active)).length;
  const passiveReviewUsers = data.filter((user) => isTrue(user.used_copilot_code_review_passive)).length;
  const anyReviewUsers = data.filter(
    (user) => isTrue(user.used_copilot_code_review_active) || isTrue(user.used_copilot_code_review_passive),
  ).length;

  const codingAgentDays = data.reduce((sum, user) => sum + getCodingAgentDays(user), 0);
  const activeReviewDays = data.reduce((sum, user) => sum + getActiveReviewDays(user), 0);
  const passiveReviewDays = data.reduce((sum, user) => sum + getPassiveReviewDays(user), 0);
  const reviewTouchDays = data.reduce((sum, user) => sum + getReviewTouchDays(user), 0);
  const repeatReviewerThreshold = Math.max(7, Math.round((windowDays ?? 28) * 0.2));
  const repeatReviewers = data.filter(
    (user) => getReviewTouchDays(user) >= repeatReviewerThreshold,
  ).length;
  const averageReviewDays = anyReviewUsers > 0 ? reviewTouchDays / anyReviewUsers : 0;

  const topReviewers: TopReviewer[] = [...data]
    .map((user) => ({
      user_login: user.user_login,
      reviewDays: getReviewTouchDays(user),
      activeReviewDays: getActiveReviewDays(user),
      passiveReviewDays: getPassiveReviewDays(user),
      agentDays: getCodingAgentDays(user),
      activeDays: toSafeNumber(user.active_days),
      prompts: toSafeNumber(user.user_initiated_interaction_count),
    }))
    .sort((a, b) => b.reviewDays - a.reviewDays || b.prompts - a.prompts)
    .slice(0, 5);
  const coverageMetrics: CoverageMetric[] = [
    {
      label: 'Coding agent coverage',
      days: codingAgentDays,
      totalDays: totalActiveDays,
      tone: 'cloud',
      detail: `${formatNumber(codingAgentUsers)} / ${formatNumber(totalUsers)} users`,
    },
    {
      label: 'Active review coverage',
      days: activeReviewDays,
      totalDays: totalActiveDays,
      tone: 'review',
      detail: `${formatNumber(activeReviewUsers)} / ${formatNumber(totalUsers)} users`,
    },
    {
      label: 'Passive review coverage',
      days: passiveReviewDays,
      totalDays: totalActiveDays,
      tone: 'neutral',
      detail: `${formatNumber(passiveReviewUsers)} / ${formatNumber(totalUsers)} users`,
    },
  ];

  return (
    <div className="review-layout">
      <div className="review-main">
        <div className="summary-grid review-grid">
          <ReviewMetricCard
            label={hasDayCoverage ? 'Coding agent days' : 'Used Copilot coding agent'}
            value={hasDayCoverage ? formatNumber(codingAgentDays) : formatNumber(codingAgentUsers)}
            subtext={
              hasDayCoverage
                ? `${formatNumber(codingAgentUsers)} / ${formatNumber(totalUsers)} users • ${formatPercent(totalActiveDays > 0 ? (codingAgentDays / totalActiveDays) * 100 : 0, 1)} of active days`
                : `${formatPercent(totalUsers > 0 ? (codingAgentUsers / totalUsers) * 100 : 0, 1)} of ${formatNumber(totalUsers)} users`
            }
            tone="cloud"
          />
          <ReviewMetricCard
            label={hasDayCoverage ? 'Review-active days' : 'Used active code review'}
            value={hasDayCoverage ? formatNumber(activeReviewDays) : formatNumber(activeReviewUsers)}
            subtext={
              hasDayCoverage
                ? `${formatNumber(activeReviewUsers)} / ${formatNumber(totalUsers)} users • ${formatPercent(totalActiveDays > 0 ? (activeReviewDays / totalActiveDays) * 100 : 0, 1)} of active days`
                : `${formatPercent(totalUsers > 0 ? (activeReviewUsers / totalUsers) * 100 : 0, 1)} of ${formatNumber(totalUsers)} users`
            }
            tone="review"
          />
          <ReviewMetricCard
            label={hasDayCoverage ? 'Review-passive days' : 'Used passive code review'}
            value={hasDayCoverage ? formatNumber(passiveReviewDays) : formatNumber(passiveReviewUsers)}
            subtext={
              hasDayCoverage
                ? `${formatNumber(passiveReviewUsers)} / ${formatNumber(totalUsers)} users • ${formatPercent(totalActiveDays > 0 ? (passiveReviewDays / totalActiveDays) * 100 : 0, 1)} of active days`
                : `${formatPercent(totalUsers > 0 ? (passiveReviewUsers / totalUsers) * 100 : 0, 1)} of ${formatNumber(totalUsers)} users`
            }
            tone="review"
          />
          <ReviewMetricCard
            label={hasDayCoverage ? 'Heavy reviewers' : 'Any code review engagement'}
            value={hasDayCoverage ? formatNumber(repeatReviewers) : formatNumber(anyReviewUsers)}
            subtext={
              hasDayCoverage
                ? `${formatNumber(repeatReviewerThreshold)}日以上 review touch のユーザー • 平均 ${formatNumber(Math.round(averageReviewDays))} review days`
                : `${formatPercent(totalUsers > 0 ? (anyReviewUsers / totalUsers) * 100 : 0, 1)} of ${formatNumber(totalUsers)} users`
            }
            tone="neutral"
          />
        </div>

        {hasDayCoverage && (
          <div className="review-depth-panel">
            <div className="slide-heading compact-heading">
              <h3>Engagement depth across active days</h3>
              <p className="section-description">
                公式フラグの reach は横並びでも、day counts にすると review / coding agent の濃淡が見えます。
              </p>
            </div>

            <div className="review-coverage-list">
              {coverageMetrics.map((metric) => {
                const ratio = metric.totalDays > 0 ? (metric.days / metric.totalDays) * 100 : 0;

                return (
                  <div key={metric.label} className="review-coverage-row">
                    <div>
                      <div className="review-coverage-label-row">
                        <span className="metric-label">{metric.label}</span>
                        <strong className="review-coverage-value">{formatNumber(metric.days)} days</strong>
                      </div>
                      <p className="metric-subtext">
                        {metric.detail} • {formatPercent(ratio, 1)} of {formatNumber(metric.totalDays)} active days
                      </p>
                    </div>
                    <div className="review-progress-track" aria-hidden="true">
                      <span
                        className={`review-progress-fill review-progress-fill--${metric.tone}`}
                        style={{ width: `${Math.min(ratio, 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {!compact && topReviewers.length > 0 && (
        <aside className="review-notes">
          <div className="panel-header review-notes-header">
            <div>
              <p className="panel-eyebrow">Top adopters</p>
              <h3>Repeat reviewers</h3>
            </div>
            <span className="status-pill status-pill--review">Review depth</span>
          </div>
          <p className="section-description">
            user-level flags だけだと全員 adoption に見えるため、review day counts が深さの差分を作ります。
          </p>

          <div className="review-ranking-list">
            {topReviewers.map((user, index) => {
              const activeShare = user.activeDays > 0 ? (user.activeReviewDays / user.activeDays) * 100 : 0;
              const passiveShare = user.activeDays > 0 ? (user.passiveReviewDays / user.activeDays) * 100 : 0;
              const reviewShare = user.activeDays > 0 ? (user.reviewDays / user.activeDays) * 100 : 0;

              return (
                <div key={user.user_login} className="review-ranking-item">
                  <div className="review-ranking-header">
                    <div className="review-ranking-user">
                      <span className="review-ranking-rank">#{index + 1}</span>
                      <div className="user-cell">
                        <strong>{user.user_login}</strong>
                        <span className="table-note">
                          {formatNumber(user.prompts)} prompts • Agent {formatNumber(user.agentDays)}d
                        </span>
                      </div>
                    </div>
                    <strong className="review-ranking-value">{formatNumber(user.reviewDays)}d</strong>
                  </div>

                  <div className="review-stacked-track" aria-hidden="true">
                    <span
                      className="review-stacked-fill review-stacked-fill--active"
                      style={{ width: `${Math.min(activeShare, 100)}%` }}
                    />
                    <span
                      className="review-stacked-fill review-stacked-fill--passive"
                      style={{ width: `${Math.min(passiveShare, 100)}%` }}
                    />
                  </div>

                  <p className="table-note">
                    Active {formatNumber(user.activeReviewDays)}d • Passive {formatNumber(user.passiveReviewDays)}d • {formatPercent(reviewShare, 1)} of their active days
                  </p>
                </div>
              );
            })}
          </div>
        </aside>
      )}
    </div>
  );
}
