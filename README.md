# Salamanca

Explore bilateral real exchange rates using monthly IMF consumer price indices and period-average exchange rates. Choose two countries, set an inclusive monthly sample, compare Real, Nominal, or Both, and download the inputs and calculations as CSV.

Named after the School of Salamanca, whose sixteenth-century scholars and theologians developed early ideas about purchasing power and exchange rates. An [IMF working paper, Box 1](https://www.elibrary.imf.org/view/journals/001/2008/153/article-A001-en.xml) discusses contributions by Azpilcueta and Domingo de Báñez.

## Status

Implemented; 32 automated calculation, parsing, transport, chart, and Streamlit interaction checks pass with Python 3.12.15. Live IMF downloads were verified on 2026-10-19. The public deployment URL and visual browser review have not been verified in this session.

Public repository: [greg-at-k/salamanca](https://github.com/greg-at-k/salamanca), branch `main`. The name replaces the assignment's example name.

## Use without installing Python locally

1. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) with your GitHub account.
2. Create an app from the public `salamanca` repository, branch `main`, entrypoint `app.py`.
3. In Advanced settings, choose **Python 3.12** and initially leave Secrets empty.
4. Deploy, save the public `streamlit.app` URL, and repeat the checks below.

Only `app.py`, `requirements.txt`, and `README.md`, all at the repository root, are required at runtime. Specifications, tests, and evidence are supporting files.

## Run locally, if desired

With Python 3.12, create and activate a virtual environment, then run:

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

No API key was required in the verified requests. Data are cached for one hour; country metadata for 24 hours. Use **Refresh IMF data** to request updated observations or retry. IMF availability and access policies can change.

## Choose and load a comparison

Select both countries and a sample window, then click **Load comparison**. Changing selections does not download or recalculate results until you submit. The results always identify the loaded pair and dates. The initial chart mode is **Real**; chart modes still switch immediately.

The default uses the latest shared valid observations over **up to 30 calendar years** (360 months). If shared history is shorter, it uses that history. Other choices are 10 years, 5 years, full available history, or custom dates. Custom dates use year and month inputs. If no complete real observations exist, automatic windows use shared nominal coverage, then available source coverage, with the limitation labeled.

Thirty years is a practical default window, not an equilibrium benchmark. RER* is always the average within the actual selected sample. To force a new source download, use **Refresh IMF data**; it reloads the last submitted comparison rather than applying unfinished edits.

## Economics

E1 and E2 are each country's local-currency units per USD; P1 and P2 are monthly price indices:

```text
S(t) = E2(t) / E1(t)              # Country 2 currency per Country 1 currency
RER(t) = S(t) * P1(t) / P2(t)
RER* = arithmetic mean of valid RER(t) in the selected sample
Real Index(t) = 100 * RER(t) / RER*
Implied S*(t) = RER* * P2(t) / P1(t)
```

UK as Country 1 and U.S. as Country 2 gives **USD per GBP**. An increase in this RER convention represents real appreciation of Country 1 relative to Country 2.

The real index averages 100 over valid months in the selected sample. Changing dates recalculates RER*. Nominal S retains actual currency units. Both mode uses separate axes.

The additional **Actual and implied exchange rates** chart compares observed nominal S with sample-average-implied S* on one common currency-unit axis. S* is the nominal rate that would keep RER equal to the selected sample's mean. For valid real months, `S / S* = Real Index / 100`. Changing the sample changes its benchmark. Both monthly price indices and a valid sample benchmark are required; S* can still be computed when that month's actual FX is missing. Each line preserves its own missing-data gaps. The second chart is independent of the first chart's mode selector.

RER* is a descriptive sample average, not an estimated equilibrium or measured PPP exchange rate. CPI indices can have different base years, so raw RER levels do not establish absolute price levels. Constant rebasing cancels in the normalized index; historical breaks can still affect comparisons. The app does not label currencies overvalued or undervalued.

## IMF data and coverage

The [IMF API page](https://data.imf.org/en/Resource-Pages/IMF-API) describes its SDMX APIs. The base used here is `https://api.imf.org/external/sdmx/3.0`.

- Countries: `/structure/codelist/IMF/CL_COUNTRY/+`, JSON metadata; country codes plus G163 (Euro area). IMF's three-letter regional codes AFR, APD, EUR, MCD, WHD, and SDS are excluded. G163 is shown as **Euro area (euro / EUR)**; the separate Europe (EUR) aggregate is not the euro currency area.
- National CPI: `/data/dataflow/IMF.STA/CPI/+/{ISO3}.CPI._T.IX.M`.
- Period-average FX: `/data/dataflow/IMF.STA/ER/+/{ISO3}.XDC_USD.PA_RT.M`.
- Euro area prices: `/data/dataflow/IMF.STA/CPI/+/G163.HICP._T.IX.M`.
- Data requests use `Accept: text/csv` and `c[TIME_PERIOD]=ge:1976-01`. IMF months such as `2024-M01` are parsed as `2024-01`.

**Euro area exception:** the supplied national CPI key has no Euro area observations. The app explicitly uses and labels IMF's HICP (harmonized consumer price index). Observed HICP coverage begins December 1999 and FX January 1999. No earlier euro history is constructed, and HICP is not silently substituted for other countries.

Countries may have gaps, limited coverage, or no matching series. Every month in the selected sample is retained; missing calculations are blank. No interpolation or carry-forward occurs. Nominal rates remain available when CPI is missing. Zero, negative, and nonfinite inputs are excluded. Download errors are distinct from empty datasets.

SCALE is applied before calculation. Original observations and all supplied nonempty row attributes are retained in the CSV. Duplicate months and unexpected dimensions are rejected. If the U.S. FX series is genuinely absent, USD/USD can be derived as 1 and explicitly labeled as an identity. A failed download never triggers this identity.

GBP, USD, and EUR are explicit labels for the UK, U.S., and Euro area. Other countries use a domestic-currency label: IMF's country codelist does not supply a time-specific historical currency map. Consider currency changes and series breaks when interpreting long samples.

See the [live response manifest](evidence/imf/manifest.json) and in-app coverage panel for versions, reference periods, flags, and retrieval times. Saved fixtures support offline tests; the running app never uses them as a fallback.

## CSV export

One row per selected month, regardless of chart mode, includes countries, currencies, sample boundaries, CPI/HICP and FX inputs, nominal S, implied S* (`implied_s`), RER, sample RER*, real index, validity, and missing-input reasons. It also includes original observation strings, scale, source attributes, keys, URLs, origin, and UTC retrieval timestamps. Actual dataflow versions are in source attributes.

Calculations use full numeric precision. Display rounding is not applied to exported values. Missing numbers are blank, never zero.

## Verification

1. Select UK / U.S. and confirm USD per GBP.
2. Export a sample and recompute `S = E2 / E1` and `RER = S * CPI1 / CPI2` for one row.
3. Average valid RER rows to obtain RER*, then calculate `100 * RER / RER*`.
4. Confirm the exported real index averages 100 within numerical tolerance (1e-8).
5. Change dates and repeat. Check Real, Nominal, and Both; nominal rates must not be normalized.

See the [independent arithmetic example](evidence/verification.md) and its [January-March 2024 CSV](evidence/salamanca_GBR_USA_2024-01_2024-03.csv). These were checked with Decimal arithmetic. **The user must still perform the assignment's manual verification.**

Development checks:

```sh
python -m unittest discover -v
python scripts/verify_sample.py
```

To refresh saved public IMF evidence, run `python scripts/probe_imf.py` with network access. This intentionally updates fixture values and retrieval metadata; rerun verification afterward.

## Specification and submission evidence

We followed a lightweight process inspired by [Spec Kit](https://github.github.io/spec-kit/quickstart.html); Spec Kit tooling itself has not been installed.

- [Specification](specs/001-real-exchange-rate/spec.md)
- [Plan and live-data decisions](specs/001-real-exchange-rate/plan.md)
- [Task status](specs/001-real-exchange-rate/tasks.md)
- [Validation record](specs/001-real-exchange-rate/validation.md)
- [Prompt evidence notes](evidence/prompt-log.md)

The final submission requires public Streamlit and GitHub URLs, actual prompt/chat screenshots or export, displayed model names and dates, one manual RER verification, and the exported CSV. The prompt notes are excerpts, not a complete transcript.
