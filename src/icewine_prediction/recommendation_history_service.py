from dataclasses import replace

from sqlalchemy.orm import Session

from icewine_prediction.historical_performance_service import (
    HistoricalPerformanceFilters,
    build_historical_performance_report,
)
from icewine_prediction.recommendation_service import Recommendation
from icewine_prediction.record_service import edge_bucket_for_value


def _enrich_recommendation_with_history(
    session: Session,
    recommendation: Recommendation,
) -> Recommendation:
    if not recommendation.should_bet or recommendation.side == "watch":
        return recommendation
    report = build_historical_performance_report(
        session,
        HistoricalPerformanceFilters(
            market_type=recommendation.market_type,
            side=recommendation.side,
            edge_bucket=edge_bucket_for_value(recommendation.edge),
        ),
    )
    return replace(
        recommendation,
        historical_sample_count=report.total.record_count,
        historical_roi=report.total.roi,
    )


def enrich_recommendations_with_history(
    session: Session,
    recommendations: list[Recommendation],
) -> list[Recommendation]:
    return [
        _enrich_recommendation_with_history(session, recommendation)
        for recommendation in recommendations
    ]
