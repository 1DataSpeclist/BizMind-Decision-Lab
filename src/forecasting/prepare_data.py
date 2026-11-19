
from pathlib import Path
import os

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv


# Locate the project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load database credentials
load_dotenv(PROJECT_ROOT / ".env")


# Connect to MySQL
database_url = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 3306)),
    database=os.getenv("DB_NAME")
)

engine = create_engine(database_url, pool_pre_ping=True)


def prepare_demand_data():

    query = text("""
        SELECT
            s.product_id,
            p.product_name,
            p.category,
            DATE(s.sale_date) AS sale_date,
            SUM(s.units_sold) AS demand
        FROM sales s
        JOIN products p
            ON s.product_id = p.product_id
        GROUP BY
            s.product_id,
            p.product_name,
            p.category,
            DATE(s.sale_date)
        ORDER BY
            s.product_id,
            sale_date
    """)

    with engine.connect() as connection:
        df = pd.read_sql_query(query, connection)

    # Convert dates into datetime format
    df["sale_date"] = pd.to_datetime(df["sale_date"])

    # Sort records chronologically
    df = df.sort_values(
        ["product_id", "sale_date"]
    ).reset_index(drop=True)

    # Save processed data
    output_dir = PROJECT_ROOT / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "product_daily_demand.csv"

    df.to_csv(output_file, index=False)

    print("Demand data prepared successfully!")
    print(f"Total records: {len(df)}")
    print(f"Unique products: {df['product_id'].nunique()}")
    print(f"Date range: {df['sale_date'].min()} to {df['sale_date'].max()}")
    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    prepare_demand_data()
