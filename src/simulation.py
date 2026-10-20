from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class Intervention:
    repaired_signals: int
    repaired_lights: int
    complaints_per_signal: float = 1.0
    complaints_per_light: float = 1.0
    fixed_monthly_cost: float = 0.0
    signal_unit_cost: float = 0.0
    light_unit_cost: float = 0.0
    horizon_months: int = 12

    def validate(self) -> None:
        values = asdict(self)
        if self.horizon_months < 1:
            raise ValueError("El horizonte debe ser de al menos un mes.")
        for name, value in values.items():
            if name != "horizon_months" and value < 0:
                raise ValueError(f"{name} no puede ser negativo.")


@dataclass(frozen=True)
class ScenarioResult:
    scenario: str
    avoided_signal_complaints: float
    avoided_light_complaints: float
    monthly_gross_benefit: float
    monthly_program_cost: float
    monthly_net_benefit: float
    horizon_gross_benefit: float
    horizon_program_cost: float
    horizon_net_benefit: float
    benefit_cost_ratio: float | None

    def as_dict(self) -> dict[str, float | str | None]:
        return asdict(self)


def calculate_scenario(
    intervention: Intervention,
    coefficients: Mapping[str, float],
    scenario: str,
) -> ScenarioResult:
    """Calcula beneficios asociados; no interpreta los coeficientes como causalidad."""
    intervention.validate()

    signal_beta = float(coefficients["traffic_signal_complaints"])
    light_beta = float(coefficients["street_light_complaints"])
    avoided_signals = intervention.repaired_signals * intervention.complaints_per_signal
    avoided_lights = intervention.repaired_lights * intervention.complaints_per_light

    monthly_gross = avoided_signals * signal_beta + avoided_lights * light_beta
    monthly_cost = (
        intervention.fixed_monthly_cost
        + intervention.repaired_signals * intervention.signal_unit_cost
        + intervention.repaired_lights * intervention.light_unit_cost
    )
    monthly_net = monthly_gross - monthly_cost
    horizon_gross = monthly_gross * intervention.horizon_months
    horizon_cost = monthly_cost * intervention.horizon_months
    horizon_net = monthly_net * intervention.horizon_months
    ratio = monthly_gross / monthly_cost if monthly_cost > 0 else None

    return ScenarioResult(
        scenario=scenario,
        avoided_signal_complaints=avoided_signals,
        avoided_light_complaints=avoided_lights,
        monthly_gross_benefit=monthly_gross,
        monthly_program_cost=monthly_cost,
        monthly_net_benefit=monthly_net,
        horizon_gross_benefit=horizon_gross,
        horizon_program_cost=horizon_cost,
        horizon_net_benefit=horizon_net,
        benefit_cost_ratio=ratio,
    )


def calculate_all_scenarios(
    intervention: Intervention,
    model: Mapping[str, object],
) -> dict[str, ScenarioResult]:
    variables = model["variables"]
    signal = variables["traffic_signal_complaints"]
    light = variables["street_light_complaints"]

    coefficients_by_scenario = {
        "Conservador": {
            "traffic_signal_complaints": signal["ci95_low"],
            "street_light_complaints": light["ci95_low"],
        },
        "Central": {
            "traffic_signal_complaints": signal["coefficient"],
            "street_light_complaints": light["coefficient"],
        },
        "Favorable": {
            "traffic_signal_complaints": signal["ci95_high"],
            "street_light_complaints": light["ci95_high"],
        },
    }
    return {
        name: calculate_scenario(intervention, coefficients, name)
        for name, coefficients in coefficients_by_scenario.items()
    }

