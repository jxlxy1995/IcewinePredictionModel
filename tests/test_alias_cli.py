from typer.testing import CliRunner

from icewine_prediction.cli import app


def test_aliases_group_exposes_add_and_list_commands():
    runner = CliRunner()

    result = runner.invoke(app, ["aliases", "--help"])

    assert result.exit_code == 0
    assert "add" in result.stdout
    assert "list" in result.stdout


def test_aliases_add_accepts_team_alias(monkeypatch):
    runner = CliRunner()
    class DummySessionFactory:
        def __call__(self):
            return self

        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr("icewine_prediction.cli.create_database_engine", lambda: object())
    monkeypatch.setattr("icewine_prediction.cli.initialize_database", lambda engine: None)
    monkeypatch.setattr(
        "icewine_prediction.cli.create_session_factory",
        lambda engine: DummySessionFactory(),
    )
    monkeypatch.setattr(
        "icewine_prediction.cli.add_external_alias",
        lambda session, entity_type, source_name, canonical_name, alias_name: type(
            "Alias",
            (),
            {
                "id": 7,
                "entity_type": entity_type,
                "source_name": source_name,
                "canonical_name": canonical_name,
                "alias_name": alias_name,
            },
        )(),
    )

    result = runner.invoke(
        app,
        [
            "aliases",
            "add",
            "--entity-type",
            "team",
            "--source-name",
            "oddspapi",
            "--canonical-name",
            "Wolves",
            "--alias-name",
            "Wolverhampton Wanderers",
        ],
    )

    assert result.exit_code == 0
    assert "已保存别名 #7 team oddspapi: Wolves = Wolverhampton Wanderers" in result.stdout
