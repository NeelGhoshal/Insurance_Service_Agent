"""
Writes Data Cloud-ready copies of data/out/*.csv to data/datacloud/.

Differences from data/out/: timestamps become ISO-8601 UTC (YYYY-MM-DDTHH:MM:SS.000Z),
booleans become true/false. Dates (YYYY-MM-DD) and everything else are unchanged.

Usage:
    python export_datacloud.py
"""
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SRC, DST = os.path.join(HERE, "out"), os.path.join(HERE, "datacloud")
os.makedirs(DST, exist_ok=True)

TIMESTAMPS = {
    "claims": ["updated_at"],
    "prior_auths": ["submitted_at", "decided_at"],
    "service_requests": ["opened_at", "closed_at"],
    "interactions": ["started_at"],
    "case_notes": ["created_at"],
}
BOOLEANS = {"interactions": ["resolved_flag"]}
INTEGERS = {"interactions": ["csat"]}  # nullable ints: avoid "5.0"

for fname in sorted(os.listdir(SRC)):
    if not fname.endswith(".csv"):
        continue
    name = fname[:-4]
    df = pd.read_csv(os.path.join(SRC, fname))
    for col in TIMESTAMPS.get(name, []):
        df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    for col in BOOLEANS.get(name, []):
        df[col] = df[col].astype(str).str.lower()
    for col in INTEGERS.get(name, []):
        df[col] = df[col].astype("Int64")
    df.to_csv(os.path.join(DST, fname), index=False)
    print(f"{fname:<24} {len(df):>6} rows")
