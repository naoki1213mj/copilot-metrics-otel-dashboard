// ユーザーレベルのサマリーデータを表示するテーブルコンポーネント

import React from 'react';
import type { UserSummary } from '../types';

interface UserTableProps {
  data: UserSummary[];
}

// テーブルのスタイル定義
const tableStyles = {
  container: {
    padding: '16px',
    overflowX: 'auto' as const,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    fontSize: '14px',
  },
  header: {
    backgroundColor: '#f5f5f5',
    fontWeight: '600',
    textAlign: 'left' as const,
    padding: '12px',
    borderBottom: '2px solid #ddd',
  },
  cell: {
    padding: '12px',
    borderBottom: '1px solid #e0e0e0',
  },
  evenRow: {
    backgroundColor: '#fafafa',
  },
  oddRow: {
    backgroundColor: '#ffffff',
  },
};

export const UserTable: React.FC<UserTableProps> = ({ data }) => {
  return (
    <div style={tableStyles.container}>
      <table style={tableStyles.table}>
        <thead>
          <tr style={{ backgroundColor: tableStyles.header.backgroundColor }}>
            <th style={tableStyles.header}>ユーザー</th>
            <th style={tableStyles.header}>アクティブ日数</th>
            <th style={tableStyles.header}>プロンプト数</th>
            <th style={tableStyles.header}>コード生成</th>
            <th style={tableStyles.header}>Agent</th>
            <th style={tableStyles.header}>Ask</th>
            <th style={tableStyles.header}>Edit</th>
            <th style={tableStyles.header}>Custom</th>
          </tr>
        </thead>
        <tbody>
          {data.map((user, index) => (
            <tr
              key={user.user_login}
              style={{
                backgroundColor: index % 2 === 0 ? tableStyles.evenRow.backgroundColor : tableStyles.oddRow.backgroundColor,
              }}
            >
              <td style={tableStyles.cell}>{user.user_login}</td>
              <td style={tableStyles.cell}>{user.active_days.toLocaleString()}</td>
              <td style={tableStyles.cell}>{user.user_initiated_interaction_count.toLocaleString()}</td>
              <td style={tableStyles.cell}>{user.code_generation_activity_count.toLocaleString()}</td>
              <td style={tableStyles.cell}>{user.chat_panel_agent_mode.toLocaleString()}</td>
              <td style={tableStyles.cell}>{user.chat_panel_ask_mode.toLocaleString()}</td>
              <td style={tableStyles.cell}>{user.chat_panel_edit_mode.toLocaleString()}</td>
              <td style={tableStyles.cell}>{user.chat_panel_custom_mode.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
