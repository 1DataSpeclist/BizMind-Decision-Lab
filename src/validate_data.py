
import pandas as pd
from pathlib import Path

# ==========================================
# 1. LOAD DATASETS
# ==========================================

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "raw"

products = pd.read_csv(DATA_DIR / "products.csv")
suppliers = pd.read_csv(DATA_DIR / "suppliers.csv")
sales = pd.read_csv(DATA_DIR / "sales.csv")
inventory = pd.read_csv(DATA_DIR / "inventory.csv")
purchases = pd.read_csv(DATA_DIR / "purchases.csv")

datasets = {
    "Products": products,
    "Suppliers": suppliers,
    "Sales": sales,
    "Inventory": inventory,
    "Purchases": purchases
}

# ==========================================
# 2. BASIC DATA QUALITY CHECKS
# ==========================================

print("\n========== DATASET OVERVIEW ==========")

for name, df in datasets.items():

    print(f"\n{name}")
    print("-" * 40)

    print("Rows:", df.shape[0])
    print("Columns:", df.shape[1])

    print("Missing values:", df.isnull().sum().sum())
    print("Duplicate rows:", df.duplicated().sum())


# ==========================================
# 3. NUMERICAL VALIDATION
# ==========================================

print("\n========== NUMERICAL VALIDATION ==========")

print(
    "Invalid product prices:",
    (products["cost_price"] <= 0).sum()
)

print(
    "Selling price below cost price:",
    (products["selling_price"] <= products["cost_price"]).sum()
)

print(
    "Negative units sold:",
    (sales["units_sold"] < 0).sum()
)

print(
    "Negative revenue:",
    (sales["revenue"] < 0).sum()
)

print(
    "Negative profit:",
    (sales["profit"] < 0).sum()
)

# ==========================================
# 4. RELATIONSHIP VALIDATION
# ==========================================

print("\n========== RELATIONSHIP VALIDATION ==========")

invalid_product_sales = (
    ~sales["product_id"].isin(products["product_id"])
).sum()

invalid_product_inventory = (
    ~inventory["product_id"].isin(products["product_id"])
).sum()

invalid_product_purchases = (
    ~purchases["product_id"].isin(products["product_id"])
).sum()

invalid_supplier_products = (
    ~products["supplier_id"].isin(suppliers["supplier_id"])
).sum()

invalid_supplier_purchases = (
    ~purchases["supplier_id"].isin(suppliers["supplier_id"])
).sum()

print("Invalid product IDs in sales:", invalid_product_sales)
print("Invalid product IDs in inventory:", invalid_product_inventory)
print("Invalid product IDs in purchases:", invalid_product_purchases)
print("Invalid supplier IDs in products:", invalid_supplier_products)
print("Invalid supplier IDs in purchases:", invalid_supplier_purchases)

# ==========================================
# 5. BUSINESS LOGIC VALIDATION
# ==========================================

print("\n========== BUSINESS LOGIC ==========")

expected_revenue = sales["units_sold"] * sales["selling_price"]

revenue_errors = (
    (sales["revenue"] - expected_revenue).abs() > 0.01
).sum()

expected_profit = sales["revenue"] - sales["cost"]

profit_errors = (
    (sales["profit"] - expected_profit).abs() > 0.01
).sum()

print("Revenue calculation errors:", revenue_errors)
print("Profit calculation errors:", profit_errors)

print(
    "Invalid promotion values:",
    (~sales["promotion"].isin([0, 1])).sum()
)

print(
    "Invalid stockout values:",
    (~sales["stockout"].isin([0, 1])).sum()
)

print(
    "Negative inventory:",
    (inventory["available_stock"] < 0).sum()
)

# ==========================================
# 6. DATE VALIDATION
# ==========================================

sales["sale_date"] = pd.to_datetime(sales["sale_date"])

print("\n========== DATE VALIDATION ==========")

print("First sale date:", sales["sale_date"].min())
print("Last sale date:", sales["sale_date"].max())

print(
    "Duplicate product-date records:",
    sales.duplicated(subset=["product_id", "sale_date"]).sum()
)

# ==========================================
# 7. FINAL REPORT
# ==========================================

print("\n========== VALIDATION COMPLETED ==========")
print("All basic checks have been executed.")
