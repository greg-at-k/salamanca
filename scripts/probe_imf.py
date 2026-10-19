"""Save real IMF response fixtures and coverage evidence; never used as an app fallback."""

import concurrent.futures
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path

import requests

BASE = "https://api.imf.org/external/sdmx/3.0"
DEST = Path(__file__).resolve().parents[1] / "evidence" / "imf"


def fetch(name, path, parameters, accept="text/csv"):
    response = requests.get(BASE + path, params=parameters,
                            headers={"Accept": accept}, timeout=(10, 45))
    response.raise_for_status()
    return name, response, datetime.now(timezone.utc).isoformat()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    queries = []
    keys = {"cpi": ("CPI", "GBR+USA+G163.CPI._T.IX.M"),
            "hicp": ("CPI", "G163.HICP._T.IX.M"),
            "fx": ("ER", "GBR+USA+G163.XDC_USD.PA_RT.M")}
    for name, (flow, key) in keys.items():
        path = f"/data/dataflow/IMF.STA/{flow}/+/{key}"
        queries.append((f"2024_q1_{name}", path,
                        {"c[TIME_PERIOD]": "ge:2024-01+le:2024-03"}))
        queries.append((f"coverage_{name}", path, {"c[TIME_PERIOD]": "ge:1976-01"}))
    queries.append(("countries", "/structure/codelist/IMF/CL_COUNTRY/+", {}, "application/json"))
    manifest = {"purpose": "Actual IMF responses; offline test evidence, not an app fallback.",
                "requests": []}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch, *q) for q in queries]
        for future in concurrent.futures.as_completed(futures):
            name, response, timestamp = future.result()
            info = {"name": name, "url": response.url, "status": response.status_code,
                    "content_type": response.headers.get("Content-Type"),
                    "retrieved_at_utc": timestamp}
            if name == "countries":
                lists = response.json()["data"]["codelists"]
                countries = {c["id"]: c.get("names", {}).get("en", c.get("name", c["id"]))
                             for item in lists if item["id"] == "CL_COUNTRY"
                             for c in item["codes"]}
                (DEST / "countries.json").write_text(json.dumps(countries, indent=2) + "\n", encoding="utf-8")
                info["code_count"] = len(countries)
            else:
                rows = list(csv.DictReader(io.StringIO(response.text)))
                info["coverage"] = {}
                for country in ("GBR", "USA", "G163"):
                    selected = [r for r in rows if r.get("COUNTRY") == country
                                and r.get("TIME_PERIOD") and r.get("OBS_VALUE")]
                    if selected:
                        months = sorted(r["TIME_PERIOD"].replace("-M", "-") for r in selected)
                        info["coverage"][country] = {"first": months[0], "last": months[-1],
                                                      "observations": len(selected)}
                info["structures"] = sorted({r["STRUCTURE_ID"] for r in rows})
                if name.startswith("2024_q1"):
                    (DEST / f"{name}.csv").write_text(response.text, encoding="utf-8")
            manifest["requests"].append(info)
    manifest["requests"].sort(key=lambda x: x["name"])
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
