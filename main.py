
import os
import calendar
from datetime import date, timedelta

from flask import Flask, render_template, request, redirect, url_for
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

from src.forecasting.forecast_service import generate_forecast


load_dotenv()


app = Flask(
    __name__,
    template_folder="app/templates",
    static_folder="app/static"
)


database_url = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 3306)),
    database=os.getenv("DB_NAME")
)


engine = create_engine(
    database_url,
    pool_pre_ping=True
)


# ============================================================
# DATABASE CONNECTION TEST
# ============================================================

@app.route("/test-db")
def test_database():

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT DATABASE()")
            ).scalar()

        return f"Database connected successfully: {result}"

    except Exception:
        app.logger.exception("Database connection failed")
        return "Database connection failed. Check the terminal."


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
def home():

    today = date.today()
    selected_period = request.args.get("period", "today").lower()

    def subtract_months(value, months):

        month_index = value.month - 1 - months
        year = value.year + month_index // 12
        month = month_index % 12 + 1

        day = min(
            value.day,
            calendar.monthrange(year, month)[1]
        )

        return date(year, month, day)

    period_labels = {
        "today": "Today",
        "yesterday": "Yesterday",
        "7_days": "Last 7 Days",
        "30_days": "Last 30 Days",
        "3_months": "Last 3 Months",
        "6_months": "Last 6 Months",
        "1_year": "Last 1 Year",
        "custom": "Custom Date Range"
    }

    if selected_period not in period_labels:
        selected_period = "today"

    filter_error = None

    if selected_period == "yesterday":

        start_date = today - timedelta(days=1)
        end_date = start_date

    elif selected_period == "7_days":

        start_date = today - timedelta(days=6)
        end_date = today

    elif selected_period == "30_days":

        start_date = today - timedelta(days=29)
        end_date = today

    elif selected_period == "3_months":

        start_date = subtract_months(today, 3)
        end_date = today

    elif selected_period == "6_months":

        start_date = subtract_months(today, 6)
        end_date = today

    elif selected_period == "1_year":

        start_date = subtract_months(today, 12)
        end_date = today

    elif selected_period == "custom":

        start_input = request.args.get("start_date", "")
        end_input = request.args.get("end_date", "")

        try:

            start_date = date.fromisoformat(start_input)
            end_date = date.fromisoformat(end_input)

            if start_date > end_date:
                raise ValueError

            if end_date > today:
                raise ValueError

        except (TypeError, ValueError):

            filter_error = (
                "Enter a valid date range. "
                "The end date cannot be in the future."
            )

            selected_period = "today"
            start_date = today
            end_date = today

    else:

        start_date = today
        end_date = today

    with engine.connect() as connection:

        stats = connection.execute(
            text("""
                SELECT
                    COALESCE(SUM(revenue), 0) AS total_revenue,
                    COALESCE(SUM(profit), 0) AS total_profit,
                    COALESCE(SUM(units_sold), 0) AS total_units_sold
                FROM sales
                WHERE sale_date >= :start_date
                  AND sale_date < DATE_ADD(:end_date, INTERVAL 1 DAY)
            """),
            {
                "start_date": start_date,
                "end_date": end_date
            }
        ).mappings().one()

        reorder_count = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM inventory
                WHERE available_stock <= minimum_stock
            """)
        ).scalar_one()

        stats = dict(stats)
        stats["products_requiring_reorder"] = reorder_count

        data_period = connection.execute(
            text("""
                SELECT
                    MIN(sale_date) AS data_min_date,
                    MAX(sale_date) AS data_max_date
                FROM sales
            """)
        ).mappings().one()

    return render_template(
        "index.html",
        stats=stats,
        selected_period=selected_period,
        period_label=period_labels[selected_period],
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        today=today.isoformat(),
        data_min_date=data_period["data_min_date"],
        data_max_date=data_period["data_max_date"],
        filter_error=filter_error
    )


# ============================================================
# FORECASTING
# ============================================================

@app.route("/forecasting")
def forecasting():

    selected_product = None
    forecast = None
    forecast_error = None

    product_id = request.args.get("product_id", type=int)

    with engine.connect() as connection:

        products = connection.execute(text("""
            SELECT
                product_id,
                product_name,
                category
            FROM products
            ORDER BY product_name
        """)).mappings().all()

        if product_id is not None:

            selected_product = connection.execute(text("""
                SELECT
                    product_id,
                    product_name,
                    category
                FROM products
                WHERE product_id = :product_id
            """), {
                "product_id": product_id
            }).mappings().first()

    if product_id is not None:

        if selected_product is None:
            return "Product not found", 404

        try:

            forecast = generate_forecast(
                product_id=product_id,
                days=7
            )

        except Exception:

            app.logger.exception("Forecast generation failed")

            forecast_error = (
                "Unable to generate forecast. "
                "Check the application terminal."
            )

    return render_template(
        "forecasting.html",
        products=products,
        selected_product=selected_product,
        forecast=forecast,
        forecast_error=forecast_error
    )


# ============================================================
# BUSINESS ANALYTICS
# ============================================================

@app.route("/analytics")
def analytics():

    today = date.today()

    filter_mode = request.args.get(
        "mode",
        "single"
    ).lower()

    if filter_mode not in ("single", "range"):
        filter_mode = "single"

    filter_error = None

    analysis_date = request.args.get(
        "analysis_date",
        today.isoformat()
    )

    start_input = request.args.get(
        "start_date",
        today.isoformat()
    )

    end_input = request.args.get(
        "end_date",
        today.isoformat()
    )

    try:

        if filter_mode == "single":

            selected_date = date.fromisoformat(analysis_date)

            if selected_date > today:
                raise ValueError

            start_date = selected_date
            end_date = selected_date

            selected_period = (
                f"Single day: {selected_date.isoformat()}"
            )

        else:

            start_date = date.fromisoformat(start_input)
            end_date = date.fromisoformat(end_input)

            if start_date > end_date or end_date > today:
                raise ValueError

            selected_period = (
                f"{start_date.isoformat()} to "
                f"{end_date.isoformat()}"
            )

    except (TypeError, ValueError):

        filter_error = (
            "Enter a valid date. The start date must not be "
            "after the end date, and future dates are not allowed."
        )

        filter_mode = "single"
        analysis_date = today.isoformat()

        start_date = today
        end_date = today

        selected_period = f"Today: {today.isoformat()}"

    with engine.connect() as connection:

        data_period = connection.execute(text("""
            SELECT
                MIN(DATE(sale_date)) AS data_min_date,
                MAX(DATE(sale_date)) AS data_max_date
            FROM sales
        """)).mappings().one()

        products = connection.execute(text("""
            SELECT
                p.product_id,
                p.product_name,
                p.category,
                COALESCE(SUM(s.units_sold), 0) AS total_units_sold,
                COALESCE(SUM(s.revenue), 0) AS total_revenue,
                COALESCE(SUM(s.profit), 0) AS total_profit,
                COALESCE(
                    ROUND(
                        SUM(s.profit) /
                        NULLIF(SUM(s.revenue), 0) * 100,
                        2
                    ),
                    0
                ) AS profit_margin

            FROM products p

            JOIN sales s
                ON p.product_id = s.product_id

            WHERE s.sale_date >= :start_date
              AND s.sale_date < DATE_ADD(:end_date, INTERVAL 1 DAY)

            GROUP BY
                p.product_id,
                p.product_name,
                p.category

            ORDER BY total_revenue DESC

            LIMIT 10

        """), {
            "start_date": start_date,
            "end_date": end_date
        }).mappings().all()

        category_rows = connection.execute(text("""
            SELECT
                p.category,
                COALESCE(SUM(s.revenue), 0) AS total_revenue,
                COALESCE(SUM(s.profit), 0) AS total_profit,
                COALESCE(SUM(s.units_sold), 0) AS total_units

            FROM products p

            JOIN sales s
                ON p.product_id = s.product_id

            WHERE s.sale_date >= :start_date
              AND s.sale_date < DATE_ADD(:end_date, INTERVAL 1 DAY)

            GROUP BY p.category

            ORDER BY total_revenue DESC

        """), {
            "start_date": start_date,
            "end_date": end_date
        }).mappings().all()

    categories = [

        {
            "category": row["category"],
            "total_revenue": float(row["total_revenue"] or 0),
            "total_profit": float(row["total_profit"] or 0),
            "total_units": int(row["total_units"] or 0)
        }

        for row in category_rows

    ]

    return render_template(
        "analytics.html",
        products=products,
        categories=categories,
        filter_mode=filter_mode,
        analysis_date=analysis_date,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        selected_period=selected_period,
        data_min_date=(
            data_period["data_min_date"].isoformat()
            if data_period["data_min_date"]
            else ""
        ),
        data_max_date=(
            data_period["data_max_date"].isoformat()
            if data_period["data_max_date"]
            else ""
        ),
        today=today.isoformat(),
        filter_error=filter_error
    )


# ============================================================
# INVENTORY MANAGEMENT
# ============================================================

@app.route("/inventory")
def inventory():

    with engine.connect() as connection:

        products = connection.execute(text("""
            SELECT
                p.product_id,
                p.product_name,
                p.category,
                i.available_stock,
                i.minimum_stock,
                p.minimum_order_quantity,

                ROUND(
                    COALESCE(SUM(s.units_sold), 0) / 30,
                    2
                ) AS avg_daily_demand,

                CASE
                    WHEN COALESCE(SUM(s.units_sold), 0) = 0
                        THEN NULL
                    ELSE ROUND(
                        i.available_stock /
                        (SUM(s.units_sold) / 30),
                        1
                    )
                END AS days_remaining

            FROM products p

            JOIN inventory i
                ON p.product_id = i.product_id

            LEFT JOIN sales s
                ON p.product_id = s.product_id
                AND s.sale_date >= CURDATE() - INTERVAL 30 DAY

            GROUP BY
                p.product_id,
                p.product_name,
                p.category,
                i.available_stock,
                i.minimum_stock,
                p.minimum_order_quantity

            ORDER BY i.available_stock ASC

        """)).mappings().all()

    return render_template(
        "inventory.html",
        products=products
    )


# ============================================================
# INVENTORY OPTIMIZATION
# ============================================================

@app.route("/optimization")
def optimization():

    with engine.connect() as connection:

        products = connection.execute(text("""
            SELECT
                p.product_id,
                p.product_name,
                p.category,
                p.minimum_order_quantity,
                i.available_stock,
                i.minimum_stock,

                COALESCE(
                    SUM(
                        CASE
                            WHEN s.sale_date >=
                                CURDATE() - INTERVAL 30 DAY
                            THEN s.units_sold
                            ELSE 0
                        END
                    ),
                    0
                ) AS units_sold_30_days

            FROM products p

            JOIN inventory i
                ON p.product_id = i.product_id

            LEFT JOIN sales s
                ON p.product_id = s.product_id

            GROUP BY
                p.product_id,
                p.product_name,
                p.category,
                p.minimum_order_quantity,
                i.available_stock,
                i.minimum_stock

            ORDER BY p.product_name

        """)).mappings().all()

    recommendations = []

    for product in products:

        average_daily_demand = (
            float(product["units_sold_30_days"] or 0) / 30
        )

        available_stock = int(
            product["available_stock"] or 0
        )

        minimum_stock = int(
            product["minimum_stock"] or 0
        )

        minimum_order_quantity = max(
            1,
            int(product["minimum_order_quantity"] or 1)
        )

        target_stock = max(
            minimum_stock,
            average_daily_demand * 14
        )

        required_quantity = max(
            0,
            target_stock - available_stock
        )

        if required_quantity > 0:

            recommended_quantity = (
                int(
                    (
                        required_quantity
                        + minimum_order_quantity
                        - 1
                    )
                    // minimum_order_quantity
                )
                * minimum_order_quantity
            )

        else:

            recommended_quantity = 0

        if available_stock <= minimum_stock:

            status = "Urgent Reorder"

        elif recommended_quantity > 0:

            status = "Replenishment Suggested"

        else:

            status = "Sufficient Stock"

        recommendations.append({

            "product_id": product["product_id"],
            "product_name": product["product_name"],
            "category": product["category"],
            "available_stock": available_stock,
            "minimum_stock": minimum_stock,

            "average_daily_demand": round(
                average_daily_demand,
                2
            ),

            "target_stock": round(
                target_stock,
                2
            ),

            "recommended_quantity": recommended_quantity,
            "minimum_order_quantity": minimum_order_quantity,
            "status": status

        })

    return render_template(
        "optimization.html",
        recommendations=recommendations
    )


# ============================================================
# WHAT-IF SIMULATOR
# ============================================================

@app.route("/simulator", methods=["GET", "POST"])
def simulator():

    result = None
    error = None

    selected_product_id = ""
    selling_price_input = ""
    cost_price_input = ""
    demand_change_input = "0"

    # Always initialize products so the dropdown has data
    # on both GET and POST requests.
    products = []

    try:

        with engine.connect() as connection:

            # Fetch the product list once per request.
            products = connection.execute(text("""
                SELECT
                    product_id,
                    product_name
                FROM products
                ORDER BY product_name
            """)).mappings().all()

            if request.method == "POST":

                selected_product_id = request.form.get(
                    "product_id", ""
                ).strip()

                selling_price_input = request.form.get(
                    "selling_price", ""
                ).strip()

                cost_price_input = request.form.get(
                    "cost_price", ""
                ).strip()

                demand_change_input = request.form.get(
                    "demand_change", "0"
                ).strip()

                # ------------------------------------------------
                # INPUT VALIDATION
                # ------------------------------------------------

                if not selected_product_id:
                    raise ValueError("Please select a product.")

                try:
                    product_id = int(selected_product_id)
                except (TypeError, ValueError):
                    raise ValueError("Invalid product selection.")

                try:
                    new_selling_price = float(selling_price_input)
                    new_cost_price = float(cost_price_input)
                    demand_change = float(demand_change_input)
                except (TypeError, ValueError):
                    raise ValueError(
                        "Enter valid numeric values for prices and demand change."
                    )

                if new_selling_price <= 0:
                    raise ValueError(
                        "Selling price must be greater than zero."
                    )

                if new_cost_price < 0:
                    raise ValueError(
                        "Cost price cannot be negative."
                    )

                if demand_change < -100 or demand_change > 500:
                    raise ValueError(
                        "Demand change must be between -100% and 500%."
                    )

                # ------------------------------------------------
                # FETCH PRODUCT, STOCK AND LAST 30 DAYS SALES
                # ------------------------------------------------

                product = connection.execute(text("""
                    SELECT
                        p.product_id,
                        p.product_name,
                        p.selling_price,
                        p.cost_price,
                        i.available_stock,

                        COALESCE(d.units_sold, 0)
                            AS units_sold_30_days

                    FROM products p

                    INNER JOIN inventory i
                        ON p.product_id = i.product_id

                    LEFT JOIN (
                        SELECT
                            product_id,
                            SUM(units_sold) AS units_sold

                        FROM sales

                        WHERE sale_date >=
                            CURDATE() - INTERVAL 29 DAY
                          AND sale_date < CURDATE() + INTERVAL 1 DAY

                        GROUP BY product_id

                    ) d
                        ON p.product_id = d.product_id

                    WHERE p.product_id = :product_id

                """), {
                    "product_id": product_id
                }).mappings().first()

                if product is None:
                    raise ValueError(
                        "Selected product was not found."
                    )

                # ------------------------------------------------
                # CURRENT PRODUCT VALUES
                # ------------------------------------------------

                current_selling_price = float(
                    product["selling_price"]
                )

                current_cost_price = float(
                    product["cost_price"]
                )

                available_stock = int(
                    product["available_stock"]
                )

                units_sold_30_days = int(
                    product["units_sold_30_days"] or 0
                )

                if available_stock < 0:
                    raise ValueError(
                        "Invalid inventory stock value."
                    )

                # ------------------------------------------------
                # BASELINE DEMAND
                # ------------------------------------------------

                baseline_demand = units_sold_30_days

                average_daily_demand = (
                    baseline_demand / 30
                )

                # ------------------------------------------------
                # SCENARIO DEMAND
                # ------------------------------------------------

                scenario_demand = (
                    baseline_demand *
                    (1 + demand_change / 100)
                )

                scenario_demand_units = int(
                    scenario_demand + 0.5
                )

                # ------------------------------------------------
                # APPLY STOCK CONSTRAINT
                # ------------------------------------------------

                baseline_units = min(
                    baseline_demand,
                    available_stock
                )

                scenario_units = min(
                    scenario_demand_units,
                    available_stock
                )

                # ------------------------------------------------
                # BASELINE FINANCIAL CALCULATIONS
                # ------------------------------------------------

                baseline_revenue = (
                    baseline_units * current_selling_price
                )

                baseline_cost = (
                    baseline_units * current_cost_price
                )

                baseline_profit = (
                    baseline_revenue - baseline_cost
                )

                # ------------------------------------------------
                # SCENARIO FINANCIAL CALCULATIONS
                # ------------------------------------------------

                scenario_revenue = (
                    scenario_units * new_selling_price
                )

                scenario_cost = (
                    scenario_units * new_cost_price
                )

                scenario_profit = (
                    scenario_revenue - scenario_cost
                )

                # ------------------------------------------------
                # BUSINESS IMPACT
                # ------------------------------------------------

                profit_difference = (
                    scenario_profit - baseline_profit
                )

                remaining_stock = (
                    available_stock - scenario_units
                )

                unfulfilled_demand = max(
                    0,
                    scenario_demand - scenario_units
                )

                # ------------------------------------------------
                # RESULT
                # ------------------------------------------------

                result = {

                    "product_name": product["product_name"],

                    "available_stock": available_stock,

                    "units_sold_30_days": units_sold_30_days,

                    "average_daily_demand": round(
                        average_daily_demand, 2
                    ),

                    "current_selling_price": current_selling_price,

                    "current_cost_price": current_cost_price,

                    "new_selling_price": new_selling_price,

                    "new_cost_price": new_cost_price,

                    "demand_change": demand_change,

                    "baseline_demand": baseline_demand,

                    "scenario_demand": round(
                        scenario_demand, 2
                    ),

                    "baseline_units": baseline_units,

                    "scenario_units": scenario_units,

                    "baseline_revenue": round(
                        baseline_revenue, 2
                    ),

                    "scenario_revenue": round(
                        scenario_revenue, 2
                    ),

                    "baseline_profit": round(
                        baseline_profit, 2
                    ),

                    "scenario_profit": round(
                        scenario_profit, 2
                    ),

                    "profit_difference": round(
                        profit_difference, 2
                    ),

                    "remaining_stock": remaining_stock,

                    "unfulfilled_demand": round(
                        unfulfilled_demand, 2
                    )

                }

    except (ValueError, TypeError, KeyError) as exc:

        error = str(exc)

    except Exception:

        app.logger.exception(
            "What-if simulation failed"
        )

        error = (
            "Unable to run simulation due to a database "
            "or application error. Check the terminal."
        )

    return render_template(
        "simulator.html",
        products=products,
        result=result,
        error=error,
        selected_product_id=selected_product_id,
        selling_price_input=selling_price_input,
        cost_price_input=cost_price_input,
        demand_change_input=demand_change_input
    )


# ============================================================
# DATA MANAGEMENT
# ============================================================

@app.route("/data-management", methods=["GET", "POST"])
def data_management():

    message = None
    error = None
    today = date.today()

    # Create transaction history table if it does not exist.
    with engine.begin() as connection:

        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS bizmind_transactions (
                transaction_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                transaction_type VARCHAR(20) NOT NULL,
                quantity INT NOT NULL,
                transaction_date DATE NOT NULL,
                unit_price DECIMAL(12,2) DEFAULT 0,
                total_amount DECIMAL(14,2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

    if request.method == "POST":

        action = request.form.get("action", "")

        try:

            product_id = int(request.form.get("product_id", ""))
            quantity = int(request.form.get("quantity", ""))

            transaction_date = date.fromisoformat(
                request.form.get("transaction_date", "")
            )

            if quantity <= 0:
                raise ValueError(
                    "Quantity must be greater than zero."
                )

            if transaction_date > today:
                raise ValueError(
                    "Future dates are not allowed."
                )

            with engine.begin() as connection:

                product = connection.execute(text("""
                    SELECT
                        product_id,
                        product_name,
                        selling_price,
                        cost_price
                    FROM products
                    WHERE product_id = :product_id
                    FOR UPDATE
                """), {
                    "product_id": product_id
                }).mappings().first()

                if product is None:
                    raise ValueError("Product not found.")

                inventory = connection.execute(text("""
                    SELECT available_stock
                    FROM inventory
                    WHERE product_id = :product_id
                    FOR UPDATE
                """), {
                    "product_id": product_id
                }).mappings().first()

                if inventory is None:
                    raise ValueError("Inventory record not found.")

                # ------------------------------------------------
                # ADD SALE
                # ------------------------------------------------

                if action == "add_sale":

                    available_stock = int(
                        inventory["available_stock"]
                    )

                    if quantity > available_stock:
                        raise ValueError(
                            "Sale quantity cannot exceed available stock."
                        )

                    unit_price = float(product["selling_price"])
                    unit_cost = float(product["cost_price"])

                    revenue = quantity * unit_price
                    total_cost = quantity * unit_cost
                    profit = revenue - total_cost

                    connection.execute(text("""
                        INSERT INTO sales (
                            product_id,
                            sale_date,
                            units_sold,
                            selling_price,
                            revenue,
                            cost,
                            profit
                        )
                        VALUES (
                            :product_id,
                            :sale_date,
                            :units_sold,
                            :selling_price,
                            :revenue,
                            :cost,
                            :profit
                        )
                    """), {
                        "product_id": product_id,
                        "sale_date": transaction_date,
                        "units_sold": quantity,
                        "selling_price": unit_price,
                        "revenue": revenue,
                        "cost": total_cost,
                        "profit": profit
                    })

                    connection.execute(text("""
                        UPDATE inventory
                        SET available_stock = available_stock - :quantity
                        WHERE product_id = :product_id
                    """), {
                        "quantity": quantity,
                        "product_id": product_id
                    })

                    connection.execute(text("""
                        INSERT INTO bizmind_transactions (
                            product_id,
                            transaction_type,
                            quantity,
                            transaction_date,
                            unit_price,
                            total_amount
                        )
                        VALUES (
                            :product_id,
                            'SALE',
                            :quantity,
                            :transaction_date,
                            :unit_price,
                            :total_amount
                        )
                    """), {
                        "product_id": product_id,
                        "quantity": quantity,
                        "transaction_date": transaction_date,
                        "unit_price": unit_price,
                        "total_amount": revenue
                    })

                    message = (
                        "Sale recorded and inventory updated successfully."
                    )

                # ------------------------------------------------
                # RECEIVE STOCK
                # ------------------------------------------------

                elif action == "receive_stock":

                    unit_price = float(
                        request.form.get("unit_price", "0") or 0
                    )

                    if unit_price < 0:
                        raise ValueError(
                            "Purchase price cannot be negative."
                        )

                    connection.execute(text("""
                        UPDATE inventory
                        SET available_stock = available_stock + :quantity
                        WHERE product_id = :product_id
                    """), {
                        "quantity": quantity,
                        "product_id": product_id
                    })

                    connection.execute(text("""
                        INSERT INTO bizmind_transactions (
                            product_id,
                            transaction_type,
                            quantity,
                            transaction_date,
                            unit_price,
                            total_amount
                        )
                        VALUES (
                            :product_id,
                            'STOCK RECEIVED',
                            :quantity,
                            :transaction_date,
                            :unit_price,
                            :total_amount
                        )
                    """), {
                        "product_id": product_id,
                        "quantity": quantity,
                        "transaction_date": transaction_date,
                        "unit_price": unit_price,
                        "total_amount": quantity * unit_price
                    })

                    message = (
                        "Stock received and inventory updated successfully."
                    )

                else:

                    raise ValueError(
                        "Invalid transaction type."
                    )

        except (ValueError, TypeError):

            error = (
                "Invalid input. Check the product, quantity, "
                "price and date."
            )

        except Exception:

            app.logger.exception(
                "Data management transaction failed"
            )

            error = (
                "Transaction failed. Check the application terminal."
            )

        if error is None:

            return redirect(
                url_for(
                    "data_management",
                    success="1"
                )
            )

    if request.args.get("success") == "1":

        message = "Transaction saved successfully."

    with engine.connect() as connection:

        products = connection.execute(text("""
            SELECT
                p.product_id,
                p.product_name,
                p.category,
                p.selling_price,
                p.cost_price,
                i.available_stock
            FROM products p
            JOIN inventory i
                ON p.product_id = i.product_id
            ORDER BY p.product_name
        """)).mappings().all()

        transactions = connection.execute(text("""
            SELECT
                t.transaction_id,
                p.product_name,
                t.transaction_type,
                t.quantity,
                t.transaction_date,
                t.unit_price,
                t.total_amount,
                t.created_at
            FROM bizmind_transactions t
            JOIN products p
                ON t.product_id = p.product_id
            ORDER BY t.created_at DESC
            LIMIT 100
        """)).mappings().all()

    return render_template(
        "data_management.html",
        products=products,
        transactions=transactions,
        today=today.isoformat(),
        message=message,
        error=error
    )


# ============================================================
# RUN FLASK APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(debug=True)
