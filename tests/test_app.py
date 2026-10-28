"""
Unit tests for analytics logic, Athena SQL queries, and AWS Manager
Project: Food Waste Analysis Dashboard Using AWS
"""

import os
import pytest
import pandas as pd
import duckdb
from aws_manager import AWSManager

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'food_waste.csv')


def test_aws_manager_offline_fallback(monkeypatch):
    """Verify AWSManager gracefully handles missing credentials without crashing."""
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/nonexistent/credentials")
    monkeypatch.setenv("AWS_CONFIG_FILE", "/nonexistent/config")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    manager = AWSManager(access_key=None, secret_key=None)
    assert manager.is_connected is False
    assert "not detected" in manager.connection_message or "not initialized" in manager.connection_message
    
    # Bucket listing should return empty list gracefully
    buckets = manager.list_s3_buckets()
    assert buckets == []
    
    # Upload should return informative error tuple
    success, msg = manager.upload_file_to_s3(DATA_PATH)
    assert success is False
    assert "not configured" in msg


def test_sql_summary_query():
    """Verify core Athena SQL summary query produces expected aggregation types."""
    df = pd.read_csv(DATA_PATH)
    con = duckdb.connect()
    con.register('canteen_waste', df)

    sql = """
    SELECT 
        COUNT(record_id) AS total_records,
        SUM(prepared_qty_kg) AS total_prepared,
        SUM(wasted_qty_kg) AS total_wasted,
        ROUND((SUM(wasted_qty_kg) / SUM(prepared_qty_kg)) * 100, 2) AS waste_pct
    FROM canteen_waste
    """
    res = con.execute(sql).fetchdf()
    assert len(res) == 1
    assert res['total_records'][0] == len(df)
    assert res['total_prepared'][0] > res['total_wasted'][0]
    assert 0 < res['waste_pct'][0] < 100


def test_sql_location_ranking_query():
    """Verify location ranking query returns distinct campus dining locations."""
    df = pd.read_csv(DATA_PATH)
    con = duckdb.connect()
    con.register('canteen_waste', df)

    sql = """
    SELECT 
        location,
        SUM(wasted_qty_kg) AS wasted_kg
    FROM canteen_waste
    GROUP BY location
    ORDER BY wasted_kg DESC
    """
    res = con.execute(sql).fetchdf()
    assert len(res) == df['location'].nunique()
    assert res['wasted_kg'].is_monotonic_decreasing


def test_sql_window_function_ranking():
    """Verify Presto/Athena window function (DENSE_RANK) executes properly."""
    df = pd.read_csv(DATA_PATH)
    con = duckdb.connect()
    con.register('canteen_waste', df)

    sql = """
    WITH ranked_dishes AS (
        SELECT 
            location,
            food_item,
            SUM(wasted_qty_kg) AS total_wasted_kg,
            DENSE_RANK() OVER (PARTITION BY location ORDER BY SUM(wasted_qty_kg) DESC) AS rnk
        FROM canteen_waste
        GROUP BY location, food_item
    )
    SELECT location, food_item, total_wasted_kg
    FROM ranked_dishes
    WHERE rnk = 1
    """
    res = con.execute(sql).fetchdf()
    assert len(res) == df['location'].nunique()
