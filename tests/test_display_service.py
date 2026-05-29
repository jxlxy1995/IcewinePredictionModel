from icewine_prediction.display_service import (
    DisplayNameService,
    load_display_names,
    save_team_display_names,
)


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


def test_default_display_names_include_mainstream_league_chinese_names():
    service = DisplayNameService()

    assert service.display_league("Bundesliga (Germany)") == "德甲"
    assert service.display_league("Bundesliga (Austria)") == "奥甲"
    assert service.display_league("Super League (China)") == "中超"
    assert service.display_league("2. Bundesliga") == "德乙"
    assert service.display_league("3. Liga") == "德丙"
    assert service.display_league("J1 League") == "日职联"
    assert service.display_league("Ligue 2") == "法乙"
    assert service.display_league("Eerste Divisie") == "荷乙"
    assert service.display_league("Liga I") == "罗甲"
    assert service.display_league("Ekstraklasa") == "波兰超"
    assert service.display_league("Primera División") == "智利甲"


def test_default_display_names_include_candidate_league_chinese_names():
    service = DisplayNameService()

    assert service.display_league("Premier Division (Ireland)") == "爱超"
    assert service.display_league("Ykkösliiga (Finland)") == "芬甲"
    assert service.display_league("1. Division (Norway)") == "挪甲"
    assert service.display_league("1. Division (Denmark)") == "丹麦甲"
    assert service.display_league("Liga 1 (Indonesia)") == "印尼超"


def test_save_team_display_names_merges_existing_yaml(tmp_path):
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

    save_team_display_names(
        {"Inter": "国米", "Fiorentina": "佛罗伦萨"},
        path=config_path,
    )

    display_names = load_display_names(config_path)
    assert display_names.leagues == {"Serie A": "意甲"}
    assert display_names.teams["Inter"] == "国米"
    assert display_names.teams["Fiorentina"] == "佛罗伦萨"
