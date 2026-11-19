
from pathlib import Path
from datetime import date, timedelta

import joblib
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_FILE = (
    PROJECT_ROOT
    / "models"
    / "forecasting"
    / "demand_model.joblib"
)

DATA_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "product_daily_demand.csv"
)

REQUIRED_FEATURES = [
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


def generate_forecast(product_id, days=7, start_date=None):

    try:
        product_id = int(product_id)
        days = int(days)
    except (TypeError, ValueError):
        raise ValueError("Product ID and duration must be integers.")

    if product_id <= 0:
        raise ValueError("Invalid product ID.")

    if days not in (7, 14, 30):
        raise ValueError("Forecast duration must be 7, 14, or 30 days.")

    if not MODEL_FILE.exists():
        raise FileNotFoundError("Forecast model file was not found.")

    if not DATA_FILE.exists():
        raise FileNotFoundError("Processed demand dataset was not found.")

    saved_model = joblib.load(MODEL_FILE)

    if not isinstance(saved_model, dict):
        raise ValueError("Invalid saved forecasting model format.")

    if "model" not in saved_model or "features" not in saved_model:
        raise ValueError("Saved model must contain model and features.")

    model = saved_model["model"]
    features = saved_model["features"]

    missing_features = [
        feature for feature in REQUIRED_FEATURES
        if feature not in features
    ]

    if missing_features:
        raise ValueError(
            f"Model is missing required features: {missing_features}"
        )

    df = pd.read_csv(
        DATA_FILE,
        parse_dates=["sale_date"]
    )

    required_columns = ["product_id", "sale_date", "demand"]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Dataset is missing columns: {missing_columns}"
        )

    product_data = df[
        df["product_id"] == product_id
    ].sort_values("sale_date").copy()

    if product_data.empty:
        raise ValueError("Product ID not found in demand dataset.")

    if product_data["demand"].isna().any():
        raise ValueError("Historical demand contains missing values.")

    history = product_data["demand"].astype(float).tolist()

    if len(history) < 28:
        raise ValueError(
            "At least 28 days of historical demand are required."
        )

    if any(value < 0 for value in history):
        raise ValueError("Historical demand cannot be negative.")

    last_date = product_data["sale_date"].max().date()

    earliest_start = last_date + timedelta(days=1)

    if start_date is None:
        selected_start = earliest_start
    else:
        try:
            selected_start = date.fromisoformat(str(start_date))
        except (TypeError, ValueError):
            raise ValueError("Invalid forecast starting date.")

    if selected_start < earliest_start:
        raise ValueError(
            f"Forecast must start on or after {earliest_start}."
        )

    if selected_start > earliest_start + timedelta(days=90):
        raise ValueError(
            "Forecast starting date cannot be more than 90 days ahead."
        )

    # Generate hidden intermediate predictions when necessary.
    # Only predictions from selected_start onward are returned.

    forecasts = []

    current_date = last_date

    total_days = (selected_start - earliest_start).days + days

    for step in range(total_days):

        next_date = current_date + timedelta(days=1)

        row = {
            "lag_1": history[-1],
            "lag_7": history[-7],
            "lag_14": history[-14],
            "lag_28": history[-28],
            "rolling_mean_7": sum(history[-7:]) / 7,
            "rolling_mean_28": sum(history[-28:]) / 28,
            "day_of_week": next_date.weekday(),
            "month": next_date.month,
            "day_of_year": next_date.timetuple().tm_yday
        }

        input_data = pd.DataFrame([row])[features]

        prediction = float(model.predict(input_data)[0])

        if not pd.notna(prediction):
            raise ValueError(
                "The model returned an invalid prediction."
            )

        prediction = max(0, prediction)

        history.append(prediction)
        current_date = next_date

        if next_date >= selected_start:
            forecasts.append({
                "date": next_date.isoformat(),
                "predicted_demand": round(prediction, 2)
            })

    return forecasts


if __name__ == "__main__":

    result = generate_forecast(
        product_id=1,
        days=7
    )

    print("\nDEMAND FORECAST")
    print("---------------------")

    for item in result:
        print(
            f"{item['date']} : "
            f"{item['predicted_demand']} units"
        )

    total_demand = sum(
        item["predicted_demand"] for item in result
    )

    print("---------------------")
    print(f"Total Demand: {total_demand:.2f} units")
    print(f"Average Daily Demand: {total_demand / len(result):.2f} units")
