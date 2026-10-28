"""
Script: ml/train_models.py
Description: Trains and compares Linear Regression, Random Forest, and Gradient Boosting
             regressors to predict canteen wasted_qty_kg from operational features.
Outputs:
  - ml/model_metrics.json (MAE, RMSE, R2 per model)
  - ml/best_model.joblib (Top-performing model pipeline)
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'food_waste.csv')
ML_DIR = os.path.join(os.path.dirname(__file__))


def load_and_preprocess_data(csv_path=DATA_PATH):
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    df['day_of_week'] = df['date'].dt.day_name()
    df['month'] = df['date'].dt.month_name()

    feature_cols = ['day_of_week', 'month', 'location', 'meal_type', 'food_category', 'prepared_qty_kg']
    target_col = 'wasted_qty_kg'

    X = df[feature_cols]
    y = df[target_col]
    return X, y


def build_pipeline(regressor):
    categorical_cols = ['day_of_week', 'month', 'location', 'meal_type', 'food_category']
    numerical_cols = ['prepared_qty_kg']

    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_cols),
            ('num', StandardScaler(), numerical_cols)
        ]
    )

    pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('model', regressor)
    ])
    return pipeline


def train_and_evaluate():
    os.makedirs(ML_DIR, exist_ok=True)
    X, y = load_and_preprocess_data()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    models = {
        'Linear Regression': LinearRegression(),
        'Random Forest': RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42),
        'Gradient Boosting': GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=4, random_state=42)
    }

    results = {}
    best_name = None
    best_r2 = -float('inf')
    best_pipeline = None

    print("=" * 80)
    print(f"{'Model':<22} | {'MAE (kg)':<10} | {'RMSE (kg)':<10} | {'R2 Score':<10}")
    print("=" * 80)

    for name, model in models.items():
        pipe = build_pipeline(model)
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)

        mae = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        r2 = float(r2_score(y_test, y_pred))

        results[name] = {
            'MAE': round(mae, 3),
            'RMSE': round(rmse, 3),
            'R2': round(r2, 4)
        }

        print(f"{name:<22} | {mae:<10.3f} | {rmse:<10.3f} | {r2:<10.4f}")

        if r2 > best_r2:
            best_r2 = r2
            best_name = name
            best_pipeline = pipe

    print("=" * 80)
    print(f"Top-Performing Model: {best_name} (R2 = {best_r2:.4f})")

    # Save metrics JSON
    metrics_path = os.path.join(ML_DIR, 'model_metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump({
            'best_model': best_name,
            'models': results,
            'dataset_size': len(X),
            'train_size': len(X_train),
            'test_size': len(X_test),
            'target': 'wasted_qty_kg'
        }, f, indent=2)
    print(f"Metrics saved to: {metrics_path}")

    # Save best model
    model_save_path = os.path.join(ML_DIR, 'best_model.joblib')
    joblib.dump(best_pipeline, model_save_path)
    print(f"Best model saved to: {model_save_path}")

    return results, best_name


if __name__ == '__main__':
    train_and_evaluate()
