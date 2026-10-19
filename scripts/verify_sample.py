"""Reproduce saved live-data calculations independently using Decimal arithmetic."""

import csv
from decimal import Decimal, localcontext
import io
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app
from tests.support import UK, US, fixture_inputs


def main():
    inputs = fixture_inputs()
    rows = app.calculate_sample(UK, US, inputs, "2024-01", "2024-03")
    output = ROOT / "evidence" / "salamanca_GBR_USA_2024-01_2024-03.csv"
    output.write_bytes(app.export_csv(rows))
    exported = list(csv.DictReader(io.StringIO(output.read_text(encoding="utf-8"))))
    with localcontext() as context:
        context.prec = 40
        rers = []
        for row in exported:
            p1, p2, e1, e2 = [Decimal(row[key]) for key in
                               ("cpi_1_raw_obs", "cpi_2_raw_obs", "fx_1_raw_obs", "fx_2_raw_obs")]
            rers.append((e2 / e1) * p1 / p2)
        benchmark = sum(rers) / len(rers)
        january_index = 100 * rers[0] / benchmark
        january_implied = benchmark * Decimal(exported[0]["cpi_2_raw_obs"]) / Decimal(exported[0]["cpi_1_raw_obs"])
        assert abs(Decimal(exported[0]["rer"]) - rers[0]) < Decimal("1e-12")
        assert abs(Decimal(exported[0]["real_index"]) - january_index) < Decimal("1e-10")
        assert abs(Decimal(exported[0]["implied_s"]) - january_implied) < Decimal("1e-12")
        index_mean = sum(Decimal(r["real_index"]) for r in exported) / len(exported)
        assert abs(index_mean - 100) < Decimal("1e-8")
        row = exported[0]
        note = f"""# UK / U.S. verification example

Date: 2026-10-19. Sample: January-March 2024, inclusive.

This is an automated independent arithmetic check against saved actual IMF responses, not a claim that the user has completed the assignment's manual verification. The user should reproduce and confirm this example personally before submitting.

Sources: see [IMF request manifest](imf/manifest.json). This CSV uses the saved response values and retrieval timestamps; it is not a substitute for testing the deployed app.

## January 2024 inputs

- Country 1: United Kingdom; Country 2: United States.
- P1 = {row['cpi_1_raw_obs']} (UK CPI, IMF reference period 2015A).
- P2 = {row['cpi_2_raw_obs']} (U.S. CPI, IMF reference period 2010A).
- E1 = {row['fx_1_raw_obs']} GBP per USD.
- E2 = {row['fx_2_raw_obs']} USD per USD.
- SCALE is 0 for all four inputs in this example.

## Calculation to reproduce

```text
S = E2 / E1 = {Decimal(row['fx_2_raw_obs']) / Decimal(row['fx_1_raw_obs']):.15f} USD per GBP
RER(January) = S * P1 / P2 = {rers[0]:.15f}
RER(February) = {rers[1]:.15f}
RER(March) = {rers[2]:.15f}
RER* = (RER(January) + RER(February) + RER(March)) / 3
     = {benchmark:.15f}
January real index = 100 * RER(January) / RER*
                   = {january_index:.15f}
Mean of the three exported real indices = {index_mean:.15f}
January implied S* = RER* * P2 / P1 = {january_implied:.15f} USD per GBP
```

The nominal direction is USD per GBP. The three-month real index averages 100 within numerical tolerance. If only January is selected, RER* becomes January's RER and January's real index becomes 100; its nominal S does not change.

The implied rate uses the same currency units as actual S and holds RER at the selected sample's mean. It is a descriptive benchmark, not estimated fair value. For a one-valid-month sample, that month's implied and actual rates coincide.

CSV: [salamanca_GBR_USA_2024-01_2024-03.csv](salamanca_GBR_USA_2024-01_2024-03.csv).

User manual verification: pending.
"""
    (ROOT / "evidence" / "verification.md").write_text(note, encoding="utf-8")
    print(f"Wrote {output.name}; independent Decimal verification passed; exported index mean = {index_mean}.")


if __name__ == "__main__":
    main()
