from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BaseFeatures:
    home_attack_strength: Decimal
    away_attack_strength: Decimal
    home_defense_strength: Decimal
    away_defense_strength: Decimal


def default_base_features() -> BaseFeatures:
    return BaseFeatures(
        home_attack_strength=Decimal("1.00"),
        away_attack_strength=Decimal("1.00"),
        home_defense_strength=Decimal("1.00"),
        away_defense_strength=Decimal("1.00"),
    )
