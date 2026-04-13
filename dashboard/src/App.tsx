import { useEffect, useMemo, useState } from 'react';
import type {
  DailySummary,
  LanguageSummary,
  UserDailySummary,
  UserSummary,
} from './types';
import { SummaryCards } from './components/SummaryCards';
import { DauChart } from './components/DauChart';
import { CodeActivityChart } from './components/CodeActivityChart';
import { ModeBreakdown } from './components/ModeBreakdown';
import { UserTable } from './components/UserTable';
import { AgentAdoptionOverview } from './components/AgentAdoptionOverview';
import { CloudAgentActivityChart } from './components/CloudAgentActivityChart';
import { ReviewEngagement } from './components/ReviewEngagement';
import { LanguageUsageChart } from './components/LanguageUsageChart';
import { loadDashboardData } from './dataLoader';
import {
  formatDateLabel,
  formatDateRange,
  formatNumber,
  formatPercent,
  hasNumber,
  toSafeNumber,
} from './utils';
import './App.css';

const RANGE_OPTIONS = [28, 60, 100] as const;
const DEFAULT_WINDOW_DAYS = 60;
const DASHBOARD_SECTIONS = [
  {
    id: 'overview',
    label: 'Overview',
    note: 'Core summary / DAU / language',
  },
  {
    id: 'agent',
    label: 'Agent',
    note: 'Adoption / mode mix / cloud signal',
  },
  {
    id: 'diagnostics',
    label: 'Diagnostics',
    note: 'Code / review / top users',
  },
] as const;

type DashboardSectionId = (typeof DASHBOARD_SECTIONS)[number]['id'];

const getReviewTouchDays = (user: UserSummary): number =>
  toSafeNumber(user.used_copilot_code_review_active_days) +
  toSafeNumber(user.used_copilot_code_review_passive_days);

const compareUsers = (a: UserSummary, b: UserSummary): number =>
  getReviewTouchDays(b) - getReviewTouchDays(a) ||
  toSafeNumber(b.used_copilot_coding_agent_days) -
    toSafeNumber(a.used_copilot_coding_agent_days) ||
  b.user_initiated_interaction_count - a.user_initiated_interaction_count ||
  b.active_days - a.active_days;

const createEmptyUserSummary = (userLogin: string): UserSummary => ({
  user_login: userLogin,
  active_days: 0,
  user_initiated_interaction_count: 0,
  code_generation_activity_count: 0,
  code_acceptance_activity_count: 0,
  chat_panel_agent_mode: 0,
  chat_panel_ask_mode: 0,
  chat_panel_edit_mode: 0,
  chat_panel_custom_mode: 0,
  agent_edit: 0,
  used_copilot_coding_agent_days: 0,
  used_copilot_code_review_active_days: 0,
  used_copilot_code_review_passive_days: 0,
  used_copilot_coding_agent: false,
  used_copilot_code_review_active: false,
  used_copilot_code_review_passive: false,
});

function aggregateUserSummaries(rows: UserDailySummary[]): UserSummary[] {
  const byUser = new Map<string, UserSummary>();

  for (const row of rows) {
    const existing = byUser.get(row.user_login) ?? createEmptyUserSummary(row.user_login);

    existing.active_days += 1;
    existing.user_initiated_interaction_count += toSafeNumber(
      row.user_initiated_interaction_count,
    );
    existing.code_generation_activity_count += toSafeNumber(row.code_generation_activity_count);
    existing.code_acceptance_activity_count += toSafeNumber(row.code_acceptance_activity_count);
    existing.chat_panel_agent_mode += toSafeNumber(row.chat_panel_agent_mode);
    existing.chat_panel_ask_mode += toSafeNumber(row.chat_panel_ask_mode);
    existing.chat_panel_edit_mode += toSafeNumber(row.chat_panel_edit_mode);
    existing.chat_panel_custom_mode += toSafeNumber(row.chat_panel_custom_mode);
    existing.agent_edit += toSafeNumber(row.agent_edit);

    if (row.used_copilot_coding_agent) {
      existing.used_copilot_coding_agent = true;
      existing.used_copilot_coding_agent_days =
        toSafeNumber(existing.used_copilot_coding_agent_days) + 1;
    }
    if (row.used_copilot_code_review_active) {
      existing.used_copilot_code_review_active = true;
      existing.used_copilot_code_review_active_days =
        toSafeNumber(existing.used_copilot_code_review_active_days) + 1;
    }
    if (row.used_copilot_code_review_passive) {
      existing.used_copilot_code_review_passive = true;
      existing.used_copilot_code_review_passive_days =
        toSafeNumber(existing.used_copilot_code_review_passive_days) + 1;
    }

    byUser.set(row.user_login, existing);
  }

  return [...byUser.values()].sort(compareUsers);
}

function getAvailableRangeOptions(totalDays: number): number[] {
  const matching = RANGE_OPTIONS.filter((option) => option <= totalDays);
  if (matching.length > 0) {
    return matching;
  }
  return totalDays > 0 ? [totalDays] : [...RANGE_OPTIONS];
}

function resolveDefaultWindow(totalDays: number): number {
  const available = getAvailableRangeOptions(totalDays);
  if (available.includes(DEFAULT_WINDOW_DAYS)) {
    return DEFAULT_WINDOW_DAYS;
  }
  return available[available.length - 1] ?? DEFAULT_WINDOW_DAYS;
}

interface MiniInsightCardProps {
  label: string;
  value: string;
  note: string;
}

function MiniInsightCard({ label, value, note }: MiniInsightCardProps) {
  return (
    <div className="mini-metric-card">
      <span className="mini-metric-label">{label}</span>
      <strong className="mini-metric-value">{value}</strong>
      <span className="mini-metric-note">{note}</span>
    </div>
  );
}

function App() {
  const [daily, setDaily] = useState<DailySummary[]>([]);
  const [languageSummary, setLanguageSummary] = useState<LanguageSummary[]>([]);
  const [userDaily, setUserDaily] = useState<UserDailySummary[]>([]);
  const [selectedWindowDays, setSelectedWindowDays] = useState<number>(DEFAULT_WINDOW_DAYS);
  const [activeSection, setActiveSection] = useState<DashboardSectionId>('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    loadDashboardData()
      .then(({ daily, languageSummary, userDaily }) => {
        if (cancelled) {
          return;
        }

        setDaily(daily);
        setLanguageSummary(languageSummary);
        setUserDaily(userDaily);
        setSelectedWindowDays(resolveDefaultWindow(daily.length));
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }

        const message = err instanceof Error ? err.message : String(err);
        setError(message);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const sortedDaily = useMemo(
    () => [...daily].sort((a, b) => a.day.localeCompare(b.day)),
    [daily],
  );
  const availableRangeOptions = useMemo(
    () => getAvailableRangeOptions(sortedDaily.length),
    [sortedDaily.length],
  );
  const resolvedWindowDays = useMemo(() => {
    if (sortedDaily.length === 0) {
      return DEFAULT_WINDOW_DAYS;
    }

    if (availableRangeOptions.includes(selectedWindowDays)) {
      return selectedWindowDays;
    }

    return resolveDefaultWindow(sortedDaily.length);
  }, [availableRangeOptions, selectedWindowDays, sortedDaily.length]);

  const visibleDaily = useMemo(() => {
    if (sortedDaily.length === 0) {
      return [];
    }

    return sortedDaily.slice(-Math.min(resolvedWindowDays, sortedDaily.length));
  }, [resolvedWindowDays, sortedDaily]);
  const visibleDaySet = useMemo(
    () => new Set(visibleDaily.map((row) => row.day)),
    [visibleDaily],
  );
  const filteredUserDaily = useMemo(
    () => userDaily.filter((row) => visibleDaySet.has(row.day)),
    [userDaily, visibleDaySet],
  );
  const filteredLanguageSummary = useMemo(
    () => languageSummary.filter((row) => visibleDaySet.has(row.day)),
    [languageSummary, visibleDaySet],
  );
  const sortedUsers = useMemo(
    () => aggregateUserSummaries(filteredUserDaily),
    [filteredUserDaily],
  );
  const fullDateRangeLabel =
    sortedDaily.length > 0
      ? formatDateRange(sortedDaily[0].day, sortedDaily[sortedDaily.length - 1].day)
      : '期間未設定';
  const selectedDateRangeLabel =
    visibleDaily.length > 0
      ? formatDateRange(visibleDaily[0].day, visibleDaily[visibleDaily.length - 1].day)
      : '期間未設定';
  const totalWindowLabel =
    sortedDaily.length > 0 ? `${sortedDaily.length}日` : '観測期間';
  const selectedWindowLabel =
    visibleDaily.length > 0 ? `${visibleDaily.length}日` : '観測期間';
  const activeSectionMeta =
    DASHBOARD_SECTIONS.find((section) => section.id === activeSection) ?? DASHBOARD_SECTIONS[0];
  const latestVisibleDaily = visibleDaily[visibleDaily.length - 1];

  const dauInsightCards = useMemo(() => {
    if (visibleDaily.length === 0) {
      return [];
    }

    const totalPrompts = visibleDaily.reduce(
      (sum, row) => sum + toSafeNumber(row.user_initiated_interaction_count),
      0,
    );
    const totalActiveUsers = visibleDaily.reduce(
      (sum, row) => sum + toSafeNumber(row.total_active_users),
      0,
    );
    const peakDauRow = visibleDaily.reduce((maxRow, row) =>
      toSafeNumber(row.total_active_users) > toSafeNumber(maxRow.total_active_users) ? row : maxRow,
    );
    const peakPromptIntensityRow = visibleDaily.reduce((maxRow, row) => {
      const currentRatio =
        toSafeNumber(row.total_active_users) > 0
          ? toSafeNumber(row.user_initiated_interaction_count) / toSafeNumber(row.total_active_users)
          : 0;
      const maxRatio =
        toSafeNumber(maxRow.total_active_users) > 0
          ? toSafeNumber(maxRow.user_initiated_interaction_count) /
            toSafeNumber(maxRow.total_active_users)
          : 0;
      return currentRatio > maxRatio ? row : maxRow;
    });
    const peakPromptIntensity =
      toSafeNumber(peakPromptIntensityRow.total_active_users) > 0
        ? toSafeNumber(peakPromptIntensityRow.user_initiated_interaction_count) /
          toSafeNumber(peakPromptIntensityRow.total_active_users)
        : 0;
    const agentTrafficDays = visibleDaily.filter(
      (row) => toSafeNumber(row.chat_panel_agent_mode) > 0,
    ).length;

    return [
      {
        label: 'Avg prompts / user',
        value:
          totalActiveUsers > 0
            ? formatNumber(Math.round(totalPrompts / totalActiveUsers))
            : '0',
        note: `${selectedWindowLabel} 平均`,
      },
      {
        label: 'Peak DAU',
        value: formatNumber(toSafeNumber(peakDauRow.total_active_users)),
        note: `${formatDateLabel(peakDauRow.day)} に最大`,
      },
      {
        label: 'Peak prompt intensity',
        value: peakPromptIntensity.toLocaleString('ja-JP', {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        }),
        note: `${formatDateLabel(peakPromptIntensityRow.day)} の 1人あたり prompt`,
      },
      {
        label: 'Days with agent traffic',
        value: formatNumber(agentTrafficDays),
        note: `${selectedWindowLabel} の中で Agent mode が動いた日`,
      },
    ];
  }, [selectedWindowLabel, visibleDaily]);

  const codeInsightCards = useMemo(() => {
    if (visibleDaily.length === 0) {
      return [];
    }

    const totalGenerated = visibleDaily.reduce(
      (sum, row) => sum + toSafeNumber(row.code_generation_activity_count),
      0,
    );
    const totalAccepted = visibleDaily.reduce(
      (sum, row) => sum + toSafeNumber(row.code_acceptance_activity_count),
      0,
    );
    const totalAgentEdit = visibleDaily.reduce((sum, row) => sum + toSafeNumber(row.agent_edit), 0);
    const peakGenerationRow = visibleDaily.reduce((maxRow, row) =>
      toSafeNumber(row.code_generation_activity_count) >
      toSafeNumber(maxRow.code_generation_activity_count)
        ? row
        : maxRow,
    );
    const peakAcceptanceRow = visibleDaily.reduce((maxRow, row) =>
      toSafeNumber(row.code_acceptance_activity_count) >
      toSafeNumber(maxRow.code_acceptance_activity_count)
        ? row
        : maxRow,
    );
    const peakAgentEditRow = visibleDaily.reduce((maxRow, row) =>
      toSafeNumber(row.agent_edit) > toSafeNumber(maxRow.agent_edit) ? row : maxRow,
    );
    const acceptanceRate = totalGenerated > 0 ? (totalAccepted / totalGenerated) * 100 : 0;

    return [
      {
        label: 'Accepted blocks',
        value: formatNumber(totalAccepted),
        note: `${formatNumber(totalGenerated)} generated blocks`,
      },
      {
        label: 'Acceptance rate',
        value: formatPercent(acceptanceRate, 1),
        note: `${selectedWindowLabel} 全体`,
      },
      {
        label: 'Agent edit volume',
        value: formatNumber(totalAgentEdit),
        note: `${selectedWindowLabel} 累計`,
      },
      {
        label: 'Peak agent edit day',
        value: formatNumber(toSafeNumber(peakAgentEditRow.agent_edit)),
        note: `${formatDateLabel(peakAgentEditRow.day)} に最大`,
      },
      {
        label: 'Peak generation day',
        value: formatNumber(toSafeNumber(peakGenerationRow.code_generation_activity_count)),
        note: `${formatDateLabel(peakGenerationRow.day)} に最大`,
      },
      {
        label: 'Peak acceptance day',
        value: formatNumber(toSafeNumber(peakAcceptanceRow.code_acceptance_activity_count)),
        note: `${formatDateLabel(peakAcceptanceRow.day)} に最大`,
      },
    ];
  }, [selectedWindowLabel, visibleDaily]);

  const codeMilestoneCards = useMemo(() => {
    if (visibleDaily.length === 0) {
      return [];
    }

    const peakGenerationRow = visibleDaily.reduce((maxRow, row) =>
      toSafeNumber(row.code_generation_activity_count) >
      toSafeNumber(maxRow.code_generation_activity_count)
        ? row
        : maxRow,
    );
    const peakAcceptanceRow = visibleDaily.reduce((maxRow, row) =>
      toSafeNumber(row.code_acceptance_activity_count) >
      toSafeNumber(maxRow.code_acceptance_activity_count)
        ? row
        : maxRow,
    );
    const peakAgentEditRow = visibleDaily.reduce((maxRow, row) =>
      toSafeNumber(row.agent_edit) > toSafeNumber(maxRow.agent_edit) ? row : maxRow,
    );
    const meaningfulAcceptanceRows = visibleDaily.filter(
      (row) => toSafeNumber(row.code_generation_activity_count) >= 80,
    );
    const acceptanceCandidates =
      meaningfulAcceptanceRows.length > 0
        ? meaningfulAcceptanceRows
        : visibleDaily.filter((row) => toSafeNumber(row.code_generation_activity_count) > 0);
    const bestAcceptanceRow =
      acceptanceCandidates.length > 0
        ? acceptanceCandidates.reduce((maxRow, row) => {
            const currentRate =
              toSafeNumber(row.code_generation_activity_count) > 0
                ? toSafeNumber(row.code_acceptance_activity_count) /
                  toSafeNumber(row.code_generation_activity_count)
                : 0;
            const maxRate =
              toSafeNumber(maxRow.code_generation_activity_count) > 0
                ? toSafeNumber(maxRow.code_acceptance_activity_count) /
                  toSafeNumber(maxRow.code_generation_activity_count)
                : 0;
            return currentRate > maxRate ? row : maxRow;
          })
        : peakAcceptanceRow;
    const bestAcceptanceRate =
      toSafeNumber(bestAcceptanceRow.code_generation_activity_count) > 0
        ? (toSafeNumber(bestAcceptanceRow.code_acceptance_activity_count) /
            toSafeNumber(bestAcceptanceRow.code_generation_activity_count)) *
          100
        : 0;

    return [
      {
        label: 'Generation spike',
        value: formatNumber(toSafeNumber(peakGenerationRow.code_generation_activity_count)),
        note: `${formatDateLabel(peakGenerationRow.day)} • 承認 ${formatNumber(
          toSafeNumber(peakGenerationRow.code_acceptance_activity_count),
        )}`,
      },
      {
        label: 'Best efficiency day',
        value: formatPercent(bestAcceptanceRate, 1),
        note: `${formatDateLabel(bestAcceptanceRow.day)} • ${formatNumber(
          toSafeNumber(bestAcceptanceRow.code_acceptance_activity_count),
        )} accepted`,
      },
      {
        label: 'Agent-heavy day',
        value: formatNumber(toSafeNumber(peakAgentEditRow.agent_edit)),
        note: `${formatDateLabel(peakAgentEditRow.day)} • 生成 ${formatNumber(
          toSafeNumber(peakAgentEditRow.code_generation_activity_count),
        )}`,
      },
    ];
  }, [visibleDaily]);

  const reviewSnapshotCards = useMemo(() => {
    return [...sortedUsers]
      .map((user) => {
        const activeReviewDays = toSafeNumber(user.used_copilot_code_review_active_days);
        const passiveReviewDays = toSafeNumber(user.used_copilot_code_review_passive_days);
        const reviewDays = activeReviewDays + passiveReviewDays;
        const activeDays = toSafeNumber(user.active_days);
        const reviewShare = activeDays > 0 ? (reviewDays / activeDays) * 100 : 0;

        return {
          userLogin: user.user_login,
          reviewDays,
          reviewShare,
          prompts: toSafeNumber(user.user_initiated_interaction_count),
          agentDays: toSafeNumber(user.used_copilot_coding_agent_days),
        };
      })
      .filter((user) => user.reviewDays > 0)
      .sort((a, b) => b.reviewDays - a.reviewDays || b.prompts - a.prompts)
      .slice(0, 3)
      .map((user, index) => ({
        label: `#${index + 1} ${user.userLogin}`,
        value: `${formatNumber(user.reviewDays)}d`,
        note: `${formatPercent(user.reviewShare, 1)} of active days • Agent ${formatNumber(
          user.agentDays,
        )}d`,
      }));
  }, [sortedUsers]);

  const officialAgentInsightCards = useMemo(() => {
    if (!latestVisibleDaily) {
      return [];
    }

    const monthlyAgentUsers = hasNumber(latestVisibleDaily.monthly_active_agent_users)
      ? latestVisibleDaily.monthly_active_agent_users
      : null;
    const rolling28d = hasNumber(latestVisibleDaily.copilot_coding_agent_active_users_28d)
      ? latestVisibleDaily.copilot_coding_agent_active_users_28d
      : null;

    return [
      {
        label: 'Latest 1d',
        value: hasNumber(latestVisibleDaily.copilot_coding_agent_active_users_1d)
          ? formatNumber(latestVisibleDaily.copilot_coding_agent_active_users_1d)
          : '—',
        note: '直近日次の cloud agent',
      },
      {
        label: 'Latest 7d',
        value: hasNumber(latestVisibleDaily.copilot_coding_agent_active_users_7d)
          ? formatNumber(latestVisibleDaily.copilot_coding_agent_active_users_7d)
          : '—',
        note: '直近 7 日アクティブ',
      },
      {
        label: 'Latest 28d',
        value: hasNumber(latestVisibleDaily.copilot_coding_agent_active_users_28d)
          ? formatNumber(latestVisibleDaily.copilot_coding_agent_active_users_28d)
          : '—',
        note: '直近 28 日アクティブ',
      },
      {
        label: 'Cloud reach',
        value:
          monthlyAgentUsers && rolling28d
            ? formatPercent((rolling28d / monthlyAgentUsers) * 100, 1)
            : '—',
        note: '28d cloud / monthly agent users',
      },
    ];
  }, [latestVisibleDaily]);

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">エラー: {error}</div>;
  }

  return (
    <div className="app-shell">
      <title>GitHub Copilot Usage Dashboard</title>
      <meta
        name="description"
        content="GitHub Copilot の公式 usage metrics を縦長レイアウトで可視化する React ダッシュボード"
      />

      <main className="app">
        <div className="slide-deck">
          <header className="page-header">
            <div>
              <p className="eyebrow">GitHub Copilot usage metrics</p>
              <h1 id="dashboard-title">GitHub Copilot Usage Dashboard</h1>
              <p className="page-description">
                公式 usage metrics API の daily reports を {totalWindowLabel} 分保持しつつ、
                Overview / Agent / Diagnostics の 3 page をタブ的に切り替えられる構成です。
                記事には必要な page だけを開いてスクショしやすくしています。
              </p>
            </div>

            <div className="page-header-actions">
              <div className="range-toggle" role="tablist" aria-label="表示期間">
                {availableRangeOptions.map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={`range-toggle-button${
                      resolvedWindowDays === option ? ' range-toggle-button--active' : ''
                    }`}
                    onClick={() => setSelectedWindowDays(option)}
                  >
                    {option}日
                  </button>
                ))}
              </div>
              <div className="page-badge" aria-label="集計期間">
                <span className="page-badge-label">Selected window</span>
                <strong>{selectedDateRangeLabel}</strong>
                <span className="page-badge-meta">
                  Viewing: {activeSectionMeta.label} • Full data: {fullDateRangeLabel}
                </span>
              </div>
            </div>
          </header>

          <nav className="capture-nav" aria-label="Dashboard sections" role="tablist">
            {DASHBOARD_SECTIONS.map((section) => (
              <button
                key={section.id}
                id={`tab-${section.id}`}
                type="button"
                role="tab"
                aria-selected={activeSection === section.id}
                aria-controls={`panel-${section.id}`}
                className={`capture-nav-item${
                  activeSection === section.id ? ' capture-nav-item--active' : ''
                }`}
                onClick={() => setActiveSection(section.id)}
              >
                <strong>{section.label}</strong>
                <span className="capture-nav-note">{section.note}</span>
              </button>
            ))}
          </nav>

          {activeSection === 'overview' && (
            <section
              id="panel-overview"
              className="dashboard-slide dashboard-slide--hero"
              role="tabpanel"
              aria-labelledby="tab-overview"
            >
              <div className="slide-heading">
                <p className="eyebrow">Overview</p>
                <h2>Overview snapshot</h2>
                <p className="slide-description section-description">
                  選択中の {selectedWindowLabel} window を、summary / DAU / language の 3 面で見られます。
                </p>
              </div>

              <div className="slide-content slide-content--overview">
                <section
                  className="chart-section slide-panel slide-panel--full"
                  aria-labelledby="summary-title"
                >
                  <div className="slide-heading compact-heading">
                    <h2 id="summary-title">Core summary</h2>
                    <p className="section-description">
                      まずは選択中の {selectedWindowLabel} window を見せ、必要に応じて 100 日全体に引き伸ばせる構成にしています。
                    </p>
                  </div>
                  <SummaryCards data={visibleDaily} variant="core" />
                </section>

                <section className="chart-section slide-panel" aria-labelledby="dau-hero-title">
                  <div className="slide-heading compact-heading">
                    <h2 id="dau-hero-title">DAU and prompts trend</h2>
                    <p className="section-description">
                      日次アクティブユーザーと 1人あたり prompt 数の {selectedWindowLabel} 推移です。
                    </p>
                  </div>
                  <DauChart data={visibleDaily} height={280} />
                  <div className="mini-metric-grid">
                    {dauInsightCards.map((card) => (
                      <MiniInsightCard
                        key={card.label}
                        label={card.label}
                        value={card.value}
                        note={card.note}
                      />
                    ))}
                  </div>
                </section>

                <section className="chart-section slide-panel" aria-labelledby="language-title">
                  <div className="slide-heading compact-heading">
                    <h2 id="language-title">Language usage by day</h2>
                    <p className="section-description">
                      `totals_by_language_feature` の raw language 値を日次に展開しています。infra 系は
                      `bicep` / `hcl`、shell 系は `bash` / `powershell` / `pwsh` / `shellscript`
                      のように返る前提で、そのまま表示します。
                    </p>
                  </div>
                  <LanguageUsageChart data={filteredLanguageSummary} height={280} />
                </section>
              </div>
            </section>
          )}

          {activeSection === 'agent' && (
            <section
              id="panel-agent"
              className="dashboard-slide"
              role="tabpanel"
              aria-labelledby="tab-agent"
            >
            <div className="slide-heading slide-heading--with-badge">
              <div>
                <p className="eyebrow">Agent adoption</p>
                <h2 id="agent-slide-title">Agent Adoption Story</h2>
                <p className="slide-description section-description">
                  選択中の {selectedWindowLabel} で mode mix と coding agent の波形を見つつ、28d
                  系の公式フィールドは最新値として読みます。
                </p>
              </div>
            </div>

            <div className="slide-content slide-content--agent">
              <section
                className="chart-section slide-panel slide-panel--agent-metrics"
                aria-labelledby="official-agent-title"
              >
                <div className="slide-heading compact-heading">
                  <h3 id="official-agent-title">Official agent metrics</h3>
                  <p className="section-description">
                    {selectedWindowLabel} の中でも、monthly_active_agent_users と 28d 系公式フィールドを独立カードで先に見せます。
                  </p>
                </div>
                <SummaryCards data={visibleDaily} variant="official" />
                <div className="mini-metric-grid">
                  {officialAgentInsightCards.map((card) => (
                    <MiniInsightCard
                      key={card.label}
                      label={card.label}
                      value={card.value}
                      note={card.note}
                    />
                  ))}
                </div>
              </section>

              <section
                className="chart-section slide-panel slide-panel--agent-overview"
                aria-labelledby="agent-overview-title"
              >
                <h3 id="agent-overview-title">Adoption overview</h3>
                <p className="section-description">
                  IDE 内の Agent 利用シグナルと org-level の cloud-agent 指標を比較します。
                </p>
                <AgentAdoptionOverview data={visibleDaily} />
              </section>

              <section
                className="chart-section slide-panel slide-panel--mode-mix"
                aria-labelledby="mode-mix-title"
              >
                <h3 id="mode-mix-title">Requests per chat mode</h3>
                  <p className="section-description">
                    API の chat_panel_edit_mode は画面上では Plan として表示しています。
                  </p>
                <ModeBreakdown data={visibleDaily} height={220} />
              </section>

              <section
                className="chart-section slide-panel slide-panel--cloud-trend"
                aria-labelledby="cloud-trend-title"
              >
                <h3 id="cloud-trend-title">Copilot coding agent active users</h3>
                  <p className="section-description">
                    {selectedWindowLabel} の各日付に対する、公式 1d / 7d / 28d アクティブユーザーの比較です。
                  </p>
                <CloudAgentActivityChart data={visibleDaily} height={220} />
              </section>
            </div>
          </section>
          )}

          {activeSection === 'diagnostics' && (
            <section
              id="panel-diagnostics"
              className="dashboard-slide"
              role="tabpanel"
              aria-labelledby="tab-diagnostics"
            >
            <div className="slide-heading slide-heading--with-badge">
              <div>
                <p className="eyebrow">Diagnostics</p>
                <h2 id="diagnostics-slide-title">Deeper Diagnostics</h2>
                <p className="slide-description section-description">
                  user-level diagnostics も {selectedWindowLabel} で再集計し、見ている期間ごとに
                  「誰が深く使ったか」を切り替えられます。
                </p>
              </div>
            </div>

            <div className="slide-content slide-content--diagnostics">
              <section
                className="chart-section slide-panel slide-panel--code-trend"
                aria-labelledby="code-trend-title"
              >
                <h3 id="code-trend-title">Code generation and acceptance</h3>
                <p className="section-description">
                  コード生成、承認、Agent edit volume と承認率を重ねています。
                </p>
                <CodeActivityChart data={visibleDaily} height={240} />
                <div className="mini-metric-grid">
                  {codeInsightCards.map((card) => (
                    <MiniInsightCard
                      key={card.label}
                      label={card.label}
                      value={card.value}
                      note={card.note}
                    />
                  ))}
                </div>
              </section>

              <section
                className="chart-section slide-panel slide-panel--review-engagement"
                aria-labelledby="review-engagement-title"
              >
                <h3 id="review-engagement-title">Code review engagement</h3>
                <p className="section-description">
                  公式フラグに加えて day counts も使い、「何人が触れたか」と「何日使われたか」を並べて見せます。
                </p>
                <ReviewEngagement data={sortedUsers} compact windowDays={visibleDaily.length} />
              </section>

              <section
                className="chart-section slide-panel slide-panel--code-milestones"
                aria-labelledby="code-milestones-title"
              >
                <h3 id="code-milestones-title">Code milestones</h3>
                <p className="section-description">
                  volume だけでなく、「どの日にストーリーが動いたか」を 3 点だけ抜き出します。
                </p>
                <div className="mini-metric-grid mini-metric-grid--triple">
                  {codeMilestoneCards.map((card) => (
                    <MiniInsightCard
                      key={card.label}
                      label={card.label}
                      value={card.value}
                      note={card.note}
                    />
                  ))}
                </div>
              </section>

              <section
                className="chart-section slide-panel slide-panel--review-snapshot"
                aria-labelledby="review-snapshot-title"
              >
                <h3 id="review-snapshot-title">Review hotspots</h3>
                <p className="section-description">
                  review day counts が濃いユーザーを残して、engagement panel の読みどころを補強します。
                </p>
                <div className="mini-metric-grid mini-metric-grid--triple">
                  {reviewSnapshotCards.map((card) => (
                    <MiniInsightCard
                      key={card.label}
                      label={card.label}
                      value={card.value}
                      note={card.note}
                    />
                  ))}
                </div>
              </section>

              <section
                className="chart-section slide-panel slide-panel--full"
                aria-labelledby="user-table-title"
              >
                <h3 id="user-table-title">Users summary</h3>
                <p className="section-description">
                  review / agent engagement が深いユーザー順です。スクショでは上位ユーザーだけ見えるよう compact 表示にしています。
                </p>
                <UserTable data={sortedUsers} compact windowDays={visibleDaily.length} />
              </section>
            </div>
          </section>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
