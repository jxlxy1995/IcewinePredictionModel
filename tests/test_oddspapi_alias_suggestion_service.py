import json

from icewine_prediction.oddspapi_alias_suggestion_service import (
    build_oddspapi_alias_suggestions,
    format_oddspapi_alias_suggestions,
)


def _write_matches_jsonl(report_dir, rows):
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "matches.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_alias_suggestions_use_anchor_side_to_avoid_wrong_fixture_pairs(tmp_path):
    report_dir = tmp_path / "diagnostic-run"
    _write_matches_jsonl(
        report_dir,
        [
            {
                "match_id": 7,
                "league_name": "Premier League",
                "home_team_name": "Wolves",
                "away_team_name": "Fulham",
                "failure_category": "team_name_mismatch",
                "candidates": [
                    {
                        "fixture_id": "oddspapi-wolves-fulham",
                        "home_team_name": "Wolverhampton Wanderers",
                        "away_team_name": "Fulham FC",
                        "home_similarity": "0",
                        "away_similarity": "0.9000",
                        "confidence": "0",
                    },
                    {
                        "fixture_id": "oddspapi-getafe-osasuna",
                        "home_team_name": "Getafe CF",
                        "away_team_name": "Osasuna",
                        "home_similarity": "0",
                        "away_similarity": "0",
                        "confidence": "0",
                    },
                ],
            }
        ],
    )

    report = build_oddspapi_alias_suggestions(
        report_dir=report_dir,
        alias_config_path=tmp_path / "external_aliases.yaml",
    )
    output = format_oddspapi_alias_suggestions(report)

    assert len(report.suggestions) == 1
    suggestion = report.suggestions[0]
    assert suggestion.canonical_name == "Wolves"
    assert suggestion.alias_name == "Wolverhampton Wanderers"
    assert suggestion.side == "home"
    assert suggestion.anchor_side == "away"
    assert "canonical_name: Wolves" in output
    assert "alias_name: Wolverhampton Wanderers" in output
    assert "oddspapi-getafe-osasuna" not in output


def test_alias_suggestions_skip_existing_config_aliases(tmp_path):
    report_dir = tmp_path / "diagnostic-run"
    _write_matches_jsonl(
        report_dir,
        [
            {
                "match_id": 7,
                "league_name": "Premier League",
                "home_team_name": "Wolves",
                "away_team_name": "Fulham",
                "failure_category": "team_name_mismatch",
                "candidates": [
                    {
                        "fixture_id": "oddspapi-wolves-fulham",
                        "home_team_name": "Wolverhampton Wanderers",
                        "away_team_name": "Fulham FC",
                        "home_similarity": "0",
                        "away_similarity": "0.9000",
                        "confidence": "0",
                    }
                ],
            }
        ],
    )
    (tmp_path / "external_aliases.yaml").write_text(
        "\n".join(
            [
                "aliases:",
                "  - entity_type: team",
                "    source_name: oddspapi",
                "    canonical_name: Wolves",
                "    alias_name: Wolverhampton Wanderers",
            ]
        ),
        encoding="utf-8",
    )

    report = build_oddspapi_alias_suggestions(
        report_dir=report_dir,
        alias_config_path=tmp_path / "external_aliases.yaml",
    )

    assert report.suggestions == ()
    assert report.skipped_existing_alias_count == 1
