"""End-to-end: generate/load sample data, build the full risk table."""
from pathlib import Path

import pandas as pd
import pytest

from src.config import DATA_DIR, DEFAULT_THRESHOLDS
from src.data_loader import (build_risk_table, load_measurements, load_plots,
                             load_suppliers)
from src.reporting import build_evidence_report, to_csv_bytes


@pytest.fixture(scope="module")
def pipeline():
    plots = load_plots(DATA_DIR)
    meas = load_measurements(DATA_DIR)
    risk = build_risk_table(plots, meas, 2015, 2023, DEFAULT_THRESHOLDS)
    return plots, meas, risk


def test_sample_data_loads(pipeline):
    plots, meas, _ = pipeline
    assert len(plots) >= 20
    assert {"plot_id", "area_ha", "geometry"} <= set(plots.columns)
    assert meas["year"].min() <= 2015 and meas["year"].max() >= 2023


def test_all_risk_categories_present(pipeline):
    _, _, risk = pipeline
    # sample data is designed to exercise every dashboard state
    assert set(risk["risk_category"]) >= {"Low", "Moderate", "High"}


def test_alert_and_stable_plots_exist(pipeline):
    _, _, risk = pipeline
    assert risk["post_cutoff_change"].sum() >= 3
    assert (risk["alert_types"] == "no_alert").sum() >= 4


def test_area_ha_plausible(pipeline):
    plots, _, _ = pipeline
    assert plots["area_ha"].between(5, 500).all()


def test_csv_export_roundtrip(pipeline):
    _, _, risk = pipeline
    back = pd.read_csv(pd.io.common.BytesIO(to_csv_bytes(risk)))
    assert len(back) == len(risk)


def test_evidence_report_contents(pipeline):
    _, _, risk = pipeline
    row = risk.iloc[0]
    report = build_evidence_report(row, DEFAULT_THRESHOLDS,
                                   {"post_cutoff_canopy_loss": 5.0})
    assert "NOT a regulatory declaration" in report
    assert row["plot_id"] in report
