
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

files = [
    "products.csv",
    "suppliers.csv",
    "sales.csv",
    "inventory.csv",
    "purchases.csv"
]

for filename in files:

    df = pd.read_csv(DATA_DIR / filename)

    print("\n" + "=" * 50)
    print("FILE:", filename)
    print("=" * 50)

    print("Shape:", df.shape)
    print("\nFirst 5 rows:")
    print(df.head())

    print("\nMissing values:")
    print(df.isnull().sum().sum())

    print("\nDuplicate rows:")
    print(df.duplicated().sum())
