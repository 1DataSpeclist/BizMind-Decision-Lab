
import numpy as np
import pandas as pd
from pathlib import Path

# --------------------------------------------------
# 1. CONFIGURATION
# --------------------------------------------------

SEED = 42
NUM_PRODUCTS = 50
NUM_SUPPLIERS = 10
NUM_DAYS = 730

rng = np.random.default_rng(SEED)

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

dates = pd.date_range(
    end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1),
    periods=NUM_DAYS,
    freq="D"
)

# --------------------------------------------------
# 2. SUPPLIERS DATASET
# --------------------------------------------------

supplier_names = [
    "Alpha Distributors", "Metro Wholesale",
    "Prime Suppliers", "National Traders",
    "Shree Enterprises", "City Distributors",
    "Reliable Supplies", "Global Wholesale",
    "Smart Traders", "Unity Distributors"
]

suppliers = pd.DataFrame({
    "supplier_id": range(1, NUM_SUPPLIERS + 1),
    "supplier_name": supplier_names,
    "lead_time_days": rng.integers(2, 11, NUM_SUPPLIERS),
    "reliability_score": np.round(
        rng.uniform(0.80, 0.99, NUM_SUPPLIERS), 2
    )
})

# --------------------------------------------------
# 3. PRODUCTS DATASET
# --------------------------------------------------

categories = ["Grocery", "Electronics", "Clothing", "Personal Care", "Stationery"]

product_names = [
    "Rice", "Wheat Flour", "Sugar", "Cooking Oil", "Tea",
    "Coffee", "Biscuits", "Milk Powder", "Salt", "Pulses",
    "Headphones", "Mouse", "Keyboard", "USB Cable", "Power Bank",
    "Charger", "Speaker", "Memory Card", "Webcam", "Calculator",
    "T-Shirt", "Jeans", "Shirt", "Jacket", "Track Pants",
    "Socks", "Belt", "Cap", "Shoes", "Shorts",
    "Shampoo", "Soap", "Toothpaste", "Face Wash", "Hair Oil",
    "Body Lotion", "Deodorant", "Toothbrush", "Hand Wash", "Comb",
    "Notebook", "Pen", "Pencil", "Marker", "Eraser",
    "Ruler", "File Folder", "Stapler", "Glue", "Scissors"
]

products = pd.DataFrame({
    "product_id": range(1, NUM_PRODUCTS + 1),
    "product_name": product_names,
    "category": [categories[i // 10] for i in range(NUM_PRODUCTS)],
    "supplier_id": rng.integers(1, NUM_SUPPLIERS + 1, NUM_PRODUCTS),
    "cost_price": np.round(rng.uniform(10, 1000, NUM_PRODUCTS), 2),
    "selling_price": np.round(rng.uniform(20, 1500, NUM_PRODUCTS), 2),
    "initial_stock": rng.integers(40, 150, NUM_PRODUCTS),
    "minimum_stock": rng.integers(10, 30, NUM_PRODUCTS),
    "minimum_order_quantity": rng.integers(5, 21, NUM_PRODUCTS)
})

# Ensure selling price is greater than cost price
products["selling_price"] = np.round(
    products["cost_price"] * rng.uniform(1.15, 1.70, NUM_PRODUCTS), 2
)

# --------------------------------------------------
# 4. SALES DATASET
# --------------------------------------------------

sales_records = []
inventory_records = []
purchase_records = []

purchase_id = 1

for product in products.itertuples(index=False):

    product_id = product.product_id
    supplier = suppliers.loc[
        suppliers["supplier_id"] == product.supplier_id
    ].iloc[0]

    stock = int(product.initial_stock)

    # Product-specific average daily demand
    base_demand = rng.uniform(2, 15)

    for current_date in dates:

        day_number = current_date.dayofweek
        month = current_date.month

        # Weekend demand effect
        weekend_factor = 1.20 if day_number >= 5 else 1.0

        # Seasonal demand effect
        seasonal_factor = 1 + 0.20 * np.sin(
            2 * np.pi * current_date.dayofyear / 365
        )

        # Random demand fluctuation
        random_factor = rng.uniform(0.70, 1.30)

        # Occasional promotions
        promotion = rng.random() < 0.05
        promotion_factor = 1.25 if promotion else 1.0

        expected_demand = (
            base_demand
            * weekend_factor
            * seasonal_factor
            * random_factor
            * promotion_factor
        )

        demand = max(0, int(round(expected_demand)))

        # Actual sales cannot exceed available stock
        units_sold = min(demand, stock)

        stockout = demand > stock

        revenue = units_sold * product.selling_price
        cost = units_sold * product.cost_price
        profit = revenue - cost

        stock -= units_sold

        sales_records.append({
            "product_id": product_id,
            "sale_date": current_date,
            "units_sold": units_sold,
            "selling_price": product.selling_price,
            "revenue": round(revenue, 2),
            "cost": round(cost, 2),
            "profit": round(profit, 2),
            "promotion": int(promotion),
            "stockout": int(stockout)
        })

        # Reorder when stock reaches minimum level
        if stock <= product.minimum_stock:

            order_quantity = max(
                int(product.minimum_order_quantity),
                int(round(base_demand * supplier["lead_time_days"] * 2))
            )

            order_date = current_date
            arrival_date = order_date + pd.Timedelta(
                days=int(supplier["lead_time_days"])
            )

            purchase_records.append({
                "purchase_id": purchase_id,
                "product_id": product_id,
                "supplier_id": product.supplier_id,
                "order_date": order_date,
                "expected_arrival_date": arrival_date,
                "quantity": order_quantity,
                "purchase_cost": product.cost_price,
                "total_purchase_cost": round(
                    order_quantity * product.cost_price, 2
                ),
                "status": "Received" if arrival_date <= dates[-1] else "Pending"
            })

            purchase_id += 1

            # Simplified replenishment for synthetic data.
            # Actual supplier delays will be modeled separately later.
            stock += order_quantity

    inventory_records.append({
        "product_id": product_id,
        "available_stock": stock,
        "minimum_stock": product.minimum_stock,
        "last_updated": dates[-1]
    })

# --------------------------------------------------
# 5. CREATE DATAFRAMES
# --------------------------------------------------

sales = pd.DataFrame(sales_records)
inventory = pd.DataFrame(inventory_records)
purchases = pd.DataFrame(purchase_records)

# --------------------------------------------------
# 6. SAVE CSV FILES
# --------------------------------------------------

datasets = {
    "products.csv": products,
    "suppliers.csv": suppliers,
    "sales.csv": sales,
    "inventory.csv": inventory,
    "purchases.csv": purchases
}

for filename, dataframe in datasets.items():

    dataframe.to_csv(OUTPUT_DIR / filename, index=False)

    print(
        f"{filename:<20} | "
        f"Rows: {len(dataframe):>7,} | "
        f"Columns: {len(dataframe.columns)}"
    )

print("\nDataset generation completed.")
print(f"Files saved in: {OUTPUT_DIR}")
