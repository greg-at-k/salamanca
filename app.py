"""Salamanca: monthly bilateral real exchange rates from IMF data.

All runtime code lives here so the app deploys with only app.py,
requirements.txt and README.md. Core functions can be tested without Streamlit.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
import math
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://api.imf.org/external/sdmx/3.0"
FIRST_MONTH = "1976-01"
COLORS = {"real": "#18766b", "nominal": "#b76e36"}
# Three-letter regional codes observed in IMF CL_COUNTRY are not countries.
REGIONAL_CODES = frozenset({"AFR", "APD", "EUR", "MCD", "WHD", "SDS"})
WINDOWS = {"Up to 30 years (recommended)": 360, "Last 10 years": 120,
           "Last 5 years": 60, "Full available history": None, "Custom dates": "custom"}
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class DataError(ValueError):
    """The source cannot be downloaded or interpreted without ambiguity."""


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def month_label(value):
    match = re.fullmatch(r"(\d{4})-(?:M)?(\d{2})", str(value))
    if not match or not 1 <= int(match[2]) <= 12:
        raise DataError(f"Unexpected monthly period: {value!r}")
    return f"{match[1]}-{match[2]}"


def month_range(start, end):
    start, end = month_label(start), month_label(end)
    if start < FIRST_MONTH or start > end:
        raise DataError("Select a start month from January 1976 onward, at or before the end month.")
    year, month = map(int, start.split("-"))
    result = []
    while f"{year:04d}-{month:02d}" <= end:
        result.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def positive(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def series_key(code, kind):
    if not (re.fullmatch(r"[A-Z]{3}", code) or code == "G163"):
        raise DataError("Unsupported IMF country code.")
    if kind == "fx":
        return "ER", f"{code}.XDC_USD.PA_RT.M"
    if kind == "cpi":
        return "CPI", f"{code}.{'HICP' if code == 'G163' else 'CPI'}._T.IX.M"
    raise DataError("Unknown series type.")


def get_response(path, accept, params=None):
    """Read public IMF data with bounded transient retries and no required secrets."""
    retries = Retry(total=2, connect=2, read=2, status=2, backoff_factor=0.3,
                    status_forcelist=(429, 500, 502, 503, 504),
                    allowed_methods=frozenset(["GET"]),
                    respect_retry_after_header=False, raise_on_status=False)
    try:
        with requests.Session() as session:
            session.mount("https://", HTTPAdapter(max_retries=retries))
            response = session.get(BASE + path, params=params,
                                   headers={"Accept": accept}, timeout=(10, 30))
            response.raise_for_status()
            return response
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        detail = f"HTTP {status}" if status else type(exc).__name__
        hint = " Try Refresh IMF data in a moment, or check the IMF Data portal."
        if status in (401, 403):
            hint = " IMF refused access. Check its current API access requirements; this app does not assume an API key."
        raise DataError(f"IMF download failed ({detail}) for {path}.{hint}") from exc


def parse_countries(payload):
    try:
        lists = payload["data"]["codelists"]
        countries = {c["id"]: c.get("names", {}).get("en") or c.get("name") or c["id"]
                     for item in lists if item["id"] == "CL_COUNTRY" for c in item["codes"]
                     if (re.fullmatch(r"[A-Z]{3}", c["id"]) and c["id"] not in REGIONAL_CODES)
                     or c["id"] == "G163"}
    except (KeyError, TypeError, AttributeError) as exc:
        raise DataError("IMF country metadata has an unexpected structure.") from exc
    if not {"GBR", "USA", "G163"}.issubset(countries):
        raise DataError("IMF country metadata is incomplete; expected UK, U.S. and Euro area codes.")
    return countries


def fetch_countries():
    response = get_response("/structure/codelist/IMF/CL_COUNTRY/+", "application/json")
    try:
        return {"countries": parse_countries(response.json()), "retrieved_at": utc_now()}
    except requests.exceptions.JSONDecodeError as exc:
        raise DataError("IMF returned unreadable country metadata.") from exc


def parse_series(text, code, kind):
    """Validate one exact series. Preserve observation strings and source attributes."""
    if not text.strip():
        return {}
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    expected = {"COUNTRY": code, "FREQUENCY": "M"}
    if kind == "cpi":
        expected.update(INDEX_TYPE="HICP" if code == "G163" else "CPI",
                        COICOP_1999="_T", TYPE_OF_TRANSFORMATION="IX")
    elif kind == "fx":
        expected.update(INDICATOR="XDC_USD", TYPE_OF_TRANSFORMATION="PA_RT")
    else:
        raise DataError("Unknown series type.")
    required = {*expected, "TIME_PERIOD", "OBS_VALUE", "STRUCTURE_ID"}
    if not required.issubset(reader.fieldnames or []):
        raise DataError("IMF did not return the expected monthly CSV columns.")
    observations = {}
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise DataError("IMF returned a malformed CSV row.")
        # IMF's empty-dataset response contains structure/action but no dimensions.
        if not any(row.get(k, "").strip() for k in (*expected, "TIME_PERIOD", "OBS_VALUE")):
            continue
        if any(row[k] != v for k, v in expected.items()):
            raise DataError("IMF returned unexpected country, frequency, or series dimensions.")
        month = month_label(row["TIME_PERIOD"])
        if month in observations:
            raise DataError(f"IMF returned duplicate observations for {code} in {month}.")
        scale = row.get("SCALE", "") or "0"
        try:
            multiplier = int(scale)
            if not -18 <= multiplier <= 18:
                raise ValueError("Unsupported scale")
        except ValueError as exc:
            raise DataError(f"IMF returned an unsupported SCALE: {scale!r}.") from exc
        raw = row["OBS_VALUE"]
        try:
            value = float(raw) * (10.0 ** multiplier)
            value = value if math.isfinite(value) else None
        except (ValueError, OverflowError):
            value = None
        observations[month] = {
            "value": value, "raw_obs": raw, "scale": scale,
            "attributes": {k: v for k, v in row.items() if k != "OBS_VALUE" and v != ""},
        }
    return observations


def fetch_series(code, kind):
    flow, key = series_key(code, kind)
    response = get_response(f"/data/dataflow/IMF.STA/{flow}/+/{key}", "text/csv",
                            {"c[TIME_PERIOD]": f"ge:{FIRST_MONTH}"})
    records = parse_series(response.text, code, kind)
    origin = "IMF"
    if code == "USA" and kind == "fx" and not records:
        # USD/USD is an identity only if its source series is genuinely absent.
        records = {m: {"value": 1.0, "raw_obs": "", "scale": "0", "attributes": {}}
                   for m in month_range(FIRST_MONTH, datetime.now(timezone.utc).strftime("%Y-%m"))}
        origin = "USD identity"
    return {"code": code, "kind": kind, "key": key, "origin": origin,
            "url": response.url, "retrieved_at": utc_now() if origin == "IMF" else "",
            "records": records}


def currency_label(code):
    # The country codelist has no time-specific currency map. Do not guess one.
    return {"GBR": "GBP", "USA": "USD", "G163": "EUR"}.get(code, f"{code} domestic currency")


def country_label(code, countries):
    return "Euro area (euro / EUR)" if code == "G163" else countries[code]


def sample_window(inputs, window, custom_start, custom_end, current_month):
    """Choose an inclusive calendar window, preferring complete shared inputs."""
    if window not in WINDOWS:
        raise DataError("Choose a supported sample window.")
    if WINDOWS[window] == "custom":
        start, end = month_label(custom_start), month_label(custom_end)
        month_range(start, end)
        if end > current_month:
            raise DataError("The end month cannot be later than the current month.")
        return start, end, "Custom dates"
    valid = {label: {m for m, r in series["records"].items()
                     if FIRST_MONTH <= m <= current_month and positive(r["value"])}
             for label, series in inputs.items()}
    shared = set.intersection(*valid.values())
    nominal = valid["fx_1"] & valid["fx_2"]
    available = set.union(*valid.values())
    coverage = shared or nominal or available or {current_month}
    basis = ("shared real-data coverage" if shared else "shared nominal-data coverage" if nominal
             else "available source coverage" if available else "no source observations")
    first, end = min(coverage), max(coverage)
    months = month_range(FIRST_MONTH, end)
    cap = WINDOWS[window]
    start = max(first, months[max(0, len(months) - cap)]) if cap is not None else first
    return start, end, f"{window} · {basis}"


def load_comparison(request, countries, fetcher, current_month):
    code1, code2 = request["country_1"], request["country_2"]
    country1 = {"code": code1, "name": countries[code1]}
    country2 = {"code": code2, "name": countries[code2]}
    inputs = {"cpi_1": fetcher(code1, "cpi"), "fx_1": fetcher(code1, "fx"),
              "cpi_2": fetcher(code2, "cpi"), "fx_2": fetcher(code2, "fx")}
    start, end, basis = sample_window(inputs, request["window"], request["custom_start"],
                                     request["custom_end"], current_month)
    return {"country_1": country1, "country_2": country2, "inputs": inputs,
            "start": start, "end": end, "basis": basis,
            "rows": calculate_sample(country1, country2, inputs, start, end)}


def calculate_sample(country_1, country_2, inputs, start, end):
    """Build a complete monthly calendar and normalize only the selected sample."""
    months = month_range(start, end)
    rows = []
    for month in months:
        row = {"month": month, "country_1_code": country_1["code"],
               "country_1_name": country_1["name"], "country_2_code": country_2["code"],
               "country_2_name": country_2["name"],
               "currency_1": currency_label(country_1["code"]),
               "currency_2": currency_label(country_2["code"]),
               "sample_start": start, "sample_end": end}
        for label, series in inputs.items():
            observation = series["records"].get(month, {})
            value_column = f"{label}_lcu_per_usd" if label.startswith("fx") else label
            row[value_column] = observation.get("value")
            row[f"{label}_raw_obs"] = observation.get("raw_obs", "")
            row[f"{label}_scale"] = observation.get("scale", "")
            row[f"{label}_attributes"] = json.dumps(observation.get("attributes", {}), sort_keys=True)
            row[f"{label}_series"] = series["key"]
            row[f"{label}_origin"] = series["origin"]
            row[f"{label}_retrieved_at_utc"] = series["retrieved_at"]
            row[f"{label}_source_url"] = series["url"]
        fields = ("cpi_1", "cpi_2", "fx_1_lcu_per_usd", "fx_2_lcu_per_usd")
        reasons = [f"{field}: missing, nonfinite or nonpositive" for field in fields if not positive(row[field])]
        row["nominal_s"] = row["rer"] = row["real_index"] = None
        if all(positive(row[k]) for k in fields[2:]):
            nominal = row["fx_2_lcu_per_usd"] / row["fx_1_lcu_per_usd"]
            if positive(nominal):
                row["nominal_s"] = nominal
            else:
                reasons.append("nominal_s: numeric overflow or underflow")
        if not reasons:
            rer = row["nominal_s"] * (row["cpi_1"] / row["cpi_2"])
            if positive(rer):
                row["rer"] = rer
            else:
                reasons.append("rer: numeric overflow or underflow")
        row["valid_rer"] = row["rer"] is not None
        row["missing_or_invalid_reason"] = "; ".join(reasons)
        rows.append(row)
    valid = [row["rer"] for row in rows if row["valid_rer"]]
    if valid:
        largest = max(valid)
        mean = largest * math.fsum((value / largest) / len(valid) for value in valid)
    else:
        mean = None
    for row in rows:
        row["sample_mean_rer"] = mean
        if row["valid_rer"]:
            row["real_index"] = 100 * (row["rer"] / mean)
    return rows


def export_csv(rows):
    buffer = io.StringIO(newline="")
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def build_chart(rows, mode, nominal_units):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    if mode not in ("Real", "Nominal", "Both"):
        raise DataError("Select Real, Nominal or Both.")
    both = mode == "Both"
    fig = make_subplots(specs=[[{"secondary_y": both}]])
    dates = [f"{row['month']}-01" for row in rows]
    for name, field, color, units in (
        ("Real index", "real_index", COLORS["real"], "sample average = 100"),
        ("Nominal exchange rate", "nominal_s", COLORS["nominal"], nominal_units),
    ):
        if (mode == "Real" and field == "nominal_s") or (mode == "Nominal" and field == "real_index"):
            continue
        secondary = both and field == "nominal_s"
        fig.add_trace(go.Scatter(x=dates, y=[row[field] for row in rows], name=name,
                                mode="lines+markers" if len(rows) == 1 else "lines",
                                connectgaps=False, line={"color": color, "width": 2.5},
                                hovertemplate=f"%{{x|%b %Y}}<br>{name}: %{{y:.6g}}<br>{units}<extra></extra>"),
                      secondary_y=secondary)
    if mode != "Nominal":
        fig.add_hline(y=100, line_dash="dot", line_color="#7f8782", secondary_y=False)
    fig.update_yaxes(title_text=nominal_units if mode == "Nominal" else "Real index · sample average = 100",
                     secondary_y=False, zeroline=False)
    if both:
        fig.update_yaxes(title_text=nominal_units, secondary_y=True, showgrid=False, zeroline=False)
    fig.update_layout(height=470, margin={"l": 15, "r": 15, "t": 35, "b": 10},
                      hovermode="x unified", legend={"orientation": "h", "y": 1.12, "x": 0},
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"family": "Arial, sans-serif"}, dragmode="zoom")
    fig.update_xaxes(type="date", title_text="Month", showgrid=False)
    return fig


def main():
    import pandas as pd
    import streamlit as st

    st.set_page_config(page_title="Salamanca · Real exchange rates", page_icon="◈", layout="wide")

    @st.cache_data(ttl=86400, show_spinner=False)
    def countries_cached():
        return fetch_countries()

    @st.cache_data(ttl=3600, max_entries=256, show_spinner=False)
    def series_cached(code, kind):
        return fetch_series(code, kind)

    st.caption("SALAMANCA  /  AN EXCHANGE RATE OBSERVATORY")
    st.title("Two currencies. A real comparison.")
    st.write("Explore how exchange rates and consumer prices move together, with monthly data from the IMF.")
    refresh = st.sidebar.button("Refresh IMF data", width="stretch", key="refresh_imf")
    if refresh:
        countries_cached.clear()
        series_cached.clear()
    st.sidebar.caption("Refresh re-downloads the last submitted comparison. Use Load comparison to apply new country or date choices. Data are cached for one hour.")
    try:
        with st.spinner("Reading IMF countries…"):
            metadata = countries_cached()
    except DataError as exc:
        st.error(str(exc))
        st.info("Country choices require IMF metadata. Refresh to retry; no substitute data are displayed.")
        return
    # Also filter previously cached metadata when upgrading an existing session.
    countries = {code: name for code, name in metadata["countries"].items() if code not in REGIONAL_CODES}
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    possible = month_range(FIRST_MONTH, current_month)
    default_start = possible[max(0, len(possible) - 360)]
    codes = sorted(countries, key=lambda code: country_label(code, countries).casefold())
    with st.form("comparison_controls"):
        col1, col2 = st.columns(2)
        code1 = col1.selectbox("Country 1", codes, index=codes.index("GBR"),
                              format_func=lambda c: country_label(c, countries), key="country_1")
        code2 = col2.selectbox("Country 2", codes, index=codes.index("USA"),
                              format_func=lambda c: country_label(c, countries), key="country_2")
        window = st.selectbox("Sample window", list(WINDOWS), key="sample_window")
        st.caption("Automatic windows end at the latest month with shared valid data. The 30-year default uses all available history when it is shorter. Gaps stay visible.")
        with st.expander("Custom dates · used only when Custom dates is selected"):
            sy, sm, ey, em = st.columns(4)
            start_year = sy.number_input("Start year", min_value=1976, max_value=int(current_month[:4]),
                                         value=int(default_start[:4]), step=1, key="start_year")
            start_month = sm.selectbox("Start month", range(1, 13), index=int(default_start[5:]) - 1,
                                        format_func=lambda m: MONTH_NAMES[m - 1], key="start_month")
            end_year = ey.number_input("End year", min_value=1976, max_value=int(current_month[:4]),
                                       value=int(current_month[:4]), step=1, key="end_year")
            end_month = em.selectbox("End month", range(1, 13), index=int(current_month[5:]) - 1,
                                      format_func=lambda m: MONTH_NAMES[m - 1], key="end_month")
        submitted = st.form_submit_button("Load comparison", type="primary")
    request = {"country_1": code1, "country_2": code2, "window": window,
               "custom_start": f"{start_year:04d}-{start_month:02d}",
               "custom_end": f"{end_year:04d}-{end_month:02d}"}
    if submitted:
        st.session_state["comparison_request"] = request
    if submitted or (refresh and st.session_state.get("comparison_request")):
        request = st.session_state["comparison_request"]
        st.session_state.pop("loaded_comparison", None)
        st.session_state.pop("comparison_error", None)
        try:
            if WINDOWS[request["window"]] == "custom":
                sample_window({}, request["window"], request["custom_start"], request["custom_end"], current_month)
            with st.spinner("Loading monthly IMF CPI and exchange rates…"):
                st.session_state["loaded_comparison"] = load_comparison(request, countries, series_cached, current_month)
        except DataError as exc:
            st.session_state["comparison_error"] = str(exc)
    if st.session_state.get("comparison_error"):
        st.error(st.session_state["comparison_error"])
        st.info("Correct the selection and click Load comparison, or use Refresh IMF data to retry the last submitted request.")
        return
    loaded = st.session_state.get("loaded_comparison")
    if loaded is None:
        st.info("Choose two countries and a sample window, then click Load comparison.")
        return
    country1, country2 = loaded["country_1"], loaded["country_2"]
    code1, code2 = country1["code"], country2["code"]
    pair = (code1, code2)
    inputs, start, end, rows = loaded["inputs"], loaded["start"], loaded["end"], loaded["rows"]
    valid_count = sum(row["valid_rer"] for row in rows)
    nominal_count = sum(row["nominal_s"] is not None for row in rows)
    mean = rows[0]["sample_mean_rer"]
    units = f"{currency_label(code2)} per {currency_label(code1)}"
    st.subheader(f"{country_label(code1, countries)} → {country_label(code2, countries)}")
    st.caption(f"Loaded sample: {start} to {end} · {loaded['basis']} · Nominal direction: {units}. Selection edits apply only when you click Load comparison.")
    if "G163" in pair:
        st.info("Euro area prices use IMF's HICP (harmonized consumer price index). The national CPI key has no Euro area observations. No earlier euro history is invented.")
    if code1 not in ("GBR", "USA", "G163") or code2 not in ("GBR", "USA", "G163"):
        st.caption("Domestic-currency labels follow the selected country. Historical currency changes and series breaks may limit comparisons over long periods; inspect the source attributes below.")
    first, second, third = st.columns(3)
    first.metric("Sample mean RER*", f"{mean:.6g}" if mean is not None else "Unavailable")
    second.metric("Valid real observations", f"{valid_count} / {len(rows)}")
    index_average = math.fsum(row["real_index"] for row in rows if row["valid_rer"]) / valid_count if valid_count else None
    third.metric("Real index average", f"{index_average:.2f}" if index_average is not None else "Unavailable")
    if not valid_count:
        st.warning("No months have all four valid inputs in this sample. The real index cannot be calculated; available nominal data and raw inputs can still be downloaded.")
    elif valid_count == 1:
        st.info("Only one valid month: its real index equals 100 by construction.")
    elif valid_count < len(rows):
        st.warning(f"{len(rows) - valid_count} month(s) lack valid real inputs. They remain as gaps and are excluded from RER*.")

    mode = st.radio("Chart", ["Real", "Nominal", "Both"], index=2, horizontal=True, key="chart_mode")
    if (mode == "Real" and valid_count) or (mode == "Nominal" and nominal_count) or (mode == "Both" and (valid_count or nominal_count)):
        st.plotly_chart(build_chart(rows, mode, units), width="stretch",
                        config={"displaylogo": False, "scrollZoom": False},
                        key="exchange_rate_chart")
    else:
        st.info("No valid observations for this chart mode in the selected sample.")
    st.caption("The real index is relative to the selected sample's average. Changing the dates recalculates that average. Nominal rates stay in currency units.")
    st.download_button("Download sample CSV", data=export_csv(rows), mime="text/csv",
                       file_name=f"salamanca_{code1}_{code2}_{start}_{end}.csv",
                       key="download_csv", type="primary")

    with st.expander("Observations and calculations", expanded=False):
        st.dataframe(pd.DataFrame(rows)[["month", "cpi_1", "cpi_2", "fx_1_lcu_per_usd",
                                        "fx_2_lcu_per_usd", "nominal_s", "rer", "sample_mean_rer",
                                        "real_index", "valid_rer", "missing_or_invalid_reason"]],
                     hide_index=True, width="stretch")
        st.caption("The CSV also includes original observation strings, scale, source attributes, series identifiers, and retrieval timestamps.")
    with st.expander("Data coverage and source attributes"):
        coverage = []
        for label, series in inputs.items():
            records = series["records"]
            numeric_months = sorted(m for m, r in records.items() if positive(r["value"]))
            coverage.append({"input": label, "IMF series": series["key"], "origin": series["origin"],
                             "first valid month": numeric_months[0] if numeric_months else "Unavailable",
                             "last valid month": numeric_months[-1] if numeric_months else "Unavailable",
                             "valid observations": len(numeric_months),
                             "retrieved (UTC)": series["retrieved_at"] or "Derived identity"})
            # Full attributes remain in the CSV; summarize relevant series metadata in the UI.
            notes = sorted({(r["attributes"].get("STRUCTURE_ID", ""),
                             r["attributes"].get("REFERENCE_PERIOD", ""),
                             r["attributes"].get("STATUS", ""),
                             r["attributes"].get("OVERLAP", "")) for r in records.values()})
            if notes:
                st.caption(f"{label}: structure / CPI reference period / status / overlap")
                st.write([dict(zip(["structure", "reference_period", "status", "overlap"], note)) for note in notes])
        st.dataframe(pd.DataFrame(coverage), hide_index=True, width="stretch")
        st.caption(f"Country metadata retrieved (UTC): {metadata['retrieved_at']}. Validity requires finite, positive numeric inputs. Coverage bounds may contain gaps.")
        st.link_button("Open IMF Data", "https://data.imf.org")
    with st.expander("How to read this comparison"):
        st.latex(r"S_t=\frac{E_{2,t}}{E_{1,t}},\quad RER_t=S_t\frac{P_{1,t}}{P_{2,t}}")
        st.latex(r"RER^*=\frac{1}{N}\sum_{t\in V}RER_t,\quad I_t=100\frac{RER_t}{RER^*}")
        st.write("E is each country's domestic currency per USD; P is its monthly CPI (HICP for the Euro area). V contains only valid months within your selected dates. An increase in this RER convention represents real appreciation of Country 1 relative to Country 2.")
        st.write("RER* is a descriptive sample average, not an estimated equilibrium rate. CPI series can have different base years: raw RER levels do not establish absolute price levels. Constant CPI rebasing cancels in the real index, but historical breaks can still affect comparisons.")
        st.write("No interpolation or carry-forward is used. Missing months remain blank in the CSV. SCALE is applied to source observations; original values and attributes are retained. USD per USD may be derived as 1 only if the IMF USD series is absent, and is labeled as an identity.")
    st.divider()
    st.caption("Named for the School of Salamanca and its early thinking on purchasing power and exchange. Source: IMF · Monthly CPI/HICP and period-average exchange rates.")


if __name__ == "__main__":
    main()
