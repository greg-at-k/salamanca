import copy
import csv
from decimal import Decimal, localcontext
import io
import math
import unittest
from unittest.mock import MagicMock, patch

import requests

import app
from tests.support import (FIXTURES, UK, US, fixture_inputs, fixture_series,
                           synthetic_inputs)


class CalculationTests(unittest.TestCase):
    def test_assignment_arithmetic_and_export_mean(self):
        rows = app.calculate_sample(UK, US, synthetic_inputs(), "2024-01", "2024-02")
        self.assertEqual([r["nominal_s"] for r in rows], [1.25, 2])
        self.assertEqual([r["rer"] for r in rows], [1.5, 2])
        self.assertEqual(rows[0]["sample_mean_rer"], 1.75)
        exported = list(csv.DictReader(io.StringIO(app.export_csv(rows).decode())))
        self.assertAlmostEqual(sum(float(r["real_index"]) for r in exported) / 2, 100, places=8)
        self.assertAlmostEqual(rows[0]["real_index"], 85.71428571428571)

    def test_dates_change_benchmark_but_not_nominal(self):
        rows = app.calculate_sample(UK, US, synthetic_inputs(), "2024-01", "2024-01")
        self.assertEqual(rows[0]["sample_mean_rer"], 1.5)
        self.assertEqual(rows[0]["real_index"], 100)
        self.assertEqual(rows[0]["nominal_s"], 1.25)

    def test_missing_cpi_retains_nominal_and_calendar(self):
        inputs = synthetic_inputs()
        inputs["cpi_1"]["records"].pop("2024-02")
        rows = app.calculate_sample(UK, US, inputs, "2024-01", "2024-03")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["nominal_s"], 2)
        self.assertIsNone(rows[1]["rer"])
        self.assertEqual(rows[0]["sample_mean_rer"], 1.5)
        self.assertEqual(rows[0]["real_index"], 100)
        self.assertFalse(rows[2]["valid_rer"])
        self.assertIn("cpi_1", rows[1]["missing_or_invalid_reason"])

    def test_invalid_inputs_and_empty_sample(self):
        for value in (None, 0, -1, math.inf, math.nan):
            for field in ("fx_1", "fx_2", "cpi_1", "cpi_2"):
                with self.subTest(value=value, field=field):
                    inputs = synthetic_inputs()
                    inputs[field]["records"]["2024-01"]["value"] = value
                    row = app.calculate_sample(UK, US, inputs, "2024-01", "2024-01")[0]
                    self.assertFalse(row["valid_rer"])
                    self.assertIsNone(row["sample_mean_rer"])
                    self.assertIsNone(row["real_index"])
                    if field.startswith("fx"):
                        self.assertIsNone(row["nominal_s"])

    def test_reverse_pair_reciprocals(self):
        inputs = synthetic_inputs()
        reverse = {"cpi_1": inputs["cpi_2"], "cpi_2": inputs["cpi_1"],
                   "fx_1": inputs["fx_2"], "fx_2": inputs["fx_1"]}
        first = app.calculate_sample(UK, US, inputs, "2024-01", "2024-02")
        second = app.calculate_sample(US, UK, reverse, "2024-01", "2024-02")
        for a, b in zip(first, second):
            self.assertAlmostEqual(a["nominal_s"] * b["nominal_s"], 1)
            self.assertAlmostEqual(a["rer"] * b["rer"], 1)

    def test_same_country(self):
        rows = app.calculate_sample(UK, UK, fixture_inputs("GBR", "GBR"), "2024-01", "2024-03")
        for row in rows:
            self.assertEqual((row["nominal_s"], row["rer"], row["real_index"]), (1, 1, 100))

    def test_live_row_against_independent_decimal_arithmetic(self):
        inputs = fixture_inputs()
        rows = app.calculate_sample(UK, US, inputs, "2024-01", "2024-03")
        with localcontext() as context:
            context.prec = 40
            rer = []
            for month in ("2024-01", "2024-02", "2024-03"):
                p1, p2, e1, e2 = [Decimal(inputs[k]["records"][month]["raw_obs"])
                                   for k in ("cpi_1", "cpi_2", "fx_1", "fx_2")]
                rer.append((e2 / e1) * p1 / p2)
            mean = sum(rer) / 3
            self.assertAlmostEqual(rows[0]["rer"], float(rer[0]), places=12)
            self.assertAlmostEqual(rows[0]["real_index"], float(100 * rer[0] / mean), places=10)
            self.assertEqual(rows[0]["currency_1"], "GBP")
            self.assertEqual(rows[0]["currency_2"], "USD")
            self.assertGreater(rows[0]["nominal_s"], 1)

    def test_csv_missing_values_provenance_and_original_precision(self):
        inputs = fixture_inputs()
        inputs["cpi_1"]["records"].pop("2024-02")
        rows = app.calculate_sample(UK, US, inputs, "2024-01", "2024-03")
        exported = list(csv.DictReader(io.StringIO(app.export_csv(rows).decode())))
        self.assertEqual(exported[1]["real_index"], "")
        self.assertEqual(exported[1]["cpi_1"], "")
        self.assertEqual(exported[0]["fx_1_raw_obs"], inputs["fx_1"]["records"]["2024-01"]["raw_obs"])
        self.assertIn("IMF.STA:CPI", exported[0]["cpi_1_attributes"])
        self.assertEqual(exported[0]["fx_1_origin"], "IMF")

    def test_month_validation_and_inclusive_calendar(self):
        self.assertEqual(app.month_range("2023-12", "2024-02"), ["2023-12", "2024-01", "2024-02"])
        for start, end in [("1975-12", "1976-01"), ("2024-02", "2024-01"), ("2024-00", "2024-02")]:
            with self.assertRaises(app.DataError):
                app.month_range(start, end)


class ParserTests(unittest.TestCase):
    def single_csv(self, **changes):
        record = fixture_series("GBR", "fx")["records"]["2024-01"]
        row = {**record["attributes"], "OBS_VALUE": record["raw_obs"], **changes}
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
        return buffer.getvalue()

    def test_actual_month_formats_and_euro_hicp(self):
        self.assertEqual(app.month_label("2024-M01"), "2024-01")
        series = fixture_series("G163", "cpi")
        self.assertEqual(len(series["records"]), 3)
        self.assertIn("HICP", series["key"])

    def test_unknown_dimensions_and_duplicate_months_rejected(self):
        for change in ({"COUNTRY": "USA"}, {"FREQUENCY": "A"}, {"INDICATOR": "USD_XDC"},
                       {"TIME_PERIOD": "2024-Q1"}, {"SCALE": "bad"}):
            with self.subTest(change=change), self.assertRaises(app.DataError):
                app.parse_series(self.single_csv(**change), "GBR", "fx")
        text = self.single_csv()
        with self.assertRaisesRegex(app.DataError, "duplicate"):
            app.parse_series(text + text.splitlines()[1] + "\n", "GBR", "fx")

    def test_empty_dataset_and_bad_format_distinct(self):
        text = self.single_csv(COUNTRY="", FREQUENCY="", INDICATOR="", TYPE_OF_TRANSFORMATION="",
                               TIME_PERIOD="", OBS_VALUE="")
        self.assertEqual(app.parse_series(text, "GBR", "fx"), {})
        self.assertEqual(app.parse_series("", "GBR", "fx"), {})
        with self.assertRaises(app.DataError):
            app.parse_series("<html>Unavailable</html>", "GBR", "fx")

    def test_scale_and_invalid_raw_value_preserved(self):
        records = app.parse_series(self.single_csv(OBS_VALUE="0.7875", SCALE="2"), "GBR", "fx")
        row = records["2024-01"]
        self.assertAlmostEqual(row["value"], 78.75)
        self.assertEqual(row["raw_obs"], "0.7875")
        for value in ("", "NaN", "Infinity", ".."):
            records = app.parse_series(self.single_csv(OBS_VALUE=value), "GBR", "fx")
            self.assertIsNone(records["2024-01"]["value"])
            self.assertEqual(records["2024-01"]["raw_obs"], value)

    def test_country_filter_includes_euro_excludes_groups(self):
        codes = ["GBR", "USA", "G163", "G001", "ESP", "XKX"]
        payload = {"data": {"codelists": [{"id": "CL_COUNTRY", "codes": [
            {"id": code, "names": {"en": code}} for code in codes]}]}}
        countries = app.parse_countries(payload)
        self.assertIn("G163", countries)
        self.assertIn("XKX", countries)
        self.assertNotIn("G001", countries)
        with self.assertRaises(app.DataError):
            app.parse_countries({"data": {}})


class TransportTests(unittest.TestCase):
    def test_timeout_auth_and_server_errors_are_actionable(self):
        for status in (None, 401, 403, 404, 503):
            with self.subTest(status=status):
                session = MagicMock()
                if status is None:
                    session.get.side_effect = requests.Timeout("test")
                else:
                    response = MagicMock()
                    response.status_code = status
                    response.raise_for_status.side_effect = requests.HTTPError(response=response)
                    session.get.return_value = response
                context = MagicMock()
                context.__enter__.return_value = session
                with patch("app.requests.Session", return_value=context), self.assertRaises(app.DataError) as exc:
                    app.get_response("/test", "text/csv")
                self.assertIn("IMF download failed", str(exc.exception))
                self.assertEqual(session.get.call_args.kwargs["timeout"], (10, 30))
                retry = session.mount.call_args.args[1].max_retries
                self.assertEqual(retry.total, 2)
                self.assertNotIn(403, retry.status_forcelist)

    def test_usd_identity_only_for_genuinely_empty_us_series(self):
        response = MagicMock(text="", url="https://api.imf.org/example")
        with patch("app.get_response", return_value=response):
            us = app.fetch_series("USA", "fx")
            uk = app.fetch_series("GBR", "fx")
        self.assertEqual(us["origin"], "USD identity")
        self.assertEqual(us["records"]["2024-01"]["value"], 1)
        self.assertEqual(uk["records"], {})
        with patch("app.get_response", side_effect=app.DataError("Failed")), self.assertRaises(app.DataError):
            app.fetch_series("USA", "fx")


class ChartTests(unittest.TestCase):
    def test_modes_axes_units_and_gaps(self):
        inputs = synthetic_inputs()
        inputs["cpi_1"]["records"].pop("2024-02")
        rows = app.calculate_sample(UK, US, inputs, "2024-01", "2024-03")
        before = copy.deepcopy(rows)
        for mode, traces in (("Real", 1), ("Nominal", 1), ("Both", 2)):
            figure = app.build_chart(rows, mode, "USD per GBP")
            self.assertEqual(len(figure.data), traces)
            self.assertTrue(all(trace.connectgaps is False for trace in figure.data))
            if mode == "Both":
                self.assertEqual(figure.data[1].yaxis, "y2")
                self.assertEqual(figure.layout.yaxis2.title.text, "USD per GBP")
                self.assertIsNone(figure.data[0].y[1])
            if mode == "Nominal":
                self.assertEqual(figure.data[0].y[0], 1.25)
        self.assertEqual(rows, before)


if __name__ == "__main__":
    unittest.main()
