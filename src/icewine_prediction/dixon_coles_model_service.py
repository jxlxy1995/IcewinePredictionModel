from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import exp, factorial, log

from scipy.optimize import minimize, minimize_scalar

from icewine_prediction.goal_distribution_service import (
    MAX_GOALS,
    GoalDistributionPrediction,
    build_goal_distribution_prediction_from_scores,
)
from icewine_prediction.training_sample_service import TrainingSample


MIN_RHO = Decimal("-0.2500")
MAX_RHO = Decimal("0.2500")
MIN_STRENGTH = -3.0
MAX_STRENGTH = 3.0
MIN_HOME_ADVANTAGE = -1.0
MAX_HOME_ADVANTAGE = 1.0
REGULARIZATION_WEIGHT = 0.01


@dataclass(frozen=True)
class DixonColesGoalModel:
    home_expected_goals: Decimal
    away_expected_goals: Decimal
    rho: Decimal

    def predict_goal_distribution(self) -> GoalDistributionPrediction:
        return _build_dixon_coles_goal_distribution(
            home_expected_goals=self.home_expected_goals,
            away_expected_goals=self.away_expected_goals,
            rho=self.rho,
        )


@dataclass(frozen=True)
class DixonColesTeamParameters:
    attack: Decimal
    defense: Decimal


@dataclass(frozen=True)
class DixonColesAttackDefenseModel:
    home_intercept: Decimal
    away_intercept: Decimal
    home_advantage: Decimal
    rho: Decimal
    team_parameters: dict[str, DixonColesTeamParameters]

    @property
    def team_count(self) -> int:
        return len(self.team_parameters)

    @property
    def home_base_expected_goals(self) -> Decimal:
        return _expected_goals_from_log_value(self.home_intercept)

    @property
    def away_base_expected_goals(self) -> Decimal:
        return _expected_goals_from_log_value(self.away_intercept)

    def predict_match_goal_distribution(
        self,
        home_team_name: str,
        away_team_name: str,
    ) -> GoalDistributionPrediction:
        home_parameters = self.team_parameters.get(home_team_name, _neutral_team_parameters())
        away_parameters = self.team_parameters.get(away_team_name, _neutral_team_parameters())
        home_log_goals = (
            self.home_intercept
            + self.home_advantage
            + home_parameters.attack
            - away_parameters.defense
        )
        away_log_goals = self.away_intercept + away_parameters.attack - home_parameters.defense
        return _build_dixon_coles_goal_distribution(
            home_expected_goals=_expected_goals_from_log_value(home_log_goals),
            away_expected_goals=_expected_goals_from_log_value(away_log_goals),
            rho=self.rho,
        )


def train_dixon_coles_goal_model(samples: list[TrainingSample]) -> DixonColesGoalModel:
    if not samples:
        raise ValueError("dixon-coles goal model requires at least one training sample")
    home_expected_goals, away_expected_goals = _weighted_expected_goals(samples)

    def objective(rho: float) -> float:
        return _negative_log_likelihood(
            samples=samples,
            home_expected_goals=home_expected_goals,
            away_expected_goals=away_expected_goals,
            rho=Decimal(str(rho)),
        )

    result = minimize_scalar(
        objective,
        bounds=(float(MIN_RHO), float(MAX_RHO)),
        method="bounded",
    )
    rho = Decimal(str(result.x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return DixonColesGoalModel(
        home_expected_goals=home_expected_goals,
        away_expected_goals=away_expected_goals,
        rho=max(MIN_RHO, min(MAX_RHO, rho)),
    )


def train_dixon_coles_attack_defense_model(
    samples: list[TrainingSample],
) -> DixonColesAttackDefenseModel:
    if not samples:
        raise ValueError("dixon-coles attack-defense model requires at least one training sample")

    team_names = sorted(
        {sample.home_team_name for sample in samples}
        | {sample.away_team_name for sample in samples}
    )
    team_indexes = {team_name: index for index, team_name in enumerate(team_names)}
    home_expected_goals, away_expected_goals = _weighted_expected_goals(samples)
    home_intercept = log(float(home_expected_goals))
    away_intercept = log(float(away_expected_goals))
    parameter_count = len(team_names) * 2 + 2
    initial_parameters = [0.0] * parameter_count
    bounds = (
        [(MIN_STRENGTH, MAX_STRENGTH)] * (len(team_names) * 2)
        + [(MIN_HOME_ADVANTAGE, MAX_HOME_ADVANTAGE)]
        + [(float(MIN_RHO), float(MAX_RHO))]
    )

    def objective(parameters) -> float:
        return _attack_defense_negative_log_likelihood(
            parameters=parameters,
            samples=samples,
            team_indexes=team_indexes,
            home_intercept=home_intercept,
            away_intercept=away_intercept,
        )

    result = minimize(
        objective,
        initial_parameters,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": 500},
    )
    return _build_attack_defense_model(
        parameters=result.x,
        team_names=team_names,
        home_intercept=home_intercept,
        away_intercept=away_intercept,
    )


def _weighted_expected_goals(samples: list[TrainingSample]) -> tuple[Decimal, Decimal]:
    total_weight = sum(sample.time_decay_weight for sample in samples)
    home_goals = sum(Decimal(sample.home_score) * sample.time_decay_weight for sample in samples)
    away_goals = sum(Decimal(sample.away_score) * sample.time_decay_weight for sample in samples)
    return (
        _round_expected_goals(home_goals / total_weight),
        _round_expected_goals(away_goals / total_weight),
    )


def _attack_defense_negative_log_likelihood(
    parameters,
    samples: list[TrainingSample],
    team_indexes: dict[str, int],
    home_intercept: float,
    away_intercept: float,
) -> float:
    team_count = len(team_indexes)
    home_advantage = parameters[team_count * 2]
    rho = parameters[team_count * 2 + 1]
    loss = 0.0
    for sample in samples:
        home_index = team_indexes[sample.home_team_name]
        away_index = team_indexes[sample.away_team_name]
        home_lambda = exp(
            home_intercept
            + home_advantage
            + parameters[home_index]
            - parameters[team_count + away_index]
        )
        away_lambda = exp(
            away_intercept
            + parameters[away_index]
            - parameters[team_count + home_index]
        )
        tau = _dixon_coles_tau_float(
            sample.home_score,
            sample.away_score,
            home_lambda,
            away_lambda,
            rho,
        )
        if tau <= 0:
            return 1_000_000_000.0
        probability = (
            _poisson_probability(home_lambda, sample.home_score)
            * _poisson_probability(away_lambda, sample.away_score)
            * tau
        )
        probability = max(probability, 0.000000000001)
        loss += float(sample.time_decay_weight) * -log(probability)
    regularization = REGULARIZATION_WEIGHT * sum(
        parameter * parameter for parameter in parameters[: team_count * 2 + 1]
    )
    return loss + regularization


def _build_attack_defense_model(
    parameters,
    team_names: list[str],
    home_intercept: float,
    away_intercept: float,
) -> DixonColesAttackDefenseModel:
    team_count = len(team_names)
    team_parameters = {
        team_name: DixonColesTeamParameters(
            attack=_round_parameter(Decimal(str(parameters[index]))),
            defense=_round_parameter(Decimal(str(parameters[team_count + index]))),
        )
        for index, team_name in enumerate(team_names)
    }
    rho = _round_parameter(Decimal(str(parameters[team_count * 2 + 1])))
    return DixonColesAttackDefenseModel(
        home_intercept=_round_parameter(Decimal(str(home_intercept))),
        away_intercept=_round_parameter(Decimal(str(away_intercept))),
        home_advantage=_round_parameter(Decimal(str(parameters[team_count * 2]))),
        rho=max(MIN_RHO, min(MAX_RHO, rho)),
        team_parameters=team_parameters,
    )


def _negative_log_likelihood(
    samples: list[TrainingSample],
    home_expected_goals: Decimal,
    away_expected_goals: Decimal,
    rho: Decimal,
) -> float:
    loss = 0.0
    for sample in samples:
        tau = _dixon_coles_tau(
            sample.home_score,
            sample.away_score,
            home_expected_goals,
            away_expected_goals,
            rho,
        )
        if tau <= Decimal("0"):
            return 1_000_000_000.0
        probability = (
            _poisson_probability(float(home_expected_goals), sample.home_score)
            * _poisson_probability(float(away_expected_goals), sample.away_score)
            * float(tau)
        )
        probability = max(probability, 0.000000000001)
        loss += float(sample.time_decay_weight) * -log(probability)
    return loss


def _dixon_coles_tau(
    home_goals: int,
    away_goals: int,
    home_expected_goals: Decimal,
    away_expected_goals: Decimal,
    rho: Decimal,
) -> Decimal:
    if home_goals == 0 and away_goals == 0:
        return Decimal("1") - home_expected_goals * away_expected_goals * rho
    if home_goals == 0 and away_goals == 1:
        return Decimal("1") + home_expected_goals * rho
    if home_goals == 1 and away_goals == 0:
        return Decimal("1") + away_expected_goals * rho
    if home_goals == 1 and away_goals == 1:
        return Decimal("1") - rho
    return Decimal("1")


def _dixon_coles_tau_float(
    home_goals: int,
    away_goals: int,
    home_expected_goals: float,
    away_expected_goals: float,
    rho: float,
) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1 - home_expected_goals * away_expected_goals * rho
    if home_goals == 0 and away_goals == 1:
        return 1 + home_expected_goals * rho
    if home_goals == 1 and away_goals == 0:
        return 1 + away_expected_goals * rho
    if home_goals == 1 and away_goals == 1:
        return 1 - rho
    return 1


def _build_dixon_coles_goal_distribution(
    home_expected_goals: Decimal,
    away_expected_goals: Decimal,
    rho: Decimal,
) -> GoalDistributionPrediction:
    score_probabilities = {}
    for home_goals in range(MAX_GOALS + 1):
        for away_goals in range(MAX_GOALS + 1):
            probability = Decimal(
                str(
                    _poisson_probability(float(home_expected_goals), home_goals)
                    * _poisson_probability(float(away_expected_goals), away_goals)
                    * float(
                        _dixon_coles_tau(
                            home_goals,
                            away_goals,
                            home_expected_goals,
                            away_expected_goals,
                            rho,
                        )
                    )
                )
            )
            if probability < Decimal("0"):
                probability = Decimal("0")
            score_probabilities[(home_goals, away_goals)] = probability
    return build_goal_distribution_prediction_from_scores(
        home_expected_goals=home_expected_goals,
        away_expected_goals=away_expected_goals,
        score_probabilities=score_probabilities,
    )


def _neutral_team_parameters() -> DixonColesTeamParameters:
    return DixonColesTeamParameters(attack=Decimal("0"), defense=Decimal("0"))


def _poisson_probability(lam: float, goals: int) -> float:
    return exp(-lam) * lam**goals / factorial(goals)


def _round_expected_goals(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_parameter(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _expected_goals_from_log_value(value: Decimal) -> Decimal:
    return _round_expected_goals(Decimal(str(exp(float(value)))))
