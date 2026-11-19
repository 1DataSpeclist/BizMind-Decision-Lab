
from pathlib import Path

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_FILE = (
    PROJECT_ROOT / "data" / "processed"
    / "forecasting_features.csv"
)

MODEL_DIR = PROJECT_ROOT / "models" / "forecasting"

MODEL_FILE = MODEL_DIR / "demand_model.joblib"


FEATURES = [
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",
    "rolling_mean_7",
    "rolling_mean_28",
    "day_of_week",
    "month",
    "day_of_year"
]


def train_model():

    df = pd.read_csv(DATA_FILE, parse_dates=["sale_date"])

    df = df.sort_values(
        ["product_id", "sale_date"]
    ).reset_index(drop=True)

    # Chronological split: last 20% of dates for testing
    unique_dates = sorted(df["sale_date"].unique())

    split_index = int(len(unique_dates) * 0.8)

    test_start = unique_dates[split_index]

    train_df = df[df["sale_date"] < test_start]
    test_df = df[df["sale_date"] >= test_start]

    X_train = train_df[FEATURES]
    y_train = train_df["demand"]

    X_test = test_df[FEATURES]
    y_test = test_df["demand"]

    # Train Random Forest
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    # Model predictions
    predictions = model.predict(X_test)

    # Baseline: previous week's demand
    baseline_predictions = test_df["lag_7"]

    # Evaluation metrics
    model_mae = mean_absolute_error(y_test, predictions)

    model_rmse = mean_squared_error(
        y_test, predictions
    ) ** 0.5

    model_r2 = r2_score(y_test, predictions)

    baseline_mae = mean_absolute_error(
        y_test, baseline_predictions
    )

    # Save model and metadata
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {
            "model": model,
            "features": FEATURES,
            "test_start": str(pd.Timestamp(test_start).date())
        },
        MODEL_FILE
    )

    print("\nDEMAND FORECASTING MODEL RESULTS")
    print("--------------------------------")
    print(f"Training records: {len(train_df)}")
    print(f"Testing records: {len(test_df)}")
    print(f"Test period starts: {test_start}")
    print(f"Model MAE: {model_mae:.3f}")
    print(f"Model RMSE: {model_rmse:.3f}")
    print(f"Model R2 Score: {model_r2:.3f}")
    print(f"Baseline MAE: {baseline_mae:.3f}")

    print("\nModel saved to:")
    print(MODEL_FILE)


if __name__ == "__main__":
    train_model()
