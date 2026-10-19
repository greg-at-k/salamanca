# Salamanca: bilateral real exchange rate explorer

Status: specification with live-data findings incorporated; see plan.md and tasks.md for implementation status.
Date: 2026-10-19.
Project/repository name: `salamanca` (user-selected name supersedes the assignment's example repository name).

## Purpose

Help a student explore nominal and real bilateral exchange rates, understand the economic calculation, and independently reproduce it from exported IMF inputs. The assignment supplied in the conversation is the requirements source.

## Principles

1. Economic definitions and units must be explicit and verifiable.
2. Real observations, missing data, and download failures must be distinguishable.
3. Every chart and export must use the same selected countries and sample.
4. Keep the implementation small and deployable on Streamlit with Python 3.12.
5. Preserve prompts, model names, dates, and verification evidence for submission.

## User journey

1. Choose Country 1 and Country 2 from IMF countries and the Euro area.
2. Choose inclusive start and end months, no earlier than January 1976.
3. Inspect data coverage and select Real, Nominal, or Both in an interactive chart.
4. Read the calculation and units, then download the selected sample as CSV.
5. Change dates and see the real index recomputed against the new sample mean.

Initial defaults: United Kingdom as Country 1, United States as Country 2; Real chart mode; most recent 30 calendar years of available overlapping valid data (at most 360 months), or all overlapping history if shorter. Automatic windows end at the latest shared valid month. This is a convenient sample choice, not an economic equilibrium benchmark. RER* remains the selected sample's arithmetic average.

Load price/FX data and calculate results only after the user clicks Load comparison. Provide 30-year, 10-year, 5-year, full-history, and custom-date windows. Custom dates use separate year and month inputs rather than a long list starting in 1976. Draft changes leave the explicitly labeled loaded comparison in place until submission. Chart-mode changes apply immediately to the loaded comparison. Refresh IMF data explicitly re-downloads the last submitted request, ignoring draft edits.

## Data contract

- Use monthly IMF CPI and period-average exchange rates from January 1976 where available.
- Assignment-provided API base: `https://api.imf.org/external/sdmx/3.0`.
- Assignment-provided CPI key: `{ISO3}.CPI._T.IX.M`.
- Verified Euro area exception: use `G163.HICP._T.IX.M` because the supplied CPI key has no observations. Clearly identify HICP as the Euro area's harmonized consumer price index in the interface and export.
- Assignment-provided exchange-rate key: `{ISO3}.XDC_USD.PA_RT.M`.
- Euro area country code: `G163`.
- Live UK/U.S. CPI and FX responses, Euro area HICP/FX, country labels, keyless access, and response formats were verified on 2026-10-19. See plan.md for request details and observed coverage.
- Populate country choices from IMF metadata; do not promise every country has both required series.
- Exclude IMF regional codes AFR, APD, EUR, MCD, WHD, and SDS as well as other regional aggregates. In particular, EUR is Europe, not the euro currency area. Label G163 as Euro area (euro / EUR) to make the choice clear.
- Preserve observed values and relevant source flags. Reject ambiguous duplicate country/month observations rather than silently averaging them.
- Align observations by calendar month and retain every month within the selected interval, including months with missing inputs.
- Do not interpolate, carry forward, synthesize history, or substitute another provider or annual data. In particular, do not invent pre-euro observations. Display provider-supplied historical coverage and any relevant metadata.
- USD per USD is an identity of 1, if a USD exchange-rate series is absent. Label this as a derived identity in the export and methodology; never use 1 to replace missing non-USD rates.
- Display the actual coverage, source, retrieval time, and missing/invalid-month counts.
- Cache successful downloads with a visible retrieval time and a refresh action. Use finite request timeouts and bounded retries for transient failures.
- Download failures must produce a clear, actionable message. Never present sample data as live IMF data.

## Economic calculation

For month t:

```text
E1(t) = Country 1 currency units per USD
E2(t) = Country 2 currency units per USD
P1(t) = Country 1 monthly CPI index
P2(t) = Country 2 monthly CPI index
S(t) = E2(t) / E1(t)
RER(t) = S(t) * P1(t) / P2(t)
V = months inside the inclusive selected interval with all four inputs finite and positive
RER* = sum(RER(t) for t in V) / count(V)
Real Index(t) = 100 * RER(t) / RER* for t in V
Implied S*(t) = RER* * P2(t) / P1(t)
```

- Compute nominal S when both FX inputs are finite and positive, even when CPI is missing.
- Compute RER and the real index only for valid months. Preserve invalid raw inputs and flag the reason.
- Recompute RER* whenever either country or date boundary changes. Never normalize against data outside the selected sample.
- Use full numerical precision in calculations and sufficient export precision to reproduce results. Rounding is for display only.
- If V is empty, show that no valid real observations are available; do not divide by zero. Retain nominal observations and allow a CSV of the available inputs.
- A one-valid-month sample has a real index of 100 and is labeled as a one-month sample.
- Allow the same country in both positions; wherever inputs are valid, S = 1, RER = 1, and Real Index = 100.
- Compute implied S* wherever both monthly price indices are finite and positive and the selected-sample RER* exists. The month's actual FX inputs need not be present; preserve gaps in actual S independently. Leave implied S* blank when its inputs are invalid or its result is nonfinite/nonpositive.
- Implied S* has the same Country 2 currency per Country 1 unit direction as actual S. It is the nominal rate holding RER at RER*. On valid real months, S/S* = Real Index/100. It is not an estimate of fair value or equilibrium.

## Interpretation

- For UK / U.S., label nominal S as USD per GBP.
- An increase in this RER convention indicates real appreciation of Country 1 relative to Country 2.
- RER* is the selected sample's arithmetic average, not an estimated equilibrium or a measured PPP exchange rate.
- CPI series are indices with potentially different reference bases. Raw RER levels do not measure absolute relative price levels. Constant CPI rebasing cancels in the normalized real index; historical breaks still require disclosure when identified in provider metadata.
- Do not claim overvaluation or undervaluation from the sample-normalized index alone.

## Interface and charts

- Provide country selectors, month-level start/end controls, and Real / Nominal / Both modes.
- Validate start <= end. Empty coverage and missing-country data must be understandable states.
- Real mode plots the real index, clearly labeled as sample average = 100, with a 100 reference line.
- Nominal mode plots S in actual Country 2 currency units per one Country 1 unit, without normalization.
- Both mode uses separate, clearly labeled axes and distinguishable series.
- Charts support interactive inspection and zooming. Tooltips identify month, series, value, and units.
- Preserve gaps in plotted series rather than drawing across missing observations.
- Changing chart mode does not change calculations, the sample, or exported content.
- Display the selected-sample RER*, valid month count, and data-coverage information.
- Default to Real on first render, preserving the user's subsequent chart-mode choices.
- Below the existing chart, always provide a separate Actual and implied exchange rates comparison when implied observations exist. Plot actual S and implied S* on a single common currency-unit axis, with distinguishable solid/dashed lines and tooltips. The first chart's Real/Nominal/Both setting does not change this comparison.
- Identify the second plot as sample-average-implied; explain that its benchmark changes with the loaded dates. Provide an unavailable state when there is no valid sample benchmark or price pair. Include the implied rate in the data preview and CSV.

## CSV contract

Export one row per calendar month in the selected inclusive interval, in ascending order. Include at least:

| Column | Meaning |
| --- | --- |
| month | Month as YYYY-MM |
| country_1_code, country_1_name | First selected IMF country |
| country_2_code, country_2_name | Second selected IMF country |
| currency_1, currency_2 | Currency labels or codes, using source metadata where available |
| cpi_1, cpi_2 | Raw CPI inputs |
| fx_1_lcu_per_usd, fx_2_lcu_per_usd | FX inputs used |
| fx_1_origin, fx_2_origin | IMF series or USD identity |
| nominal_s | E2 / E1 |
| implied_s | RER* * CPI2 / CPI1, in the same currency units as nominal_s |
| rer | S * CPI1 / CPI2 |
| sample_mean_rer | RER* repeated on each row, blank if unavailable |
| real_index | 100 * RER / RER* |
| valid_rer, missing_or_invalid_reason | Validity and explanation |
| sample_start, sample_end | Selected boundaries |
| cpi_1_series, cpi_2_series, fx_1_series, fx_2_series | Source series identifiers |
| cpi_1_retrieved_at_utc, cpi_2_retrieved_at_utc, fx_1_retrieved_at_utc, fx_2_retrieved_at_utc | Per-input retrieval timestamps; blank for identities |

Include relevant IMF observation flags if supplied. Missing numeric values are blank, not zero. Include all observations and calculations regardless of chart mode. The filename identifies both countries and the selected date range.

## Acceptance checks

These checks are requirements, not claims of completed testing.

| ID | Scenario | Expected result |
| --- | --- | --- |
| A01 | UK as Country 1, U.S. as Country 2 | S is USD per GBP and equals E2/E1 |
| A02 | Two synthetic months: E1 = [0.8, 0.5], E2 = [1, 1], P1 = [120, 100], P2 = [100, 100] | S = [1.25, 2], RER = [1.5, 2], RER* = 1.75, indices approximately [85.7142857143, 114.2857142857] |
| A03 | Export a valid multi-month sample | Arithmetic mean of exported real_index is 100 within absolute tolerance 1e-8 |
| A04 | Shorten the synthetic sample to its first month | RER* = 1.5 and its index = 100; nominal S remains 1.25 |
| A05 | Remove one CPI input from one month | Preserve its row and nominal value; omit its RER/index and exclude it from RER* |
| A06 | Missing, zero, negative, or nonfinite FX/CPI | Preserve and flag the invalid input; no invalid division or infinite plotted/exported result |
| A07 | Select Real, Nominal, and Both | Correct series/units; Both has two axes; export remains identical |
| A08 | Select a period with no valid RER months | Clear explanation; no real curve or normalization; available inputs remain exportable |
| A09 | Select the same country twice | Valid months have nominal S = RER = 1 and real index = 100 |
| A10 | Swap country order for one valid month | Nominal S and raw RER are reciprocals of their original values |
| A11 | Simulate timeout, empty response, malformed response, and unavailable country series | Clear failure or coverage state; no fabricated live data |
| A12 | Inspect Euro area coverage | G163 selected; no app-generated pre-euro backfill |
| A13 | Manually recompute one live-data CSV row | FX direction, RER, and real index reproduce exported values within floating-point tolerance |
| A14 | Deploy with Python 3.12 | App starts; country/date controls, every chart mode, and CSV download work online |
| A15 | Use the default automatic window | Latest shared valid month is the end; start is no earlier than shared coverage and at most 359 months before the end; shorter histories use all shared coverage |
| A16 | Edit countries/dates before Load comparison | No price/FX fetch or recalculation until submission; loaded results keep their own explicit countries/dates |
| A17 | Select custom months and refresh | Year/month inputs apply on Load; invalid ranges fail before fetching; Refresh reloads only the last submitted pair |
| A18 | Search euro in the country menu | G163 is clearly labeled Euro area; the misleading Europe (EUR) regional aggregate is absent |
| A19 | Open a fresh loaded comparison | Real is initially selected; later mode selections persist during interaction |
| A20 | Compare actual and implied rates | Both are on one currency-unit axis; implied S* holds RER at RER*; S/S* equals Real Index/100 for valid real months; dates recalculate S*; CSV includes implied_s |
| A21 | Missing FX, missing CPI, or no benchmark | Implied S* may exist with valid prices despite missing monthly FX; missing prices or absent RER* leave S* blank; neither chart connects across its missing observations |

## Delivery and evidence

- Root deployment files: `app.py`, `requirements.txt`, `README.md`.
- Public GitHub repository named `salamanca`; deploy the root `app.py` to Streamlit with Python 3.12.
- Start with no secrets. If live IMF behavior differs from the assignment's keyless-access assumption, document the observed error and determine the supported access method before changing deployment requirements.
- Preserve actual user prompts or chat screenshots, model names as reported by the interface, and dates. Do not invent a model version or screenshot.
- Submission document: Streamlit URL, GitHub URL, prompt/model/date evidence, and one manual RER verification. Also retain the exported CSV used for that verification.

## Work sequence

1. Verify IMF access and metadata using a small UK/U.S. sample; record response evidence and coverage.
2. Resolve any data-contract discrepancies, then write the implementation plan and ordered tasks.
3. Implement calculation and parsing behavior with meaningful checks for arithmetic, dates, gaps, and error states.
4. Build the Streamlit interface, interactive charts, and CSV export.
5. Verify against A01-A14, documenting any checks that remain unverified.
6. Publish to GitHub and Streamlit, then assemble the submission evidence.

Accounts, dashboards, forecasting, equilibrium-rate estimation, automatic historical currency splicing, and substitute data sources are outside the initial assignment scope.
