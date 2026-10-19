# Implementation plan

Date: 2026-10-19. Specification: [spec.md](spec.md).

## Verified data decisions

Live keyless requests succeeded against the assignment's SDMX 3.0 base. Data requests use `/data/dataflow/IMF.STA/{CPI|ER}/+/{key}`, `Accept: text/csv`, and the `c[TIME_PERIOD]` filter. A combined range is `ge:2024-01+le:2024-03`, passed through requests' parameter encoder so the plus remains a filter operator.

The server returns months such as `2024-M01`. The CPI response identifies dataflow version 5.0.0; ER identifies 4.0.1. Use `+` to request the current version and export the actual response's structure identifier.

Country metadata is available at `/structure/codelist/IMF/CL_COUNTRY/+` with `Accept: application/json`. This succeeds where shortened version-specific metadata media types fail. Keep country codes plus G163; explicitly exclude the three-letter regional codes AFR, APD, EUR, MCD, WHD, and SDS in addition to other regional aggregates. EUR is the Europe aggregate, not the Euro area. Country inclusion does not guarantee data availability.

G163.CPI._T.IX.M returns an empty dataset. G163.HICP._T.IX.M returns the Euro area harmonized consumer price index. Use that explicit key for G163, label HICP in the UI and export, and document the distinction. Do not silently substitute HICP for other countries.

Observed coverage in the 2026-10-19 probe, restricted to January 1976 onward:

| Series | First observed month | Last observed month | Numeric observations |
| --- | --- | --- | --- |
| UK CPI | 1976-01 | 2026-08 | 608 |
| U.S. CPI | 1976-01 | 2026-09 | 608 |
| UK FX | 1976-01 | 2026-08 | 608 |
| U.S. FX | 1976-01 | 2026-09 | 609 |
| Euro area HICP | 1999-12 | 2026-09 | 322 |
| Euro area FX | 1999-01 | 2026-08 | 332 |

These are observed availability bounds, not a promise of continuous coverage. The U.S. CPI count already shows why gaps must be retained. Currency names are not in the country codelist: label GBP/USD/EUR explicitly for verified default/Euro countries; otherwise use the source country's domestic-currency label without guessing historical currency codes.

## Architecture

Keep all runtime code in root `app.py` to meet the three-file deployment requirement. Separate pure calculation/parsing functions, HTTP functions, chart construction, and the Streamlit entrypoint within that file. Import UI/dataframe dependencies only inside functions that need them, so core arithmetic and parsing tests run with the standard library and requests.

- Requests: finite connect/read timeouts and at most two retries for transient transport errors, 429, and 5xx. Do not retry ordinary 4xx. Empty data is distinct from transport failure.
- Standard-library CSV parsing: validate expected dimensions, frequency, country and month; reject duplicate months; preserve original observation strings and attributes. Honor SCALE when deriving numeric inputs and retain raw inputs alongside scaled values.
- Pure calculation: align a full selected monthly calendar, validate finite positive inputs, compute nominal values independently of CPI, and calculate the real normalization solely within the selected sample. Handle arithmetic overflow as invalid data.
- Streamlit: cached country metadata for 24 hours, cached series for one hour. A form batches both countries, a sample-window preset, and custom year/month controls behind Load comparison. Default to the latest shared coverage capped at 360 calendar months; also offer 10 years, 5 years, full history, and custom dates. Keep an explicitly labeled loaded snapshot separate from draft fields. Chart mode applies immediately to that snapshot. Refresh explicitly clears caches and reloads the last submitted request.
- Plotly: interactive lines, no gap connection, actual nominal units, optional secondary axis for Both, and a sample-average reference line for Real.
- Default the main chart to Real. Add an independent second figure comparing actual nominal S against S* = RER* * CPI2 / CPI1, using one common currency-unit axis. Use solid/dashed lines to distinguish observed and implied rates. Derive S* in the pure calculation function, retain it in the loaded snapshot, preview, and CSV, and label it as sample-average-implied. Its valid-price coverage can extend to months where actual FX is missing, provided RER* exists.
- CSV: one row per selected month, raw source observations and attributes, arithmetic inputs, calculations, source keys/versions, and retrieval timestamps.

Never present loaded results as though they belong to unsubmitted controls. Fetch full country history only on a submitted load or explicit refresh; use cached series when available. Filter and normalize against the submitted dates. Clear the loaded snapshot on a failed submission so old charts cannot be mistaken for a successful new load. A failed request remains an error rather than becoming an empty or fabricated series. UI can still display/export available nominal inputs when CPI is genuinely empty.

## Validation

Use standard-library unittest for arithmetic, missing data, interval changes, reciprocals, same-country behavior, parser rejection cases, and request failure handling. Save actual small IMF responses as offline regression fixtures with retrieval metadata; synthetic test rows must be identified as synthetic. Compare one live fixture row to independently calculated Decimal arithmetic.

Use Streamlit's AppTest with mocked downloads for country/date/chart flows and actual IMF fixtures. Run with Python 3.12. Inspect the rendered browser if an available browser surface can reach the local server. Record limits honestly: local tests do not establish a public deployment.

## Publishing

Prepare the app and evidence locally first. Publishing requires an authenticated GitHub/Streamlit session and the intended repository owner. Use the user's repository name `salamanca`. Preserve a checklist of deployment and manual submission work that cannot be completed from the available session.
