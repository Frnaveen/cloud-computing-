"""
Unit Tests for Machine Learning Pipeline and Report Metrics Computation
Tests ML model training, inference, and exact statistics from data/food_waste.csv.
"""

import os
import pytest
import pandas as pd
import joblib
from ml.train_models import load_and_preprocess_data, build_pipeline
from scripts.compute_report_numbers import compute_all_metrics


def test_data_preprocessing():
    X, y = load_and_preprocess_data()
    assert len(X) == 630, f"Expected 630 rows, got {len(X)}"
    assert len(y) == 630
    assert 'day_of_week' in X.columns
    assert 'month' in X.columns
    assert 'prepared_qty_kg' in X.columns


def test_trained_model_exists_and_predicts():
    model_path = os.path.join(os.path.dirname(__file__), '..', 'ml', 'best_model.joblib')
    assert os.path.exists(model_path), "ml/best_model.joblib not found"
    
    pipe = joblib.load(model_path)
    sample_input = pd.DataFrame([{
        'day_of_week': 'Monday',
        'month': 'September',
        'location': 'Main Canteen',
        'meal_type': 'Lunch',
        'food_category': 'Cooked Grains',
        'prepared_qty_kg': 100.0
    }])
    pred = pipe.predict(sample_input)
    assert len(pred) == 1
    assert 0 < pred[0] < 100, f"Predicted waste {pred[0]} should be reasonable (between 0 and 100 kg)"


def test_compute_report_numbers_exact_values():
    metrics = compute_all_metrics()
    assert metrics['total_records'] == 630
    assert metrics['total_prepared_kg'] == 48061.9
    assert metrics['total_wasted_kg'] == 8128.6
    assert metrics['overall_waste_percentage'] == 16.91
    assert metrics['total_financial_loss_inr'] == 697507
    assert metrics['records_above_25_pct'] == 26
