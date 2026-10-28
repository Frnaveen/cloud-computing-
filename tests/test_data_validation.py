"""
Automated Unit Tests for Food Waste Data Validation and AWS Lambda Logic
Project: Food Waste Analysis Dashboard Using AWS
"""

import os
import pytest
import pandas as pd
import lambda_function

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'food_waste.csv')


def test_dataset_exists_and_readable():
    """Verify that data/food_waste.csv exists and contains rows."""
    assert os.path.exists(DATA_PATH), f"Dataset not found at {DATA_PATH}"
    df = pd.read_csv(DATA_PATH)
    assert len(df) > 0, "Dataset is empty"
    assert len(df) >= 100, f"Expected at least 100 records for meaningful analysis, got {len(df)}"


def test_dataset_columns():
    """Verify all required columns are present in the dataset."""
    df = pd.read_csv(DATA_PATH)
    expected_cols = [
        'record_id', 'date', 'location', 'meal_type', 'food_category',
        'food_item', 'prepared_qty_kg', 'consumed_qty_kg', 'wasted_qty_kg',
        'waste_percentage', 'cost_per_kg_inr', 'waste_cost_inr'
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing required column: {col}"


def test_dataset_logical_integrity():
    """Verify physical and mathematical logic in the food waste records."""
    df = pd.read_csv(DATA_PATH)
    
    # 1. Prepared quantity must be strictly positive
    assert (df['prepared_qty_kg'] > 0).all(), "Found non-positive prepared_qty_kg"
    
    # 2. Wasted quantity cannot be negative
    assert (df['wasted_qty_kg'] >= 0).all(), "Found negative wasted_qty_kg"
    
    # 3. Wasted cannot exceed prepared
    assert (df['wasted_qty_kg'] <= df['prepared_qty_kg']).all(), "Found wasted_qty_kg exceeding prepared_qty_kg"
    
    # 4. Consumed quantity cannot be negative
    assert (df['consumed_qty_kg'] >= 0).all(), "Found negative consumed_qty_kg"
    
    # 5. Waste cost must be non-negative
    assert (df['waste_cost_inr'] >= 0).all(), "Found negative waste_cost_inr"


def test_lambda_validate_record_valid():
    """Test Lambda validation with a perfectly valid record."""
    valid_row = {
        'record_id': 'FW-TEST-001',
        'date': '2026-09-01',
        'location': 'Main Canteen',
        'meal_type': 'Lunch',
        'food_category': 'Cooked Grains',
        'food_item': 'Basmati Rice',
        'prepared_qty_kg': '100.0',
        'consumed_qty_kg': '85.0',
        'wasted_qty_kg': '15.0',
        'waste_percentage': '15.0',
        'cost_per_kg_inr': '50.0',
        'waste_cost_inr': '750.0'
    }
    is_valid, err, is_anomaly = lambda_function.validate_record(valid_row, 1)
    assert is_valid is True
    assert err is None
    assert is_anomaly is False


def test_lambda_validate_record_invalid_wasted_exceeds_prepared():
    """Test Lambda rejection when wasted > prepared."""
    bad_row = {
        'record_id': 'FW-TEST-BAD',
        'date': '2026-09-01',
        'location': 'Main Canteen',
        'meal_type': 'Lunch',
        'food_category': 'Cooked Grains',
        'food_item': 'Basmati Rice',
        'prepared_qty_kg': '50.0',
        'consumed_qty_kg': '0.0',
        'wasted_qty_kg': '60.0', # Exceeds prepared!
        'waste_percentage': '120.0',
        'cost_per_kg_inr': '50.0',
        'waste_cost_inr': '3000.0'
    }
    is_valid, err, _ = lambda_function.validate_record(bad_row, 1)
    assert is_valid is False
    assert "exceeds" in err


def test_lambda_validate_record_detects_anomaly():
    """Test Lambda anomaly flag when waste_percentage >= 25%."""
    high_waste_row = {
        'record_id': 'FW-TEST-ANOMALY',
        'date': '2026-09-01',
        'location': 'Hostel Mess Block A',
        'meal_type': 'Dinner',
        'food_category': 'Dairy & Desserts',
        'food_item': 'Gulab Jamun',
        'prepared_qty_kg': '100.0',
        'consumed_qty_kg': '70.0',
        'wasted_qty_kg': '30.0',
        'waste_percentage': '30.0', # Above 25% threshold
        'cost_per_kg_inr': '160.0',
        'waste_cost_inr': '4800.0'
    }
    is_valid, err, is_anomaly = lambda_function.validate_record(high_waste_row, 1)
    assert is_valid is True
    assert is_anomaly is True


def test_lambda_process_csv_on_actual_dataset():
    """Test Lambda CSV processor directly on data/food_waste.csv."""
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    result = lambda_function.process_csv_content(content)
    assert result['success'] is True
    assert result['total_rows'] == result['valid_rows']
    assert result['invalid_rows'] == 0
    assert result['anomalies_detected'] > 0
