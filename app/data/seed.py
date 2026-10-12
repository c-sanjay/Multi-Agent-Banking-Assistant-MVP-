"""Create and populate the mock bank database.

Run:  python -m app.data.seed
Deterministic (fixed random seed) so demos and tests are repeatable.
Some suspicious transactions are planted on purpose for the fraud agent.
"""
import random
from datetime import datetime, timedelta

from app import config
from app.db import get_conn

SCHEMA = """
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS loans;
DROP TABLE IF EXISTS devices;

CREATE TABLE customers (
  id TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT, city TEXT,
  home_country TEXT, monthly_income REAL, credit_score INTEGER, kyc_status TEXT
);
CREATE TABLE accounts (
  customer_id TEXT PRIMARY KEY, account_no TEXT, account_type TEXT, balance REAL,
  card_last4 TEXT, card_status TEXT
);
CREATE TABLE transactions (
  id TEXT PRIMARY KEY, customer_id TEXT, ts TEXT, amount REAL, merchant TEXT,
  category TEXT, country TEXT, channel TEXT, device_id TEXT
);
CREATE TABLE loans (
  id TEXT PRIMARY KEY, customer_id TEXT, loan_type TEXT, principal REAL, annual_rate REAL,
  tenure_months INTEGER, emi REAL, outstanding REAL, status TEXT, next_due TEXT
);
CREATE TABLE devices (
  device_id TEXT, customer_id TEXT, label TEXT, city TEXT, country TEXT,
  last_seen TEXT, trusted INTEGER
);
"""

CUSTOMERS = [
    # id, name, email, phone, city, income, credit_score, kyc
    ("C001", "Sanjay", "sanjay@example.com", "9876501234", "Namakkal", 130000, 782, "VERIFIED"),
    ("C002", "Faizal", "faizal@example.com", "9876505678", "Chennai", 85000, 701, "VERIFIED"),
    ("C003", "Harris", "harris@example.com", "9876509012", "Tirupathur", 45000, 612, "VERIFIED"),
    ("C004", "Mukesh", "mukesh@example.com", "9876503456", "Tenkasi", 200000, 815, "VERIFIED"),
    ("C005", "Ragul", "ragul@example.com", "9876507890", "Theni", 60000, 690, "PENDING"),
]

MERCHANTS = [
    ("BigBasket", "groceries", 600, 3500), ("Swiggy", "food", 200, 1200),
    ("Zomato", "food", 200, 1100), ("Amazon India", "shopping", 500, 6000),
    ("Uber", "transport", 150, 900), ("Reliance Fresh", "groceries", 400, 2500),
    ("Netflix", "entertainment", 199, 649), ("Indian Oil", "fuel", 800, 3000),
    ("Apollo Pharmacy", "health", 150, 1800), ("BookMyShow", "entertainment", 300, 1500),
]


def seed() -> None:
    random.seed(42)
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    with get_conn() as conn:
        conn.executescript(SCHEMA)

        txn_no = 1000
        for cid, name, email, phone, city, income, score, kyc in CUSTOMERS:
            conn.execute(
                "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?)",
                (cid, name, email, phone, city, "IN", income, score, kyc),
            )
            acct_no = "50100" + str(random.randint(1000000, 9999999))
            card4 = str(random.randint(1000, 9999))
            balance = round(random.uniform(0.8, 3.5) * income, 2)
            conn.execute(
                "INSERT INTO accounts VALUES (?,?,?,?,?,?)",
                (cid, acct_no, "SAVINGS", balance, card4, "ACTIVE"),
            )
            dev_id = f"DEV-{cid}-1"
            conn.execute(
                "INSERT INTO devices VALUES (?,?,?,?,?,?,?)",
                (dev_id, cid, "Primary phone", city, "IN", now.isoformat(), 1),
            )

            # 50 normal transactions over the last 45 days
            for _ in range(50):
                m, cat, lo, hi = random.choice(MERCHANTS)
                ts = now - timedelta(days=random.randint(1, 45), hours=random.randint(0, 12))
                ts = ts.replace(hour=random.randint(8, 22))
                txn_no += 1
                conn.execute(
                    "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"TXN-{txn_no}", cid, ts.isoformat(), round(random.uniform(lo, hi), 2),
                     m, cat, "IN", random.choice(["UPI", "CARD", "NETBANKING"]), dev_id),
                )

        # ---- Planted suspicious activity for C001 (Sanjay) ------------------
        def add(tid, cid, ts, amt, merch, cat, country, chan, dev):
            conn.execute(
                "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?)",
                (tid, cid, ts.isoformat(), amt, merch, cat, country, chan, dev),
            )

        # Large domestic purchase at 3 AM from an unknown device
        add("TXN-9001", "C001", now - timedelta(hours=14, minutes=0), 48000.0, "Ethos Watches",
            "luxury", "IN", "CARD", "DEV-UNKNOWN-77")
        # Card-testing pattern: repeated small domestic charges
        for i in range(4):
            add(f"TXN-900{2 + i}", "C001", now - timedelta(hours=13, minutes=50 - i * 3), 99.0,
                "Paytm", "digital", "IN", "CARD", "DEV-UNKNOWN-77")
        conn.execute("UPDATE transactions SET ts = ? WHERE id = 'TXN-9001'",
                     ((now - timedelta(days=1)).replace(hour=3, minute=12).isoformat(),))
        conn.execute("UPDATE transactions SET ts = ? WHERE id IN ('TXN-9002','TXN-9003','TXN-9004','TXN-9005')",
                     ((now - timedelta(days=1)).replace(hour=3, minute=20).isoformat(),))
        conn.execute("INSERT INTO devices VALUES (?,?,?,?,?,?,?)",
                     ("DEV-UNKNOWN-77", "C001", "Unrecognised device", "Bengaluru", "IN",
                      (now - timedelta(days=1)).isoformat(), 0))

        # One mildly unusual txn for C003 (high amount, but domestic)
        add("TXN-9101", "C003", now - timedelta(days=2), 21000.0, "Croma Electronics",
            "shopping", "IN", "CARD", "DEV-C003-1")

        # ---- Loans -----------------------------------------------------------
        loans = [
            ("L001", "C001", "HOME", 4500000, 8.5, 180, 44313.0, 4120000, "ACTIVE", "2026-11-05"),
            ("L002", "C002", "PERSONAL", 300000, 12.0, 36, 9964.0, 180000, "ACTIVE", "2026-10-20"),
            ("L003", "C003", "PERSONAL", 200000, 14.5, 24, 9600.0, 150000, "ACTIVE", "2026-10-15"),
            ("L004", "C004", "CAR", 900000, 9.5, 60, 18900.0, 520000, "ACTIVE", "2026-11-02"),
        ]
        conn.executemany("INSERT INTO loans VALUES (?,?,?,?,?,?,?,?,?,?)", loans)
        conn.commit()
    print(f"Seeded {config.DB_PATH} with {len(CUSTOMERS)} customers.")


if __name__ == "__main__":
    seed()
