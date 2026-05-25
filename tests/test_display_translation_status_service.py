from icewine_prediction.display_translation_status_service import (
    DisplayTranslationStatusService,
)


def test_display_translation_status_service_marks_league_season_done(tmp_path):
    path = tmp_path / "display_translation_status.yaml"
    service = DisplayTranslationStatusService(path)

    assert service.is_done(league_id=39, season=2025) is False

    service.mark_done(league_id=39, season=2025)

    reloaded = DisplayTranslationStatusService(path)
    assert reloaded.is_done(league_id=39, season=2025) is True
    assert reloaded.list_done_keys() == {"39-2025"}
