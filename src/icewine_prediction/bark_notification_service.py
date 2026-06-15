from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable
from zoneinfo import ZoneInfo

import requests

from icewine_prediction.config import BEIJING_TIMEZONE
from icewine_prediction.paper_confidence_service import PaperConfidenceGroup


DEFAULT_MAX_BODY_CHARS = 3500


@dataclass(frozen=True)
class BarkMessage:
    title: str
    body: str


@dataclass(frozen=True)
class BarkPushResult:
    success: bool
    status_code: int | None = None
    response_text: str | None = None
    error: str | None = None


def load_bark_push_url() -> str | None:
    push_url = os.getenv("BARK_PUSH_URL")
    return push_url.strip() if push_url and push_url.strip() else None


def push_bark_message(
    push_url: str,
    message: BarkMessage,
    timeout_seconds: float = 8.0,
) -> BarkPushResult:
    try:
        response = requests.post(
            push_url,
            json={"title": message.title, "body": message.body},
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return BarkPushResult(success=False, error=str(exc))
    return BarkPushResult(
        success=200 <= response.status_code < 300,
        status_code=response.status_code,
        response_text=response.text,
    )


def format_paper_automation_bark_messages(
    *,
    groups: Iterable[PaperConfidenceGroup],
    recorded_count: int | None = None,
    max_body_chars: int = DEFAULT_MAX_BODY_CHARS,
) -> list[BarkMessage]:
    group_list = list(groups)
    total_count = len(group_list) if recorded_count is None else recorded_count
    base_title = f"纸面自动任务：已记录 {total_count} 条"
    if not group_list:
        return [BarkMessage(title=base_title, body="没有记录到候选")]

    blocks = [_format_group_line(index, group) for index, group in enumerate(group_list, start=1)]
    chunks = _split_group_blocks(blocks, max_body_chars=max_body_chars)
    if len(chunks) == 1:
        return [BarkMessage(title=base_title, body=chunks[0])]
    return [
        BarkMessage(title=f"{base_title}（{index}/{len(chunks)}）", body=body)
        for index, body in enumerate(chunks, start=1)
    ]


def _format_group_line(index: int, group: PaperConfidenceGroup) -> str:
    league = group.league_display_name or group.league_name
    home_team = group.home_team_display_name or group.home_team_name
    away_team = group.away_team_display_name or group.away_team_name
    kickoff_time = _format_kickoff_time(group.kickoff_time)
    recommendation = group.recommendation_text or _fallback_recommendation_text(group)
    stake_units = _format_stake_units(group.suggested_stake_units)
    return (
        f"{index}. {league} {home_team} vs {away_team}\n"
        f"   {kickoff_time} {recommendation}  评分{group.confidence_score} 推荐{stake_units}手"
    )


def _split_group_blocks(blocks: list[str], *, max_body_chars: int) -> list[str]:
    if max_body_chars <= 0:
        return ["\n".join(blocks)]

    chunks: list[str] = []
    current_blocks: list[str] = []
    current_length = 0
    for block in blocks:
        separator_length = 1 if current_blocks else 0
        candidate_length = current_length + separator_length + len(block)
        if current_blocks and candidate_length > max_body_chars:
            chunks.append("\n".join(current_blocks))
            current_blocks = [block]
            current_length = len(block)
        else:
            current_blocks.append(block)
            current_length = candidate_length
    if current_blocks:
        chunks.append("\n".join(current_blocks))
    return chunks


def _format_kickoff_time(value: object) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(ZoneInfo(BEIJING_TIMEZONE))
        return value.strftime("%H:%M")
    return str(value)


def _fallback_recommendation_text(group: PaperConfidenceGroup) -> str:
    side = {"home": "主队", "away": "客队", "over": "大球", "under": "小球"}.get(
        group.logical_side,
        group.logical_side,
    )
    return f"{side} {_format_decimal(group.representative_market_line)}"


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _format_stake_units(value: Decimal) -> str:
    return format(value, ".2f")
