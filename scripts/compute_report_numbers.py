"""
Script: scripts/compute_report_numbers.py
Description: Computes all exact statistical numbers and KPIs directly from data/food_waste.csv.
             Guarantees zero hardcoded or hand-typed values in the technical report.
"""

import os
import json
import pandas as pd

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'food_waste.csv')
METRICS_PATH = os.path.join(os.path.dirname(__file__), '..', 'ml', 'model_metrics.json')


def compute_all_metrics():
    df = pd.read_csv(DATA_PATH)

    total_records = len(df)
    total_prep = float(df['prepared_qty_kg'].sum())
    total_consumed = float(df['consumed_qty_kg'].sum())
    total_wasted = float(df['wasted_qty_kg'].sum())
    waste_pct = (total_wasted / total_prep) * 100.0
    total_loss_inr = float(df['waste_cost_inr'].sum())
    high_waste_count = int((df['waste_percentage'] >= 25.0).sum())

    # Location breakdown
    loc_agg = df.groupby('location').agg({
        'prepared_qty_kg': 'sum',
        'wasted_qty_kg': 'sum',
        'waste_cost_inr': 'sum'
    }).reset_index()
    loc_agg['waste_pct'] = (loc_agg['wasted_qty_kg'] / loc_agg['prepared_qty_kg'] * 100).round(2)
    loc_agg = loc_agg.sort_values(by='wasted_qty_kg', ascending=False)

    # Category breakdown
    cat_agg = df.groupby('food_category').agg({
        'prepared_qty_kg': 'sum',
        'wasted_qty_kg': 'sum',
        'waste_cost_inr': 'sum'
    }).reset_index()
    cat_agg['waste_pct'] = (cat_agg['wasted_qty_kg'] / cat_agg['prepared_qty_kg'] * 100).round(2)
    cat_agg = cat_agg.sort_values(by='waste_cost_inr', ascending=False)

    # Meal session breakdown
    meal_agg = df.groupby('meal_type').agg({
        'prepared_qty_kg': 'sum',
        'wasted_qty_kg': 'sum',
        'waste_cost_inr': 'sum'
    }).reset_index()
    meal_agg['waste_pct'] = (meal_agg['wasted_qty_kg'] / meal_agg['prepared_qty_kg'] * 100).round(2)
    meal_agg = meal_agg.sort_values(by='wasted_qty_kg', ascending=False)

    # Top dishes by financial loss
    top_dishes = df.groupby(['food_item', 'food_category']).agg({
        'prepared_qty_kg': 'sum',
        'wasted_qty_kg': 'sum',
        'waste_cost_inr': 'sum'
    }).reset_index().sort_values(by='waste_cost_inr', ascending=False).head(5)

    # ML Metrics
    ml_metrics = {}
    if os.path.exists(METRICS_PATH):
        with open(METRICS_PATH, 'r') as f:
            ml_metrics = json.load(f)

    report_numbers = {
        'total_records': total_records,
        'total_prepared_kg': round(total_prep, 1),
        'total_consumed_kg': round(total_consumed, 1),
        'total_wasted_kg': round(total_wasted, 1),
        'overall_waste_percentage': round(waste_pct, 2),
        'total_financial_loss_inr': int(round(total_loss_inr)),
        'records_above_25_pct': high_waste_count,
        'location_breakdown': loc_agg.to_dict(orient='records'),
        'category_breakdown': cat_agg.to_dict(orient='records'),
        'meal_breakdown': meal_agg.to_dict(orient='records'),
        'top_dishes': top_dishes.to_dict(orient='records'),
        'ml_metrics': ml_metrics
    }

    return report_numbers


def print_summary(metrics):
    print("=" * 80)
    print("CANTEEN FOOD WASTE TELEMETRY SUMMARY METRICS")
    print("=" * 80)
    print(f"Total Operational Logs:           {metrics['total_records']} records")
    print(f"Total Food Prepared:              {metrics['total_prepared_kg']:,} kg")
    print(f"Total Food Consumed:              {metrics['total_consumed_kg']:,} kg")
    print(f"Total Food Discarded (Waste):     {metrics['total_wasted_kg']:,} kg")
    print(f"Overall Waste Percentage:         {metrics['overall_waste_percentage']:.2f}%")
    print(f"Total Institutional Loss:         INR {metrics['total_financial_loss_inr']:,}")
    print(f"High-Waste Incidents (>= 25%):    {metrics['records_above_25_pct']} records")
    print("=" * 80)
    print("\nLOCATION BREAKDOWN:")
    for l in metrics['location_breakdown']:
        print(f"  {l['location']:<25}: Prepared {l['prepared_qty_kg']:>7.1f} kg | Wasted {l['wasted_qty_kg']:>6.1f} kg ({l['waste_pct']:>5.2f}%) | Loss INR {l['waste_cost_inr']:>8,.0f}")

    print("\nCATEGORY BREAKDOWN:")
    for c in metrics['category_breakdown']:
        print(f"  {c['food_category']:<20}: Wasted {c['wasted_qty_kg']:>6.1f} kg ({c['waste_pct']:>5.2f}%) | Loss INR {c['waste_cost_inr']:>8,.0f}")

    print("\nMEAL SESSION BREAKDOWN:")
    for m in metrics['meal_breakdown']:
        print(f"  {m['meal_type']:<15}: Prepared {m['prepared_qty_kg']:>7.1f} kg | Wasted {m['wasted_qty_kg']:>6.1f} kg ({m['waste_pct']:>5.2f}%)")

    print("\nTOP 5 DISHES BY FINANCIAL LOSS:")
    for d in metrics['top_dishes']:
        print(f"  {d['food_item']:<25} ({d['food_category']}): Loss INR {d['waste_cost_inr']:>8,.0f} | Wasted {d['wasted_qty_kg']:>6.1f} kg")
    print("=" * 80)


if __name__ == '__main__':
    metrics = compute_all_metrics()
    print_summary(metrics)
