"""
Run SQL against CEDARLINE.SERVICE, or one of the built-in sample queries.

Credentials come from environment variables, or from a .env file in the
project root (SNOWFLAKE_PASSWORD or SNOWFLAKE_TOKEN holds the password / access token):
    SNOWFLAKE_ACCOUNT    default UOGGEXS-LY50525
    SNOWFLAKE_USER       default NEELGHOSHAL
    SNOWFLAKE_WAREHOUSE  default COMPUTE_WH
    SNOWFLAKE_ROLE       default ACCOUNTADMIN

Usage:
    python query_snowflake.py --list
    python query_snowflake.py counts
    python query_snowflake.py member M000002
    python query_snowflake.py sql "select * from plans"
"""
import argparse
import os
import sys

import pandas as pd
from snowflake.connector import connect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# name -> (description, SQL with an optional %(member)s parameter)
QUERIES = {
    "counts": (
        "Row count per table",
        """
        select 'PLANS' t, count(*) n from plans union all
        select 'MEMBERS', count(*) from members union all
        select 'ACCUMULATORS', count(*) from accumulators union all
        select 'CLAIMS', count(*) from claims union all
        select 'PRIOR_AUTHS', count(*) from prior_auths union all
        select 'SERVICE_REQUESTS', count(*) from service_requests union all
        select 'INTERACTIONS', count(*) from interactions union all
        select 'CALL_TRANSCRIPTS', count(*) from call_transcripts union all
        select 'CASE_NOTES', count(*) from case_notes
        """,
    ),
    "member": (
        "Profile, plan and deductible progress for a member (arg: MEMBER_ID)",
        """
        select m.member_id, m.name, m.status, p.plan_name, p.deductible, p.oop_max,
               a.deductible_met, a.oop_met, a.as_of
        from members m
        left join plans p using (plan_id)
        left join accumulators a on a.member_id = m.member_id
        where m.member_id = %(member)s
        """,
    ),
    "claims": (
        "Claims for a member, newest first (arg: MEMBER_ID)",
        """
        select claim_id, service_date, provider, billed, member_owes, status, status_reason
        from claims where member_id = %(member)s order by service_date desc
        """,
    ),
    "denials": (
        "Denied claims by reason",
        "select status_reason, count(*) n, round(sum(billed)) billed from claims "
        "where status = 'denied' group by 1 order by n desc",
    ),
    "intents": (
        "Interaction volume by intent (seed story 5)",
        "select intent, count(*) n, round(100 * ratio_to_report(count(*)) over (), 1) pct "
        "from interactions group by 1 order by n desc",
    ),
    "repeat": (
        "Members with 3+ contacts on the same intent in any 7 days",
        """
        select distinct a.member_id, a.intent
        from interactions a join interactions b
          on a.member_id = b.member_id and a.intent = b.intent
         and b.started_at between a.started_at and dateadd(day, 7, a.started_at)
        group by a.member_id, a.intent, a.interaction_id
        having count(*) >= 3
        """,
    ),
    "injections": (
        "Case notes that contain instructions aimed at an AI assistant",
        "select note_id, request_id, text from case_notes "
        "where text ilike '%instruction%' or text ilike '%ignore%'",
    ),
}


def load_dotenv() -> None:
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def connection():
    load_dotenv()
    password = os.environ.get("SNOWFLAKE_PASSWORD") or os.environ.get("SNOWFLAKE_TOKEN")
    if not password:
        sys.exit("Set SNOWFLAKE_PASSWORD (or SNOWFLAKE_TOKEN) in the environment or .env")
    return connect(
        account=os.environ.get("SNOWFLAKE_ACCOUNT", "UOGGEXS-LY50525"),
        user=os.environ.get("SNOWFLAKE_USER", "NEELGHOSHAL"),
        password=password,
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        database="CEDARLINE",
        schema="SERVICE",
    )


def run(sql: str, params: dict | None = None) -> pd.DataFrame:
    conn = connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        cols = [c[0].lower() for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", nargs="?", help="sample query name, or 'sql'")
    ap.add_argument("arg", nargs="?", help="MEMBER_ID for member/claims, or the SQL text for 'sql'")
    ap.add_argument("--list", action="store_true", help="list sample queries")
    args = ap.parse_args()

    if args.list or not args.name:
        for k, (desc, _) in QUERIES.items():
            print(f"  {k:<11} {desc}")
        print("  sql         Run your own SQL: python query_snowflake.py sql \"select ...\"")
        return

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_colwidth", 80)

    if args.name == "sql":
        if not args.arg:
            sys.exit("Usage: python query_snowflake.py sql \"select ...\"")
        print(run(args.arg).to_string(index=False))
        return
    if args.name not in QUERIES:
        sys.exit(f"Unknown query '{args.name}'. Try --list.")
    sql = QUERIES[args.name][1]
    params = None
    if "%(member)s" in sql:
        if not args.arg:
            sys.exit(f"'{args.name}' needs a MEMBER_ID, e.g. M000002")
        params = {"member": args.arg}
    print(run(sql, params).to_string(index=False))


if __name__ == "__main__":
    main()
