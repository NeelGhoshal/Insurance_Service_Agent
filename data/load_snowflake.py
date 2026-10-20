"""
Creates the CEDARLINE.SERVICE tables (ddl.sql) and loads the CSVs from data/out/.

Credentials come from environment variables so nothing secret lands in the repo:
    SNOWFLAKE_ACCOUNT    e.g. UOGGEXS-LY50525
    SNOWFLAKE_USER       e.g. NEELGHOSHAL
    SNOWFLAKE_WAREHOUSE  an existing warehouse
    SNOWFLAKE_ROLE       optional, default ACCOUNTADMIN
    SNOWFLAKE_PASSWORD   password, OR set SNOWFLAKE_AUTHENTICATOR=externalbrowser
                         for browser/SSO login (use this if the account enforces MFA)

Usage:
    pip install -r requirements.txt
    python load_snowflake.py
"""
import os
import sys

import pandas as pd
from snowflake.connector import connect
from snowflake.connector.pandas_tools import write_pandas

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
DATABASE = "CEDARLINE"
SCHEMA = "SERVICE"

# (csv filename, table name) in FK-safe load order.
TABLES = [
    ("plans.csv", "PLANS"),
    ("members.csv", "MEMBERS"),
    ("accumulators.csv", "ACCUMULATORS"),
    ("claims.csv", "CLAIMS"),
    ("prior_auths.csv", "PRIOR_AUTHS"),
    ("service_requests.csv", "SERVICE_REQUESTS"),
    ("interactions.csv", "INTERACTIONS"),
    ("call_transcripts.csv", "CALL_TRANSCRIPTS"),
    ("case_notes.csv", "CASE_NOTES"),
]


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return val


def main() -> None:
    kwargs = dict(
        account=require_env("SNOWFLAKE_ACCOUNT"),
        user=require_env("SNOWFLAKE_USER"),
        warehouse=require_env("SNOWFLAKE_WAREHOUSE"),
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    )
    if os.environ.get("SNOWFLAKE_AUTHENTICATOR"):
        kwargs["authenticator"] = os.environ["SNOWFLAKE_AUTHENTICATOR"]
    else:
        kwargs["password"] = require_env("SNOWFLAKE_PASSWORD")

    conn = connect(**kwargs)
    try:
        with open(os.path.join(HERE, "ddl.sql"), encoding="utf-8") as f:
            for cur in conn.execute_string(f.read()):
                cur.close()

        for csv_name, table_name in TABLES:
            df = pd.read_csv(os.path.join(OUT_DIR, csv_name))
            # write_pandas matches columns by name against the existing table.
            df.columns = [c.upper() for c in df.columns]
            success, _, nrows, _ = write_pandas(
                conn, df, table_name, database=DATABASE, schema=SCHEMA
            )
            print(f"{table_name:<18} {nrows:>6} rows  [{'OK' if success else 'FAILED'}]")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
