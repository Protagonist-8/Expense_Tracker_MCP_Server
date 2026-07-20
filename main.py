from fastmcp import FastMCP
import sqlite3
import os
from datetime import datetime

TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "expenses.db")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("Budget Tracker")

def init_db() -> None:
    """Initialize the finance database with expenses and credits tables."""

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()


# Initialize the database when the server starts
init_db()


@mcp.tool()
def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
) -> dict:
    """
    Add a new expense entry to the database.
    """

    if amount <= 0:
        return {
            "status": "error",
            "message": "Amount must be greater than 0."
        }
    created_at = datetime.now().isoformat(timespec="seconds")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO expenses
                (date, amount, category, subcategory, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (date, amount, category, subcategory, note, created_at),
            )

            conn.commit()

            return {
                "status": "success",
                "expense_id": cursor.lastrowid,
                "message": "Expense added successfully."
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@mcp.tool()
def list_expenses(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """
    List expense entries.
    If start_date and end_date are provided, only expenses within the
    inclusive date range are returned. Otherwise, all expenses are returned.
    """

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if start_date and end_date:
                cursor.execute(
                    """
                    SELECT
                        id,
                        date,
                        amount,
                        category,
                        subcategory,
                        note,
                        created_at
                    FROM expenses
                    WHERE date BETWEEN ? AND ?
                    ORDER BY date ASC, id ASC
                    """,
                    (start_date, end_date),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        id,
                        date,
                        amount,
                        category,
                        subcategory,
                        note,
                        created_at
                    FROM expenses
                    ORDER BY date ASC, id ASC
                    """
                )

            return [dict(row) for row in cursor.fetchall()]

    except Exception as e:
        return [
            {
                "status": "error",
                "message": str(e),
            }
        ]


@mcp.tool()
def update_expense(
    expense_id: int,
    date: str | None = None,
    amount: float | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    note: str | None = None,
) -> dict:
    """
    Update an existing expense.
    Only the supplied fields are updated.
    """

    try:
        updates = []
        values = []

        if date is not None:
            updates.append("date = ?")
            values.append(date)

        if amount is not None:
            if amount <= 0:
                return {
                    "status": "error",
                    "message": "Amount must be greater than 0."
                }
            updates.append("amount = ?")
            values.append(amount)

        if category is not None:
            updates.append("category = ?")
            values.append(category)

        if subcategory is not None:
            updates.append("subcategory = ?")
            values.append(subcategory)

        if note is not None:
            updates.append("note = ?")
            values.append(note)

        if not updates:
            return {
                "status": "error",
                "message": "No fields provided to update."
            }

        values.append(expense_id)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(
                f"""
                UPDATE expenses
                SET {", ".join(updates)}
                WHERE id = ?
                """,
                values,
            )

            conn.commit()

            if cursor.rowcount == 0:
                return {
                    "status": "error",
                    "message": f"Expense with ID {expense_id} not found."
                }

            return {
                "status": "success",
                "message": "Expense updated successfully."
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@mcp.tool()
def delete_expense(expense_id: int) -> dict:
    """
    Delete an expense by its ID.
    """

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM expenses
                WHERE id = ?
                """,
                (expense_id,),
            )

            conn.commit()

            if cursor.rowcount == 0:
                return {
                    "status": "error",
                    "message": f"Expense with ID {expense_id} not found."
                }

            return {
                "status": "success",
                "message": f"Expense with ID {expense_id} deleted successfully."
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@mcp.tool()
def generate_budget_report(
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """
    Generate an Excel budget report containing:
      - Summary
      - Expenses

    If no dates are provided, all expenses are included.
    """

    try:
        with sqlite3.connect(DB_PATH) as conn:

            if start_date and end_date:
                query = """
                    SELECT
                        id,
                        date,
                        amount,
                        category,
                        subcategory,
                        note,
                        created_at
                    FROM expenses
                    WHERE date BETWEEN ? AND ?
                    ORDER BY date ASC, id ASC
                """

                expenses_df = pd.read_sql_query(
                    query,
                    conn,
                    params=(start_date, end_date),
                )

            else:
                query = """
                    SELECT
                        id,
                        date,
                        amount,
                        category,
                        subcategory,
                        note,
                        created_at
                    FROM expenses
                    ORDER BY date ASC, id ASC
                """

                expenses_df = pd.read_sql_query(query, conn)

        total_expense = (
            float(expenses_df["amount"].sum())
            if not expenses_df.empty
            else 0.0
        )

        total_transactions = len(expenses_df)

        average_expense = (
            float(expenses_df["amount"].mean())
            if not expenses_df.empty
            else 0.0
        )

        largest_expense = (
            float(expenses_df["amount"].max())
            if not expenses_df.empty
            else 0.0
        )

        summary_df = pd.DataFrame(
            {
                "Metric": [
                    "Total Expense",
                    "Total Transactions",
                    "Average Expense",
                    "Largest Expense",
                ],
                "Value": [
                    total_expense,
                    total_transactions,
                    round(average_expense, 2),
                    largest_expense,
                ],
            }
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(
            REPORTS_DIR,
            f"Budget_Report_{timestamp}.xlsx",
        )

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            summary_df.to_excel(
                writer,
                sheet_name="Summary",
                index=False,
            )

            expenses_df.to_excel(
                writer,
                sheet_name="Expenses",
                index=False,
            )

        return {
            "status": "success",
            "file_path": file_path,
            "message": "Budget report generated successfully.",
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@mcp.resource(
    "expense://categories",
    mime_type="application/json",
)
def get_categories() -> str:
    """
    Returns the available expense categories and subcategories.
    """

    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    mcp.run(transport="http", host = "0.0.0.0", port = 8000)