import json
import unittest
from pathlib import Path

from src.simulation import Intervention, calculate_all_scenarios, calculate_scenario


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = json.loads((PROJECT_ROOT / "data" / "modelo_hc3.json").read_text(encoding="utf-8"))

    def test_notebook_reference_scenario(self) -> None:
        intervention = Intervention(
            repaired_signals=50,
            repaired_lights=100,
            fixed_monthly_cost=1_850_000,
        )
        central = calculate_all_scenarios(intervention, self.model)["Central"]
        self.assertAlmostEqual(central.monthly_gross_benefit, 12_145_942.50, places=2)
        self.assertAlmostEqual(central.monthly_net_benefit, 10_295_942.50, places=2)
        self.assertAlmostEqual(central.horizon_net_benefit, 123_551_310.00, places=2)

    def test_conversion_factors_and_unit_costs(self) -> None:
        intervention = Intervention(
            repaired_signals=10,
            repaired_lights=5,
            complaints_per_signal=0.5,
            complaints_per_light=2.0,
            fixed_monthly_cost=100,
            signal_unit_cost=10,
            light_unit_cost=20,
            horizon_months=3,
        )
        result = calculate_scenario(
            intervention,
            {"traffic_signal_complaints": 20, "street_light_complaints": 5},
            "Prueba",
        )
        self.assertEqual(result.avoided_signal_complaints, 5)
        self.assertEqual(result.avoided_light_complaints, 10)
        self.assertEqual(result.monthly_gross_benefit, 150)
        self.assertEqual(result.monthly_program_cost, 300)
        self.assertEqual(result.horizon_net_benefit, -450)

    def test_negative_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_scenario(
                Intervention(repaired_signals=-1, repaired_lights=0),
                {"traffic_signal_complaints": 1, "street_light_complaints": 1},
                "Inválido",
            )


if __name__ == "__main__":
    unittest.main()

