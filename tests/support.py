"""Offline fixtures sourced from actual IMF responses, with explicit provenance."""

import csv
import io
import json
from pathlib import Path

import app

FIXTURES = Path(__file__).resolve().parents[1] / "evidence" / "imf"


def fixture_series(code, kind):
    suffix = "hicp" if code == "G163" and kind == "cpi" else kind
    name = f"2024_q1_{suffix}"
    text = (FIXTURES / f"{name}.csv").read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(text))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(row for row in reader if row["COUNTRY"] == code)
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    info = next(item for item in manifest["requests"] if item["name"] == name)
    return {"code": code, "kind": kind, "key": app.series_key(code, kind)[1],
            "origin": "IMF", "url": info["url"], "retrieved_at": info["retrieved_at_utc"],
            "records": app.parse_series(buffer.getvalue(), code, kind)}


def fixture_inputs(code1="GBR", code2="USA"):
    return {"cpi_1": fixture_series(code1, "cpi"), "fx_1": fixture_series(code1, "fx"),
            "cpi_2": fixture_series(code2, "cpi"), "fx_2": fixture_series(code2, "fx")}


def fixture_countries():
    return {"countries": {"GBR": "United Kingdom", "USA": "United States",
                           "G163": "Euro Area (EA)", "ESP": "Spain"},
            "retrieved_at": "2026-10-19T22:45:06+00:00"}


def synthetic_series(values, code="GBR", kind="cpi"):
    return {"key": app.series_key(code, kind)[1], "origin": "synthetic test fixture",
            "url": "", "retrieved_at": "", "records": {
                month: {"value": value, "raw_obs": str(value), "scale": "0", "attributes": {}}
                for month, value in zip(["2024-01", "2024-02", "2024-03"], values)}}


def synthetic_inputs():
    return {"cpi_1": synthetic_series([120, 100]),
            "cpi_2": synthetic_series([100, 100], "USA"),
            "fx_1": synthetic_series([0.8, 0.5], kind="fx"),
            "fx_2": synthetic_series([1, 1], "USA", "fx")}


UK = {"code": "GBR", "name": "United Kingdom"}
US = {"code": "USA", "name": "United States"}
