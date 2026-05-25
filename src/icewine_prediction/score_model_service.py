from dataclasses import dataclass

from icewine_prediction.goal_distribution_service import GoalDistributionPrediction
from icewine_prediction.model_training_service import (
    BaselineResultModel,
    LeagueTeamStrengthGoalModel,
    TeamStrengthGoalModel,
)


@dataclass(frozen=True)
class ScoreModelContext:
    league_name: str | None = None
    home_team_name: str | None = None
    away_team_name: str | None = None


def predict_goal_distribution_from_model(
    model,
    context: ScoreModelContext | None = None,
) -> GoalDistributionPrediction:
    if isinstance(model, LeagueTeamStrengthGoalModel):
        context = _require_context(context, require_league=True)
        model = model.predict_match_result_model(
            context.league_name,
            context.home_team_name,
            context.away_team_name,
        )
    elif isinstance(model, TeamStrengthGoalModel):
        context = _require_context(context, require_league=False)
        model = model.predict_match_result_model(
            context.home_team_name,
            context.away_team_name,
        )

    if isinstance(model, BaselineResultModel) or hasattr(model, "predict_goal_distribution"):
        return model.predict_goal_distribution()
    raise TypeError(f"unsupported score model: {model.__class__.__name__}")


def _require_context(
    context: ScoreModelContext | None,
    require_league: bool,
) -> ScoreModelContext:
    if context is None or context.home_team_name is None or context.away_team_name is None:
        raise ValueError("score model context requires home and away names")
    if require_league and context.league_name is None:
        raise ValueError("score model context requires league, home, and away names")
    return context
