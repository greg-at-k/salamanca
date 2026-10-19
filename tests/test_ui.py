"""Streamlit interaction checks using real saved IMF rows, with no network calls."""

import unittest
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

import app
from tests.support import fixture_countries, fixture_series


def render_app():
    import app
    app.main()


class StreamlitTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        self.countries = patch("app.fetch_countries", side_effect=fixture_countries)
        self.series = patch("app.fetch_series", side_effect=fixture_series)
        self.countries.start()
        self.series_mock = self.series.start()
        self.addCleanup(self.countries.stop)
        self.addCleanup(self.series.stop)

    def create_app(self):
        at = AppTest.from_function(render_app, default_timeout=20).run()
        self.assertFalse(at.exception)
        return at

    def test_default_pair_dates_modes_and_download(self):
        at = self.create_app()
        self.assertEqual(at.selectbox(key="country_1").value, "GBR")
        self.assertEqual(at.selectbox(key="country_2").value, "USA")
        self.assertEqual(at.selectbox(key="sample_start").value, "2024-01")
        self.assertEqual(at.selectbox(key="sample_end").value, "2024-03")
        self.assertEqual(at.metric[1].value, "3 / 3")
        self.assertEqual(len(at.get("download_button")), 1)
        for mode in ("Real", "Nominal", "Both"):
            at.radio(key="chart_mode").set_value(mode).run()
            self.assertFalse(at.exception)
            self.assertEqual(len(at.get("plotly_chart")), 1)
            self.assertEqual(at.metric[1].value, "3 / 3")
        at.selectbox(key="sample_start").set_value("2024-02").run()
        self.assertEqual(at.metric[1].value, "2 / 2")
        at.selectbox(key="sample_end").set_value("2024-02").run()
        self.assertEqual(at.metric[1].value, "1 / 1")
        self.assertEqual(at.metric[2].value, "100.00")
        self.assertFalse(at.exception)

    def test_reversed_dates_hide_results(self):
        at = self.create_app()
        at.selectbox(key="sample_start").set_value("2024-03").run()
        at.selectbox(key="sample_end").set_value("2024-01").run()
        self.assertFalse(at.exception)
        self.assertIn("Start month", at.error[0].value)
        self.assertEqual(len(at.get("download_button")), 0)

    def test_euro_area_and_same_country(self):
        at = self.create_app()
        at.selectbox(key="country_1").set_value("G163").run()
        self.assertFalse(at.exception)
        self.assertTrue(any("HICP" in message.value for message in at.info))
        self.assertEqual(at.metric[1].value, "3 / 3")
        at.selectbox(key="country_2").set_value("G163").run()
        self.assertEqual(at.metric[0].value, "1")
        self.assertEqual(at.metric[2].value, "100.00")

    def test_empty_series_keeps_nominal_and_export(self):
        def no_cpi(code, kind):
            series = fixture_series(code, kind)
            if kind == "cpi":
                series["records"] = {}
            return series
        self.series_mock.side_effect = no_cpi
        at = self.create_app()
        self.assertIn("No months", at.warning[0].value)
        self.assertEqual(len(at.get("plotly_chart")), 1)
        self.assertEqual(len(at.get("download_button")), 1)
        at.radio(key="chart_mode").set_value("Real").run()
        self.assertEqual(len(at.get("plotly_chart")), 0)

    def test_download_failure_has_no_stale_chart(self):
        at = self.create_app()
        self.series_mock.side_effect = app.DataError("IMF download failed (Timeout)")
        at.selectbox(key="country_1").set_value("ESP").run()
        self.assertFalse(at.exception)
        self.assertIn("download failed", at.error[0].value)
        self.assertEqual(len(at.get("plotly_chart")), 0)
        self.assertEqual(len(at.get("download_button")), 0)


if __name__ == "__main__":
    unittest.main()
