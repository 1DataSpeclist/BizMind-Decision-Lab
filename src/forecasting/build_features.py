
from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT / "data" / "processed"
    / "product_daily_demand.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT / "data" / "processed"
    / "forecasting_features.csv"
)


def build_features():

    df = pd.read_csv(INPUT_FILE, parse_dates=["sale_date"])

    df = df.sort_values(
        ["product_id", "sale_date"]
    ).copy()

    grouped = df.groupby("product_id")["demand"]

    # Previous demand values
    for lag in [1, 7, 14, 28]:
        df[f"lag_{lag}"] = grouped.shift(lag)

    # Previous-period rolling averages
    df["rolling_mean_7"] = (
        df.groupby("product_id")["demand"]
        .transform(lambda x: x.shift(1).rolling(7).mean())
    )

    df["rolling_mean_28"] = (
        df.groupby("product_id")["demand"]
        .transform(lambda x: x.shift(1).rolling(28).mean())
    )

    # Calendar features
    df["day_of_week"] = df["sale_date"].dt.dayofweek
    df["month"] = df["sale_date"].dt.month
    df["day_of_year"] = df["sale_date"].dt.dayofyear

    # Remove rows without sufficient historical information
    df = df.dropna().reset_index(drop=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print("Forecasting features created successfully!")
    print(f"Total usable records: {len(df)}")
    print(f"Unique products: {df['product_id'].nunique()}")
    print(f"Features saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_features()
