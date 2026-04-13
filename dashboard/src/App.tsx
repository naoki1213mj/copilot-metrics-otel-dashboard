import { useEffect, useState } from 'react';
import type { DailySummary, UserSummary } from './types';
import { SummaryCards } from './components/SummaryCards';
import { DauChart } from './components/DauChart';
import { CodeActivityChart } from './components/CodeActivityChart';
import { ModeBreakdown } from './components/ModeBreakdown';
import { UserTable } from './components/UserTable';
import './App.css';

function App() {
  const [daily, setDaily] = useState<DailySummary[]>([]);
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // public/data/ 配下の JSON を並列で取得する
    Promise.all([
      fetch('/data/daily_summary.json').then((res) => {
        if (!res.ok) throw new Error(`daily_summary.json: ${res.status}`);
        return res.json() as Promise<DailySummary[]>;
      }),
      fetch('/data/user_summary.json').then((res) => {
        if (!res.ok) throw new Error(`user_summary.json: ${res.status}`);
        return res.json() as Promise<UserSummary[]>;
      }),
    ])
      .then(([dailyData, userData]) => {
        setDaily(dailyData);
        setUsers(userData);
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">エラー: {error}</div>;
  }

  return (
    <div className="app">
      <h1>GitHub Copilot Usage Dashboard</h1>

      <section className="chart-section">
        <SummaryCards data={daily} />
      </section>

      <section className="chart-section">
        <h2>DAU・プロンプト数推移</h2>
        <DauChart data={daily} />
      </section>

      <section className="chart-section">
        <h2>コード生成・承認・Agent 変更量</h2>
        <CodeActivityChart data={daily} />
      </section>

      <section className="chart-section">
        <h2>チャットモード別利用状況（構成比）</h2>
        <ModeBreakdown data={daily} />
      </section>

      <section className="chart-section">
        <h2>ユーザー別サマリー（28 日間）</h2>
        <UserTable data={users} />
      </section>
    </div>
  );
}

export default App;
