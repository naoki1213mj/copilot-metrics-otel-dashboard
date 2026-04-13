/** 日次サマリーデータ（Organization レベル） */
export interface DailySummary {
  day: string;
  total_active_users: number;
  user_initiated_interaction_count: number;
  code_generation_activity_count: number;
  chat_panel_agent_mode: number;
  chat_panel_ask_mode: number;
  chat_panel_edit_mode: number;
  chat_panel_custom_mode: number;
  agent_edit: number;
}

/** ユーザー別集計データ */
export interface UserSummary {
  user_login: string;
  active_days: number;
  user_initiated_interaction_count: number;
  code_generation_activity_count: number;
  chat_panel_agent_mode: number;
  chat_panel_ask_mode: number;
  chat_panel_edit_mode: number;
  chat_panel_custom_mode: number;
  agent_edit: number;
}
