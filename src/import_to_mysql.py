
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# ==========================================
# 1. DATABASE CONFIGURATION
# ==========================================

DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "sqlorwot"
DB_NAME = "bizmind_db"

# ==========================================
# 2. PROJECT PATHS
# ==========================================

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "raw"

# ==========================================
# 3. CONNECT TO MYSQL
# ==========================================

connection_url = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME
)

engine = create_engine(connection_url)

try:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    print("MySQL connection successful!")

except Exception as error:
    print("Database connection failed!")
    print(error)
    raise SystemExit(1)

# ==========================================
# 4. LOAD CSV FILES
# ==========================================

print("\nLoading CSV datasets...")

products = pd.read_csv(DATA_DIR / "products.csv")
suppliers = pd.read_csv(DATA_DIR / "suppliers.csv")
sales = pd.read_csv(DATA_DIR / "sales.csv")
inventory = pd.read_csv(DATA_DIR / "inventory.csv")
purchases = pd.read_csv(DATA_DIR / "purchases.csv")

# Convert dates to proper date values
sales["sale_date"] = pd.to_datetime(sales["sale_date"]).dt.date

inventory["last_updated"] = pd.to_datetime(
    inventory["last_updated"]
).dt.date

purchases["order_date"] = pd.to_datetime(
    purchases["order_date"]
).dt.date

purchases["expected_arrival_date"] = pd.to_datetime(
    purchases["expected_arrival_date"]
).dt.date

# ==========================================
# 5. PREPARE IMPORT ORDER
# ==========================================

datasets = {
    "suppliers": suppliers,
    "products": products,
    "sales": sales,
    "inventory": inventory,
    "purchases": purchases
}

# ==========================================
# 6. IMPORT INTO MYSQL
# ==========================================

try:

    with engine.begin() as connection:

        # Clear previous synthetic data.
        # Child tables must be cleared before parent tables.
        print("\nClearing previous imported data...")

        delete_order = [
            "purchases",
            "sales",
            "inventory",
            "products",
            "suppliers"
        ]

        for table in delete_order:
            connection.execute(
                text(f"DELETE FROM {table}")
            )

        # Insert records in foreign-key dependency order
        for table_name, dataframe in datasets.items():

            dataframe.to_sql(
                name=table_name,
                con=connection,
                if_exists="append",
                index=False,
                chunksize=1000
            )

            print(
                f"{table_name:<15} "
                f"| {len(dataframe):,} records imported"
            )

    print("\nAll datasets imported successfully!")

except Exception as error:

    print("\nData import failed!")
    print(error)
    raise

finally:
    engine.dispose()
