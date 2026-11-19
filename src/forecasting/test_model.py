from pathlib import Path
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
    / "forecasting_features.csv"
)

def test_model():

    saved_model = joblib.load(MODEL_FILE)

    model = saved_model["model"]
    features = saved_model["features"]

    df = pd.read_csv(DATA_FILE)

    sample = df[features].tail(10)

    predictions = model.predict(sample)

    print("\nDEMAND FORECAST TEST")
    print("--------------------")

    for i, prediction in enumerate(predictions, start=1):
        print(f"Sample {i}: Predicted demand = {max(0, prediction):.2f}")

    print("\nModel loaded and predictions generated successfully!")

if __name__ == "__main__":
    test_model()