"""モックデータを NDJSON 形式で生成する。

実 API を叩けない環境でもダッシュボードの動作確認ができるように、
Organization レベル・ユーザーレベルの 100 日分 daily report を生成する。
出力先は実データと同じ非公開ディレクトリ data/raw/。
"""

import json
import logging
import random
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

MOCK_ORG_ID = 123456789
RAW_DATA_DIR = Path("data") / "raw"
LEGACY_PUBLIC_RAW_FILES = (
    Path("dashboard") / "public" / "data" / "org_metrics.ndjson",
    Path("dashboard") / "public" / "data" / "user_metrics.ndjson",
    Path("dashboard") / "public" / "data" / "org_metrics.json",
    Path("dashboard") / "public" / "data" / "user_metrics.json",
)
MOCK_USERS = [
    {
        "user_id": 1001,
        "user_login": "alice",
        "persona": "staff-engineer",
        "weekday_activity_probability": 0.95,
        "weekend_activity_probability": 0.35,
        "interaction_range": (18, 28),
        "generation_ratio": (1.15, 1.55),
        "acceptance_ratio": (0.42, 0.66),
        "ask_share": (0.22, 0.38),
        "edit_share": (0.12, 0.22),
        "custom_share": (0.04, 0.10),
        "agent_share": (0.16, 0.32),
        "agent_edit_share": (0.10, 0.18),
        "coding_agent_affinity": 0.95,
        "review_active_affinity": 0.35,
        "review_passive_affinity": 0.55,
    },
    {
        "user_id": 1002,
        "user_login": "bob",
        "persona": "frontend-lead",
        "weekday_activity_probability": 0.86,
        "weekend_activity_probability": 0.24,
        "interaction_range": (16, 24),
        "generation_ratio": (1.00, 1.32),
        "acceptance_ratio": (0.38, 0.62),
        "ask_share": (0.28, 0.42),
        "edit_share": (0.10, 0.18),
        "custom_share": (0.03, 0.08),
        "agent_share": (0.08, 0.18),
        "agent_edit_share": (0.04, 0.10),
        "coding_agent_affinity": 0.38,
        "review_active_affinity": 0.88,
        "review_passive_affinity": 0.98,
    },
    {
        "user_id": 1003,
        "user_login": "charlie",
        "persona": "review-focused",
        "weekday_activity_probability": 0.72,
        "weekend_activity_probability": 0.12,
        "interaction_range": (12, 18),
        "generation_ratio": (0.72, 0.98),
        "acceptance_ratio": (0.45, 0.70),
        "ask_share": (0.30, 0.46),
        "edit_share": (0.08, 0.14),
        "custom_share": (0.02, 0.06),
        "agent_share": (0.00, 0.04),
        "agent_edit_share": (0.00, 0.03),
        "coding_agent_affinity": 0.0,
        "review_active_affinity": 0.52,
        "review_passive_affinity": 0.95,
    },
    {
        "user_id": 1004,
        "user_login": "diana",
        "persona": "automation-champion",
        "weekday_activity_probability": 0.90,
        "weekend_activity_probability": 0.30,
        "interaction_range": (17, 27),
        "generation_ratio": (1.18, 1.62),
        "acceptance_ratio": (0.34, 0.56),
        "ask_share": (0.16, 0.28),
        "edit_share": (0.14, 0.24),
        "custom_share": (0.04, 0.10),
        "agent_share": (0.20, 0.36),
        "agent_edit_share": (0.12, 0.22),
        "coding_agent_affinity": 1.0,
        "review_active_affinity": 0.25,
        "review_passive_affinity": 0.42,
    },
    {
        "user_id": 1005,
        "user_login": "eve",
        "persona": "steady-builder",
        "weekday_activity_probability": 0.79,
        "weekend_activity_probability": 0.20,
        "interaction_range": (13, 20),
        "generation_ratio": (0.95, 1.25),
        "acceptance_ratio": (0.38, 0.62),
        "ask_share": (0.24, 0.38),
        "edit_share": (0.10, 0.18),
        "custom_share": (0.03, 0.08),
        "agent_share": (0.10, 0.20),
        "agent_edit_share": (0.05, 0.11),
        "coding_agent_affinity": 0.58,
        "review_active_affinity": 0.16,
        "review_passive_affinity": 0.34,
    },
    {
        "user_id": 1006,
        "user_login": "frank",
        "persona": "feature-shipper",
        "weekday_activity_probability": 0.71,
        "weekend_activity_probability": 0.12,
        "interaction_range": (11, 18),
        "generation_ratio": (0.86, 1.12),
        "acceptance_ratio": (0.34, 0.58),
        "ask_share": (0.26, 0.40),
        "edit_share": (0.08, 0.14),
        "custom_share": (0.04, 0.10),
        "agent_share": (0.02, 0.08),
        "agent_edit_share": (0.01, 0.04),
        "coding_agent_affinity": 0.18,
        "review_active_affinity": 0.0,
        "review_passive_affinity": 0.45,
    },
    {
        "user_id": 1007,
        "user_login": "grace",
        "persona": "docs-support",
        "weekday_activity_probability": 0.56,
        "weekend_activity_probability": 0.10,
        "interaction_range": (8, 14),
        "generation_ratio": (0.55, 0.82),
        "acceptance_ratio": (0.26, 0.44),
        "ask_share": (0.34, 0.54),
        "edit_share": (0.04, 0.10),
        "custom_share": (0.02, 0.06),
        "agent_share": (0.00, 0.03),
        "agent_edit_share": (0.00, 0.02),
        "coding_agent_affinity": 0.0,
        "review_active_affinity": 0.0,
        "review_passive_affinity": 0.0,
    },
    {
        "user_id": 1008,
        "user_login": "henry",
        "persona": "new-adopter",
        "weekday_activity_probability": 0.49,
        "weekend_activity_probability": 0.07,
        "interaction_range": (7, 13),
        "generation_ratio": (0.62, 0.92),
        "acceptance_ratio": (0.22, 0.40),
        "ask_share": (0.28, 0.46),
        "edit_share": (0.05, 0.11),
        "custom_share": (0.02, 0.06),
        "agent_share": (0.04, 0.12),
        "agent_edit_share": (0.02, 0.05),
        "coding_agent_affinity": 0.28,
        "review_active_affinity": 0.0,
        "review_passive_affinity": 0.22,
    },
    {
        "user_id": 1009,
        "user_login": "iris",
        "persona": "qa-reviewer",
        "weekday_activity_probability": 0.60,
        "weekend_activity_probability": 0.09,
        "interaction_range": (9, 15),
        "generation_ratio": (0.58, 0.88),
        "acceptance_ratio": (0.40, 0.64),
        "ask_share": (0.24, 0.40),
        "edit_share": (0.06, 0.12),
        "custom_share": (0.02, 0.05),
        "agent_share": (0.00, 0.04),
        "agent_edit_share": (0.00, 0.02),
        "coding_agent_affinity": 0.0,
        "review_active_affinity": 0.12,
        "review_passive_affinity": 0.82,
    },
    {
        "user_id": 1010,
        "user_login": "jack",
        "persona": "casual-user",
        "weekday_activity_probability": 0.43,
        "weekend_activity_probability": 0.04,
        "interaction_range": (5, 10),
        "generation_ratio": (0.45, 0.74),
        "acceptance_ratio": (0.18, 0.34),
        "ask_share": (0.26, 0.40),
        "edit_share": (0.03, 0.08),
        "custom_share": (0.00, 0.03),
        "agent_share": (0.00, 0.02),
        "agent_edit_share": (0.00, 0.01),
        "coding_agent_affinity": 0.0,
        "review_active_affinity": 0.0,
        "review_passive_affinity": 0.0,
    },
]
USER_LANGUAGE_PROFILES: dict[str, dict[str, float]] = {
    "alice": {"python": 0.40, "go": 0.22, "hcl": 0.22, "bash": 0.16},
    "bob": {"typescript": 0.56, "css": 0.14, "markdown": 0.16, "json": 0.14},
    "charlie": {"markdown": 0.30, "yaml": 0.28, "shellscript": 0.22, "typescript": 0.20},
    "diana": {"python": 0.32, "bicep": 0.28, "hcl": 0.24, "powershell": 0.16},
    "eve": {"typescript": 0.34, "python": 0.26, "hcl": 0.22, "yaml": 0.18},
    "frank": {"typescript": 0.42, "javascript": 0.28, "bash": 0.18, "markdown": 0.12},
    "grace": {"markdown": 0.42, "yaml": 0.28, "powershell": 0.16, "json": 0.14},
    "henry": {"python": 0.44, "pwsh": 0.24, "yaml": 0.18, "markdown": 0.14},
    "iris": {"yaml": 0.34, "shellscript": 0.24, "hcl": 0.24, "markdown": 0.18},
    "jack": {"markdown": 0.32, "python": 0.28, "bash": 0.20, "json": 0.20},
}
LANGUAGE_PHASE_BOOSTS: dict[str, dict[str, float]] = {
    "baseline": {},
    "onboarding-drive": {"markdown": 1.30, "json": 1.12, "typescript": 1.08},
    "release-hardening": {
        "yaml": 1.28,
        "markdown": 1.20,
        "bash": 1.10,
        "powershell": 1.12,
        "pwsh": 1.12,
        "shellscript": 1.14,
    },
    "agent-rollout": {
        "bicep": 1.40,
        "hcl": 1.30,
        "powershell": 1.18,
        "pwsh": 1.18,
        "shellscript": 1.16,
        "python": 1.08,
    },
    "review-push": {"markdown": 1.30, "yaml": 1.24, "typescript": 1.08},
    "delivery-sprint": {
        "python": 1.18,
        "typescript": 1.18,
        "go": 1.12,
        "hcl": 1.10,
        "bicep": 1.06,
    },
}
AGENTIC_LANGUAGE_FAMILIES = {
    "bicep",
    "hcl",
    "bash",
    "powershell",
    "pwsh",
    "shellscript",
}
CHAT_HEAVY_LANGUAGES = {"markdown", "yaml", "json"}
LANGUAGE_METRIC_FIELDS = (
    "user_initiated_interaction_count",
    "code_generation_activity_count",
    "code_acceptance_activity_count",
)
NUM_DAYS = 100
ROLLING_AGENT_WINDOW_DAYS = 28

FIELD_RANGES: dict[str, tuple[int, int]] = {
    "total_active_users": (3, 8),
    "user_initiated_interaction_count": (30, 200),
    "code_generation_activity_count": (25, 280),
    "code_acceptance_activity_count": (5, 160),
    "chat_panel_agent_mode": (0, 52),
    "chat_panel_ask_mode": (6, 65),
    "chat_panel_edit_mode": (2, 50),
    "chat_panel_custom_mode": (0, 18),
    "agent_edit": (0, 36),
}
ORG_DAILY_ROLLUP_FIELDS = (
    "monthly_active_agent_users",
    "copilot_coding_agent_active_users_1d",
    "copilot_coding_agent_active_users_7d",
    "copilot_coding_agent_active_users_28d",
)
USER_FLAG_FIELDS = (
    "used_copilot_coding_agent",
    "used_copilot_code_review_active",
    "used_copilot_code_review_passive",
)
USER_METRIC_FIELDS = tuple(FIELD_RANGES.keys())


def generate_dates() -> list[date]:
    """過去 100 日分の日付リストを生成する。実 API は 2 日遅れなので today - 2 から遡る。"""
    end = date.today() - timedelta(days=2)
    return [end - timedelta(days=i) for i in range(NUM_DAYS - 1, -1, -1)]


def generate_day_context(
    day: date,
    *,
    day_index: int,
    total_days: int,
) -> dict[str, float | bool | str]:
    """曜日ごとの傾向を持つ 1 日分のコンテキストを生成する。"""
    weekday = day.weekday()
    is_weekend = weekday >= 5
    progress = day_index / max(total_days - 1, 1)
    activity_multiplier = (0.76 if is_weekend else 0.94) * (0.84 + progress * 0.34)
    review_multiplier = (0.58 if is_weekend else 1.02) * (0.88 + progress * 0.26)
    ask_multiplier = 1.02 + (1.0 - progress) * 0.08
    plan_multiplier = 0.90 + progress * 0.28
    phase = "baseline"
    if weekday == 0:
        review_multiplier *= 1.18
    elif weekday == 4:
        review_multiplier *= 1.22
    coding_multiplier = (0.74 if is_weekend else 0.96) * (0.86 + progress * 0.28)
    if weekday in (1, 2, 3):
        coding_multiplier *= 1.12
    agent_multiplier = (0.60 if is_weekend else 0.86) * (0.72 + progress * 0.64)
    custom_multiplier = 0.84 + progress * 0.42
    acceptance_multiplier = 0.98
    if 0.16 <= progress <= 0.24:
        phase = "onboarding-drive"
        activity_multiplier *= 1.08
        ask_multiplier *= 1.14
        acceptance_multiplier *= 0.96
    if 0.40 <= progress <= 0.48:
        phase = "release-hardening"
        activity_multiplier *= 0.92
        coding_multiplier *= 0.88
        review_multiplier *= 1.18
        acceptance_multiplier *= 1.05
    if weekday in (2, 3):
        agent_multiplier *= 1.15
    if progress >= 0.65:
        agent_multiplier *= 1.08
        coding_multiplier *= 1.05
    if progress >= 0.78:
        review_multiplier *= 1.06
        custom_multiplier *= 1.08
        plan_multiplier *= 1.05
    if 0.62 <= progress <= 0.72:
        phase = "agent-rollout"
        activity_multiplier *= 1.08
        agent_multiplier *= 1.28
        custom_multiplier *= 1.14
        plan_multiplier *= 1.10
        acceptance_multiplier *= 0.90
    if 0.78 <= progress <= 0.86:
        phase = "review-push"
        review_multiplier *= 1.22
        plan_multiplier *= 1.12
        ask_multiplier *= 0.96
        acceptance_multiplier *= 1.08
    if progress >= 0.92:
        phase = "delivery-sprint"
        activity_multiplier *= 1.12
        coding_multiplier *= 1.10
        agent_multiplier *= 1.18
        custom_multiplier *= 1.12
        acceptance_multiplier *= 0.93
    if 0.28 <= progress <= 0.42 and random.random() < 0.35:
        activity_multiplier *= 0.90
        coding_multiplier *= 0.94
    if progress >= 0.58 and weekday in (2, 3, 4) and random.random() < 0.45:
        activity_multiplier *= 1.08
        review_multiplier *= 1.06
        agent_multiplier *= 1.12
    if weekday in (3, 4) and random.random() < 0.40:
        coding_multiplier *= 1.10
        activity_multiplier *= 1.05
    if weekday in (0, 4) and random.random() < 0.35:
        review_multiplier *= 1.08
    activity_multiplier *= random.uniform(0.94, 1.08)
    coding_multiplier *= random.uniform(0.92, 1.08)
    review_multiplier *= random.uniform(0.92, 1.08)
    agent_multiplier *= random.uniform(0.90, 1.10)
    return {
        "is_weekend": is_weekend,
        "progress": progress,
        "phase": phase,
        "activity_multiplier": activity_multiplier,
        "coding_multiplier": coding_multiplier,
        "review_multiplier": review_multiplier,
        "agent_multiplier": agent_multiplier,
        "ask_multiplier": ask_multiplier,
        "plan_multiplier": plan_multiplier,
        "custom_multiplier": custom_multiplier,
        "acceptance_multiplier": acceptance_multiplier,
    }


def generate_org_row(
    day: date,
    day_rows: Sequence[dict[str, object]],
    rolling_day_rows: Sequence[Sequence[dict[str, object]]],
) -> dict[str, object]:
    """ユーザー行から Organization レベルの 1 日分データを集計する。"""
    row: dict[str, object] = {
        "day": day.isoformat(),
        "organization_id": MOCK_ORG_ID,
    }
    for field in USER_METRIC_FIELDS:
        row[field] = sum(int(user_row[field]) for user_row in day_rows)
    row.update(generate_org_agent_rollups(rolling_day_rows))
    row["totals_by_language_feature"] = generate_org_language_rollups(day_rows)
    return row


def generate_user_row(
    day: date,
    user: dict[str, object],
    day_context: dict[str, float | bool | str] | None = None,
) -> dict[str, object]:
    """ユーザーレベルの 1 日 1 ユーザー分データを生成する。"""
    context = day_context or generate_day_context(day, day_index=0, total_days=1)
    interaction_count = sample_range(
        user["interaction_range"],
        multiplier=float(context["activity_multiplier"]),
    )
    code_generation_count = sample_ratio_count(
        interaction_count,
        user["generation_ratio"],
        multiplier=float(context["coding_multiplier"]),
    )
    code_acceptance_count = generate_acceptance_count(
        code_generation_count,
        ratio_range=user["acceptance_ratio"],
        multiplier=float(context["acceptance_multiplier"]),
    )
    chat_panel_ask_mode = sample_ratio_count(
        interaction_count,
        user["ask_share"],
        multiplier=float(context["ask_multiplier"]),
    )
    chat_panel_edit_mode = sample_ratio_count(
        interaction_count,
        user["edit_share"],
        multiplier=float(context["coding_multiplier"]) * float(context["plan_multiplier"]),
    )
    chat_panel_custom_mode = sample_ratio_count(
        interaction_count,
        user["custom_share"],
        multiplier=float(context["custom_multiplier"]),
    )
    chat_panel_agent_mode = sample_ratio_count(
        interaction_count,
        user["agent_share"],
        multiplier=float(context["agent_multiplier"]) * float(user["coding_agent_affinity"]),
    )
    agent_edit = sample_ratio_count(
        code_generation_count,
        user["agent_edit_share"],
        multiplier=float(context["agent_multiplier"]) * float(user["coding_agent_affinity"]),
    )

    row: dict[str, object] = {
        "day": day.isoformat(),
        "organization_id": MOCK_ORG_ID,
        "user_id": user["user_id"],
        "user_login": user["user_login"],
        "persona": user["persona"],
        "total_active_users": 1,
        "user_initiated_interaction_count": interaction_count,
        "code_generation_activity_count": code_generation_count,
        "code_acceptance_activity_count": code_acceptance_count,
        "chat_panel_agent_mode": chat_panel_agent_mode,
        "chat_panel_ask_mode": chat_panel_ask_mode,
        "chat_panel_edit_mode": chat_panel_edit_mode,
        "chat_panel_custom_mode": chat_panel_custom_mode,
        "agent_edit": agent_edit,
    }
    row.update(generate_user_flags(row, user, context))
    row["totals_by_language_feature"] = generate_language_breakdown(row, user, context)
    row.pop("persona")
    return row


def generate_org_agent_rollups(
    rolling_day_rows: Sequence[Sequence[dict[str, object]]],
) -> dict[str, int]:
    """公式の Agent 系日次ロールアップを直近ユーザー行から集計する。"""
    one_day_rows = rolling_day_rows[-1] if rolling_day_rows else []
    seven_day_rows = flatten_rows(rolling_day_rows[-7:])
    trailing_twenty_eight_day_rows = flatten_rows(
        rolling_day_rows[-ROLLING_AGENT_WINDOW_DAYS:]
    )

    coding_agent_active_users_1d = count_unique_users(
        one_day_rows,
        lambda row: bool(row["used_copilot_coding_agent"]),
    )
    coding_agent_active_users_7d = count_unique_users(
        seven_day_rows,
        lambda row: bool(row["used_copilot_coding_agent"]),
    )
    coding_agent_active_users_28d = count_unique_users(
        trailing_twenty_eight_day_rows,
        lambda row: bool(row["used_copilot_coding_agent"]),
    )
    monthly_active_agent_users = count_unique_users(
        trailing_twenty_eight_day_rows,
        lambda row: bool(row["used_copilot_coding_agent"])
        or int(row["chat_panel_agent_mode"]) > 0
        or int(row["agent_edit"]) > 0,
    )

    return {
        "monthly_active_agent_users": monthly_active_agent_users,
        "copilot_coding_agent_active_users_1d": coding_agent_active_users_1d,
        "copilot_coding_agent_active_users_7d": coding_agent_active_users_7d,
        "copilot_coding_agent_active_users_28d": coding_agent_active_users_28d,
    }


def normalize_language_weights(
    weights: dict[str, float],
    phase: str,
) -> list[tuple[str, float]]:
    """フェーズ補正込みの言語重みを正規化する。"""
    boosts = LANGUAGE_PHASE_BOOSTS.get(phase, {})
    adjusted = {
        language: base_weight * boosts.get(language, 1.0)
        for language, base_weight in weights.items()
    }
    total = sum(adjusted.values())
    if total <= 0:
        fallback = 1 / max(len(weights), 1)
        return [(language, fallback) for language in weights]
    return [
        (language, weight / total)
        for language, weight in adjusted.items()
    ]


def distribute_weighted_total(
    total: int,
    weighted_items: Sequence[tuple[str, float]],
) -> dict[str, int]:
    """整数値の合計を重みに応じて配分する。"""
    if total <= 0:
        return {language: 0 for language, _weight in weighted_items}

    raw_values = {
        language: total * weight
        for language, weight in weighted_items
    }
    counts = {
        language: int(raw_value)
        for language, raw_value in raw_values.items()
    }
    remainder = total - sum(counts.values())
    for language, _raw_value in sorted(
        raw_values.items(),
        key=lambda item: item[1] - counts[item[0]],
        reverse=True,
    )[:remainder]:
        counts[language] += 1
    return counts


def detect_language_feature(language: str, phase: str) -> str:
    """言語とフェーズから feature ラベルを決める。"""
    if language in AGENTIC_LANGUAGE_FAMILIES and phase in {
        "agent-rollout",
        "delivery-sprint",
    }:
        return "chat_panel_agent_mode"
    if language in CHAT_HEAVY_LANGUAGES:
        return "chat_panel_ask_mode"
    return "code_completion"


def generate_language_breakdown(
    row: dict[str, object],
    user: dict[str, object],
    day_context: dict[str, float | bool | str],
) -> list[dict[str, object]]:
    """ユーザー日次データから language breakdown を生成する。"""
    profile = USER_LANGUAGE_PROFILES[str(user["user_login"])]
    phase = str(day_context["phase"])
    weighted_languages = normalize_language_weights(profile, phase)
    prompt_counts = distribute_weighted_total(
        int(row["user_initiated_interaction_count"]),
        weighted_languages,
    )
    generation_counts = distribute_weighted_total(
        int(row["code_generation_activity_count"]),
        weighted_languages,
    )
    acceptance_counts = distribute_weighted_total(
        int(row["code_acceptance_activity_count"]),
        weighted_languages,
    )
    language_rows: list[dict[str, object]] = []
    for language, _weight in weighted_languages:
        language_rows.append(
            {
                "feature": detect_language_feature(language, phase),
                "language": language,
                "user_initiated_interaction_count": prompt_counts[language],
                "code_generation_activity_count": generation_counts[language],
                "code_acceptance_activity_count": acceptance_counts[language],
            }
        )
    return language_rows


def generate_org_language_rollups(
    day_rows: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    """ユーザーの language breakdown を Organization 単位に集計する。"""
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in day_rows:
        for language_entry in row.get("totals_by_language_feature", []):
            if not isinstance(language_entry, dict):
                continue
            language = str(language_entry.get("language", "unknown"))
            feature = str(language_entry.get("feature", "code_completion"))
            key = (language, feature)
            if key not in grouped:
                grouped[key] = {
                    "language": language,
                    "feature": feature,
                    **{metric: 0 for metric in LANGUAGE_METRIC_FIELDS},
                }
            for metric in LANGUAGE_METRIC_FIELDS:
                grouped[key][metric] = int(grouped[key][metric]) + int(
                    language_entry.get(metric, 0)
                )

    return sorted(
        grouped.values(),
        key=lambda entry: (
            -int(entry["code_generation_activity_count"]),
            -int(entry["user_initiated_interaction_count"]),
            str(entry["language"]),
        ),
    )


def generate_user_flags(
    row: dict[str, object],
    user: dict[str, object],
    day_context: dict[str, float | bool | str],
) -> dict[str, bool]:
    """公式ユーザーフラグを既存アクティビティ量とペルソナから生成する。"""
    interaction_count = int(row["user_initiated_interaction_count"])
    code_generation_count = int(row["code_generation_activity_count"])
    acceptance_count = int(row["code_acceptance_activity_count"])
    chat_panel_agent_mode = int(row["chat_panel_agent_mode"])
    chat_panel_edit_mode = int(row["chat_panel_edit_mode"])
    agent_edit = int(row["agent_edit"])
    coding_agent_affinity = float(user["coding_agent_affinity"])
    review_active_affinity = float(user["review_active_affinity"])
    review_passive_affinity = float(user["review_passive_affinity"])

    coding_agent_score = chat_panel_agent_mode * 2 + agent_edit * 3 + chat_panel_edit_mode
    used_copilot_coding_agent = (
        coding_agent_affinity >= 0.25
        and coding_agent_score >= 10
        and random.random() < min(0.92, 0.45 + coding_agent_affinity * 0.35)
    )

    active_review_signal = acceptance_count + interaction_count // 2 + chat_panel_edit_mode
    active_review_probability = min(
        0.82,
        review_active_affinity * float(day_context["review_multiplier"]) * 0.42,
    )
    used_copilot_code_review_active = (
        review_active_affinity >= 0.3
        and active_review_signal >= 18
        and random.random() < active_review_probability
    )

    passive_review_signal = acceptance_count + code_generation_count // 3
    passive_review_probability = min(
        0.88,
        review_passive_affinity * float(day_context["review_multiplier"]) * 0.34,
    )
    used_copilot_code_review_passive = used_copilot_code_review_active or (
        review_passive_affinity >= 0.2
        and passive_review_signal >= 10
        and random.random() < passive_review_probability
    )

    return {
        "used_copilot_coding_agent": used_copilot_coding_agent,
        "used_copilot_code_review_active": used_copilot_code_review_active,
        "used_copilot_code_review_passive": used_copilot_code_review_passive,
    }


def generate_acceptance_count(
    code_generation_count: int,
    *,
    ratio_range: tuple[float, float],
    multiplier: float = 1.0,
) -> int:
    """コード承認数をコード生成数以下の妥当な範囲で生成する。"""
    acceptance_count = sample_ratio_count(
        code_generation_count,
        ratio_range,
        multiplier=multiplier,
    )
    return min(code_generation_count, acceptance_count)


def sample_active_users(
    users: Sequence[dict[str, object]],
    day_context: dict[str, float | bool | str],
) -> list[dict[str, object]]:
    """その日にアクティブなユーザーをペルソナベースで選ぶ。"""
    is_weekend = bool(day_context["is_weekend"])
    progress = float(day_context["progress"])
    min_active_users = 3 if is_weekend else 4 + round(progress * 2)
    max_active_users = 5 + round(progress * 2) if is_weekend else 6 + round(progress * 2)
    max_active_users = min(max_active_users, FIELD_RANGES["total_active_users"][1])
    min_active_users = min(min_active_users, max_active_users)
    scored_users: list[tuple[float, dict[str, object]]] = []
    active_users: list[dict[str, object]] = []
    for user in users:
        base_probability = float(
            user[
                "weekend_activity_probability"
                if is_weekend
                else "weekday_activity_probability"
            ]
        )
        activity_score = (
            base_probability
            * float(day_context["activity_multiplier"])
            * random.uniform(0.88, 1.12)
        )
        scored_users.append((activity_score, user))
        if activity_score >= 0.52:
            active_users.append(user)

    scored_users.sort(key=lambda item: item[0], reverse=True)
    if len(active_users) < min_active_users:
        selected_logins = {str(user["user_login"]) for user in active_users}
        for _score, user in scored_users:
            if str(user["user_login"]) in selected_logins:
                continue
            active_users.append(user)
            selected_logins.add(str(user["user_login"]))
            if len(active_users) == min_active_users:
                break
    elif len(active_users) > max_active_users:
        active_users = [
            user
            for _score, user in scored_users
            if user in active_users
        ][:max_active_users]

    return active_users


def generate_mock_data(
    *,
    days: Sequence[date] | None = None,
    users: Sequence[dict[str, object]] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """日別・ユーザー別のモックデータをまとめて生成する。"""
    all_days = list(days or generate_dates())
    all_users = list(users or MOCK_USERS)
    day_contexts: list[dict[str, float | bool | str]] = []
    daily_rows: list[list[dict[str, object]]] = []
    org_rows: list[dict[str, object]] = []

    for day_index, day in enumerate(all_days):
        day_context = generate_day_context(
            day,
            day_index=day_index,
            total_days=len(all_days),
        )
        day_contexts.append(day_context)
        active_users = sample_active_users(all_users, day_context)
        day_rows = [
            generate_user_row(day, user, day_context)
            for user in active_users
        ]
        daily_rows.append(day_rows)

    ensure_all_users_seen(all_days, all_users, day_contexts, daily_rows)

    user_rows = flatten_rows(daily_rows)
    rolling_day_rows: list[list[dict[str, object]]] = []
    for day, day_rows in zip(all_days, daily_rows, strict=True):
        rolling_day_rows.append(day_rows)
        org_rows.append(generate_org_row(day, day_rows, rolling_day_rows))

    return org_rows, user_rows


def generate_mock_bundle(
    *,
    seed: int | None = 42,
    days: Sequence[date] | None = None,
    users: Sequence[dict[str, object]] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """シード付きでモックデータを生成する。"""
    if seed is not None:
        random.seed(seed)
    return generate_mock_data(days=days, users=users)


def sample_range(
    value_range: tuple[int, int],
    *,
    multiplier: float = 1.0,
) -> int:
    """範囲と倍率から自然な整数値を 1 つ生成する。"""
    low, high = value_range
    scaled_low = max(0, int(round(int(low) * multiplier)))
    scaled_high = max(scaled_low, int(round(int(high) * multiplier)))
    return random.randint(scaled_low, scaled_high)


def sample_ratio_count(
    base_count: int,
    ratio_range: tuple[float, float],
    *,
    multiplier: float = 1.0,
) -> int:
    """比率レンジから派生カウントを生成する。"""
    if base_count <= 0:
        return 0
    low, high = ratio_range
    ratio = random.uniform(float(low), float(high)) * multiplier
    return max(0, int(round(base_count * ratio)))


def flatten_rows(
    rolling_day_rows: Sequence[Sequence[dict[str, object]]],
) -> list[dict[str, object]]:
    """日単位の行リストを 1 つの配列に平坦化する。"""
    return [row for day_rows in rolling_day_rows for row in day_rows]


def ensure_all_users_seen(
    days: Sequence[date],
    users: Sequence[dict[str, object]],
    day_contexts: Sequence[dict[str, float | bool | str]],
    daily_rows: list[list[dict[str, object]]],
) -> None:
    """観測期間のどこかで全ユーザーが最低 1 回は現れるよう補正する。"""
    seen_users = {
        str(row["user_login"])
        for row in flatten_rows(daily_rows)
    }
    missing_users = [
        user
        for user in users
        if str(user["user_login"]) not in seen_users
    ]
    max_active_users = FIELD_RANGES["total_active_users"][1]
    candidate_indices = sorted(
        range(len(daily_rows)),
        key=lambda index: (len(daily_rows[index]), days[index].weekday() >= 5, index),
    )
    for user in missing_users:
        for index in candidate_indices:
            active_logins = {str(row["user_login"]) for row in daily_rows[index]}
            if str(user["user_login"]) in active_logins:
                break
            if len(daily_rows[index]) >= max_active_users:
                continue
            daily_rows[index].append(
                generate_user_row(days[index], user, day_contexts[index])
            )
            break


def count_unique_users(
    rows: Sequence[dict[str, object]],
    predicate: Callable[[dict[str, object]], bool],
) -> int:
    """条件を満たすユーザー数を一意件数で返す。"""
    matches = {
        str(row["user_login"])
        for row in rows
        if predicate(row)
    }
    return len(matches)


def rows_to_ndjson_bytes(rows: Sequence[dict[str, object]]) -> bytes:
    """行リストを NDJSON バイト列に変換する。"""
    if not rows:
        return b""
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_ndjson(rows: list[dict], path: Path) -> None:
    """行のリストを NDJSON ファイルに書き出す。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(rows_to_ndjson_bytes(rows))
    logger.info("保存: %s (%d 行)", path, len(rows))


def remove_legacy_public_raw_files() -> None:
    """旧ワークフローが public に残した raw データを削除する。"""
    for path in LEGACY_PUBLIC_RAW_FILES:
        if not path.exists():
            continue
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("古い raw データを削除できませんでした: %s (%s)", path, exc)
        else:
            logger.info("古い raw データを削除: %s", path)


def main() -> None:
    """メインエントリポイント。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    output_dir = RAW_DATA_DIR
    remove_legacy_public_raw_files()

    org_rows, user_rows = generate_mock_bundle(seed=42)
    write_ndjson(org_rows, output_dir / "org_metrics.ndjson")
    write_ndjson(user_rows, output_dir / "user_metrics.ndjson")


if __name__ == "__main__":
    main()
