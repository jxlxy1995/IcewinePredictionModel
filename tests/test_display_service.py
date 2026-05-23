from icewine_prediction.display_service import DisplayNameService, load_display_names


def test_display_name_service_translates_leagues_and_teams(tmp_path):
    config_path = tmp_path / "display_names.yaml"
    config_path.write_text(
        """
leagues:
  Serie A: 意甲
teams:
  Inter: 国际米兰
""",
        encoding="utf-8",
    )

    display_names = load_display_names(config_path)
    service = DisplayNameService(display_names)

    assert service.display_league("Serie A") == "意甲"
    assert service.display_team("Inter") == "国际米兰"


def test_display_name_service_falls_back_to_original_name(tmp_path):
    config_path = tmp_path / "display_names.yaml"
    config_path.write_text("leagues: {}\nteams: {}\n", encoding="utf-8")

    display_names = load_display_names(config_path)
    service = DisplayNameService(display_names)

    assert service.display_league("Unknown League") == "Unknown League"
    assert service.display_team("Unknown Team") == "Unknown Team"
