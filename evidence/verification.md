# UK / U.S. verification example

Date: 2026-10-19. Sample: January-March 2024, inclusive.

This is an automated independent arithmetic check against saved actual IMF responses, not a claim that the user has completed the assignment's manual verification. The user should reproduce and confirm this example personally before submitting.

Sources: see [IMF request manifest](imf/manifest.json). This CSV uses the saved response values and retrieval timestamps; it is not a substitute for testing the deployed app.

## January 2024 inputs

- Country 1: United Kingdom; Country 2: United States.
- P1 = 130 (UK CPI, IMF reference period 2015A).
- P2 = 141.439679347689 (U.S. CPI, IMF reference period 2010A).
- E1 = 0.7875078750787511 GBP per USD.
- E2 = 1 USD per USD.
- SCALE is 0 for all four inputs in this example.

## Calculation to reproduce

```text
S = E2 / E1 = 1.269828571428571 USD per GBP
RER(January) = S * P1 / P2 = 1.167124494675344
RER(February) = 1.160905689519586
RER(March) = 1.168173759237894
RER* = (RER(January) + RER(February) + RER(March)) / 3
     = 1.165401314477608
January real index = 100 * RER(January) / RER*
                   = 100.147861528584972
Mean of the three exported real indices = 100.000000000000003
January implied S* = RER* * P2 / P1 = 1.267953755623755 USD per GBP
```

The nominal direction is USD per GBP. The three-month real index averages 100 within numerical tolerance. If only January is selected, RER* becomes January's RER and January's real index becomes 100; its nominal S does not change.

The implied rate uses the same currency units as actual S and holds RER at the selected sample's mean. It is a descriptive benchmark, not estimated fair value. For a one-valid-month sample, that month's implied and actual rates coincide.

CSV: [salamanca_GBR_USA_2024-01_2024-03.csv](salamanca_GBR_USA_2024-01_2024-03.csv).

User manual verification: pending.
