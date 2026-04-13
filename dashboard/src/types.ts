/** 日次サマリーデータ（Organization レベル） */
export interface DailySummary {
  day: string;
  total_active_users: number;
  user_initiated_interaction_count: number;
  code_generation_activity_count: number;
  code_acceptance_activity_count: number;
  chat_panel_agent_mode: number;
  chat_panel_ask_mode: number;
  chat_panel_edit_mode: number;
  chat_panel_custom_mode: number;
  agent_edit: number;
  monthly_active_agent_users?: number | null;
  copilot_coding_agent_active_users_1d?: number | null;
  copilot_coding_agent_active_users_7d?: number | null;
  copilot_coding_agent_active_users_28d?: number | null;
}

/** ユーザー別集計データ */
export interface UserSummary {
  user_login: string;
  active_days: number;
  user_initiated_interaction_count: number;
  code_generation_activity_count: number;
  code_acceptance_activity_count: number;
  chat_panel_agent_mode: number;
  chat_panel_ask_mode: number;
  chat_panel_edit_mode: number;
  chat_panel_custom_mode: number;
  agent_edit: number;
  used_copilot_coding_agent_days?: number | null;
  used_copilot_code_review_active_days?: number | null;
  used_copilot_code_review_passive_days?: number | null;
  used_copilot_coding_agent?: boolean | null;
  used_copilot_code_review_active?: boolean | null;
  used_copilot_code_review_passive?: boolean | null;
}

/** ユーザー日次データ（user_id は公開しない） */
export interface UserDailySummary {
  day: string;
  user_login: string;
  total_active_users: number;
  user_initiated_interaction_count: number;
  code_generation_activity_count: number;
  code_acceptance_activity_count: number;
  chat_panel_agent_mode: number;
  chat_panel_ask_mode: number;
  chat_panel_edit_mode: number;
  chat_panel_custom_mode: number;
  agent_edit: number;
  used_copilot_coding_agent?: boolean | null;
  used_copilot_code_review_active?: boolean | null;
  used_copilot_code_review_passive?: boolean | null;
}

/** 言語別日次サマリーデータ */
export interface LanguageSummary {
  day: string;
  language: string;
  user_initiated_interaction_count: number;
  code_generation_activity_count: number;
  code_acceptance_activity_count: number;
  activity_score: number;
}
