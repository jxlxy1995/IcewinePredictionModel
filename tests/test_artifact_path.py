from pathlib import Path

import pytest

from icewine_prediction.artifact_path import resolve_artifact_path


@pytest.mark.parametrize(
    "stored_path",
    [
        "local_data/training/latest.csv",
        r"local_data\training\latest.csv",
    ],
)
def test_resolve_artifact_path_accepts_both_relative_separator_styles(tmp_path, stored_path):
    expected = tmp_path / "local_data" / "training" / "latest.csv"

    assert resolve_artifact_path(stored_path, project_root=tmp_path) == expected


@pytest.mark.parametrize(
    "stored_path",
    [
        "../outside.csv",
        r"local_data\..\..\outside.csv",
        "/tmp/outside.csv",
        r"C:\outside.csv",
    ],
)
def test_resolve_artifact_path_rejects_absolute_or_escaping_paths(tmp_path, stored_path):
    with pytest.raises(ValueError):
        resolve_artifact_path(stored_path, project_root=tmp_path)
