import React from 'react';
import type { DailySummary } from '../types';

// サマリーカードの Props
interface SummaryCardsProps {
  data: DailySummary[];
}

// カードのスタイル
const styles = {
  container: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '1rem',
  } as React.CSSProperties,
  card: {
    background: '#ffffff',
    borderRadius: '8px',
    padding: '1.2rem',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
    textAlign: 'center' as const,
  },
  value: {
    fontSize: '2rem',
    fontWeight: '700',
    color: '#1a1a2e',
    margin: '0.5rem 0',
  },
  label: {
    fontSize: '0.85rem',
    color: '#666',
  },
  sub: {
    fontSize: '0.75rem',
    color: '#999',
    marginTop: '0.3rem',
  },
};

// 28 日間の KPI サマリーカード
export const SummaryCards: React.FC<SummaryCardsProps> = ({ data }) => {
  if (data.length === 0) return null;

  const days = data.length;

  // DAU 平均
  const avgDau = Math.round(
    data.reduce((sum, d) => sum + d.total_active_users, 0) / days
  );

  // 総プロンプト数
  const totalPrompts = data.reduce(
    (sum, d) => sum + d.user_initiated_interaction_count,
    0
  );

  // 総コード生成数
  const totalCodeGen = data.reduce(
    (sum, d) => sum + d.code_generation_activity_count,
    0
  );

  // 承認率（全期間平均）
  const totalAccepted = data.reduce(
    (sum, d) => sum + d.code_acceptance_activity_count,
    0
  );
  const acceptanceRate =
    totalCodeGen > 0 ? Math.round((totalAccepted / totalCodeGen) * 100) : 0;

  // Agent 採用率（Agent モードを 1 回でも使った日の割合）
  const agentDays = data.filter((d) => d.chat_panel_agent_mode > 0).length;
  const agentAdoption = Math.round((agentDays / days) * 100);

  // Agent によるコード変更量
  const totalAgentEdit = data.reduce((sum, d) => sum + d.agent_edit, 0);

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.label}>平均 DAU</div>
        <div style={styles.value}>{avgDau}</div>
        <div style={styles.sub}>{days} 日間</div>
      </div>
      <div style={styles.card}>
        <div style={styles.label}>総プロンプト数</div>
        <div style={styles.value}>{totalPrompts.toLocaleString()}</div>
        <div style={styles.sub}>1日平均 {Math.round(totalPrompts / days)}</div>
      </div>
      <div style={styles.card}>
        <div style={styles.label}>コード承認率</div>
        <div style={styles.value}>{acceptanceRate}%</div>
        <div style={styles.sub}>
          {totalAccepted.toLocaleString()} / {totalCodeGen.toLocaleString()}
        </div>
      </div>
      <div style={styles.card}>
        <div style={styles.label}>Agent 利用日率</div>
        <div style={styles.value}>{agentAdoption}%</div>
        <div style={styles.sub}>{agentDays} / {days} 日</div>
      </div>
      <div style={styles.card}>
        <div style={styles.label}>Agent コード変更量</div>
        <div style={styles.value}>{totalAgentEdit.toLocaleString()}</div>
        <div style={styles.sub}>行（追加+削除）</div>
      </div>
    </div>
  );
};
