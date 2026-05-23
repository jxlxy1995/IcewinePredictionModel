from icewine_prediction.sync_runner import build_sync_summary


def test_build_sync_summary_formats_counts():
    summary = build_sync_summary(
        operation="upcoming",
        created=2,
        updated=3,
        skipped=1,
        requests_used=4,
    )

    assert "upcoming" in summary
    assert "created=2" in summary
    assert "updated=3" in summary
    assert "requests=4" in summary
