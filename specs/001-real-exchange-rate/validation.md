# Validation record

Date: 2026-10-19. Environment: Python 3.12.15, Streamlit 1.66.0, Plotly 6.9.0, pandas 2.3.3, requests 2.34.2.

`python -m unittest discover -v`: 22 checks passed. The suite uses saved actual IMF responses and clearly identified synthetic arithmetic cases, without network access.

The production adapter also retrieved live IMF country metadata and all six UK/U.S./Euro area price and FX series. It returned 266 country choices and the coverage described in plan.md. The January-March 2024 UK/U.S. real indices averaged 100.

The complete Streamlit app was additionally exercised against live IMF data, including its date controls and all three chart modes. The local server's health endpoint returned HTTP 200. See [live-smoke.json](../../evidence/live-smoke.json).

The public GitHub repository was created and pushed to main: https://github.com/greg-at-k/salamanca. Public visibility and the default branch were verified through GitHub CLI.

| Check | Evidence / status |
| --- | --- |
| A01: currency direction | Live adapter and Decimal fixture check verify USD per GBP |
| A02: synthetic arithmetic | CalculationTests.test_assignment_arithmetic_and_export_mean |
| A03: exported mean | CSV parsing and Decimal verification; within 1e-8 of 100 |
| A04: changing sample | Core benchmark check and Streamlit date interactions |
| A05: missing CPI | Calendar retained, nominal preserved, invalid real month excluded |
| A06: invalid inputs | Missing/zero/negative/nonfinite inputs; blank CSV values |
| A07: chart modes | Plotly axes/units/gaps checks and Streamlit mode interactions |
| A08: no valid RER | Core empty sample and Streamlit no-CPI state checks |
| A09: same country | Core and Streamlit checks |
| A10: reciprocals | Core swap-country check |
| A11: failures | Timeout/HTTP error, empty/malformed CSV, unexpected dimensions, duplicate-month, and no-stale-chart checks |
| A12: Euro area | Live HICP/FX probe; explicit G163/HICP UI check; no app-generated backfill |
| A13: live arithmetic | Reproduced independently with Decimal; user's manual verification pending |
| A14: online deployment | Pending public Streamlit deployment; local server startup succeeded |

The browser-control inventory returned no available browsers or apps, so no visual screenshot review was possible. Streamlit AppTest verifies app execution and widget interactions, but does not replace visual inspection or testing the public deployment.

No public Streamlit URL is established by this record.

## Euro report and selection improvements

Follow-up on 2026-10-19: the reported failure for euro against USD was not reproduced with the actual G163 Euro area series. Live UK/Euro area, Euro area/U.S., and Euro area/Euro area calculations succeeded. Inspection did reveal that the initial country filter admitted six three-letter IMF regions, including Europe (EUR), which is not the Euro area. Those regions are now excluded, including from older cached metadata, and G163 is labeled Euro area (euro / EUR). This fixes a verified menu defect; it does not establish the exact cause of the user's reported failure.

The revised specification adds an explicit Load comparison form, a shared-data default capped at 360 calendar months, shorter/full-history presets, and custom year/month controls. Refresh re-downloads only the last submitted request, while chart-mode changes act immediately on the loaded snapshot.

`python -m unittest discover -v`: **29 checks passed** with Python 3.12.15. New checks cover the 360-month cap, shorter Euro history, preset windows, custom date validation, no price/FX downloads before submission, draft selection behavior, and explicit refresh behavior.

The complete revised app was then exercised with live G163/U.S. downloads, the Load comparison action, and all three chart modes. It selected December 1999-August 2026 (321 months, 320 valid real months), and the exported real index averaged 100 within 1e-8. Country choices now total 260 after excluding the six regions. See [euro-usd-smoke.json](../../evidence/euro-usd-smoke.json) and the [Euro area/U.S. CSV](../../evidence/salamanca_G163_USA_latest.csv).

Browser inventory remained empty, so visual inspection and verification of the user's actual deployed app remain outstanding.
