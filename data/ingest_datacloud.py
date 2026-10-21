"""
Loads data/datacloud/*.csv into Salesforce Data Cloud (Data 360) via the
Ingestion API bulk path: one job per table (create -> upload CSV -> close).

One-time setup (UI, once):
  1. Setup -> External Client App (or Connected App): enable OAuth, scopes
     api, cdp_ingest_api, cdp_api; enable Client Credentials Flow and set a Run As user.
  2. Data Cloud/Data 360 -> Ingestion API -> New. Name it e.g. cedarline; upload
     datacloud/schema.yaml (create it with: python ingest_datacloud.py schema).
  3. Create one Data Stream per object from that connector, choosing the
     primary key (and event date for engagement tables).
  4. Put these in the project's .env:
        SF_DOMAIN=https://yourorg.my.salesforce.com
        SF_CLIENT_ID=...
        SF_CLIENT_SECRET=...
        DC_SOURCE=cedarline         (the connector's API name)

Usage:
    python ingest_datacloud.py schema            # write datacloud/schema.yaml
    python ingest_datacloud.py load               # load all nine tables
    python ingest_datacloud.py load claims members
"""
import os
import sys
import time

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIR = os.path.join(HERE, "datacloud")
ORDER = ["plans", "members", "accumulators", "claims", "prior_auths",
         "service_requests", "interactions", "call_transcripts", "case_notes"]
DATE_COLS = {"dob", "service_date", "as_of"}
TS_COLS = {"updated_at", "submitted_at", "decided_at", "opened_at", "closed_at",
           "started_at", "created_at"}


def load_dotenv():
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def env(name, default=None):
    v = os.environ.get(name, default)
    if not v:
        sys.exit(f"Missing {name} (set it in .env)")
    return v


def field_type(col, series):
    if col in TS_COLS:
        return "type: string\n          format: date-time"
    if col in DATE_COLS:
        return "type: string\n          format: date"
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series) and col != "plan_year":
        return "type: number"
    return "type: string"  # ids, text, booleans (resolved_flag), zip


def write_schema():
    lines = ["openapi: 3.0.3", "components:", "  schemas:"]
    for name in ORDER:
        df = pd.read_csv(os.path.join(DIR, f"{name}.csv"), dtype={"zip": str})
        lines += [f"    {name}:", "      type: object", "      properties:"]
        for col in df.columns:
            lines += [f"        {col}:", f"          {field_type(col, df[col])}"]
    path = os.path.join(DIR, "schema.yaml")
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("Wrote", path)


def token():
    domain = env("SF_DOMAIN").rstrip("/")
    r = requests.post(f"{domain}/services/oauth2/token", data={
        "grant_type": "client_credentials",
        "client_id": env("SF_CLIENT_ID"), "client_secret": env("SF_CLIENT_SECRET")})
    r.raise_for_status()
    sf = r.json()
    # Exchange the Salesforce token for a Data Cloud token + tenant URL.
    r = requests.post(f"{domain}/services/a360/token", data={
        "grant_type": "urn:salesforce:grant-type:external:cdp",
        "subject_token": sf["access_token"],
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token"})
    r.raise_for_status()
    dc = r.json()
    base = dc["instance_url"]
    return (base if base.startswith("http") else "https://" + base), dc["access_token"]


def load(tables):
    base, tok = token()
    h = {"Authorization": f"Bearer {tok}"}
    source = env("DC_SOURCE", "cedarline")
    for name in tables:
        r = requests.post(f"{base}/api/v1/ingest/jobs", headers=h, json={
            "object": name, "sourceName": source, "operation": "upsert"})
        r.raise_for_status()
        job = r.json()["id"]
        with open(os.path.join(DIR, f"{name}.csv"), "rb") as f:
            requests.put(f"{base}/api/v1/ingest/jobs/{job}/batches",
                         headers={**h, "Content-Type": "text/csv"}, data=f).raise_for_status()
        requests.patch(f"{base}/api/v1/ingest/jobs/{job}", headers=h,
                       json={"state": "UploadComplete"}).raise_for_status()
        for _ in range(60):  # poll up to ~5 min
            state = requests.get(f"{base}/api/v1/ingest/jobs/{job}", headers=h).json().get("state")
            if state in ("JobComplete", "Failed", "Aborted"):
                break
            time.sleep(5)
        print(f"{name:<18} job {job}  {state}")


if __name__ == "__main__":
    load_dotenv()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "schema":
        write_schema()
    elif cmd == "load":
        tables = sys.argv[2:] or ORDER
        bad = [t for t in tables if t not in ORDER]
        if bad:
            sys.exit(f"Unknown table(s): {bad}")
        load(tables)
    else:
        sys.exit(__doc__)
