"""
Writes Agentforce Data Library-ready TXT files from data/datacloud/*.csv to
"salesforce data library/" in the project root.

Each record becomes one self-contained paragraph (the Data Library chunks files for
search, so every chunk must make sense alone). Members are joined with their plan
and accumulators; other records carry the member's name. Files over ~3.5MB are split
into parts to stay under the 4MB TXT limit.

Usage:
    python export_datalibrary.py
"""
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "datacloud")
DST = os.path.join(os.path.dirname(HERE), "salesforce data library")
MAX_BYTES = 3_500_000
os.makedirs(DST, exist_ok=True)


def read(name):
    return pd.read_csv(os.path.join(SRC, f"{name}.csv"), dtype=str, keep_default_na=False)


def money(v):
    return f"${float(v):,.2f}" if v else "unknown"


def when(v):
    return v.replace("T", " ").replace(".000Z", " UTC") if v else "not yet"


def zip5(v):
    return v.split(".")[0].zfill(5) if v else "not on file"


def write(name, title, blocks):
    header = f"{title}\nSource: Cedarline Health Plan service data.\n\n"
    parts, cur = [], header
    for b in blocks:
        if len(cur.encode("utf-8")) + len(b.encode("utf-8")) > MAX_BYTES:
            parts.append(cur)
            cur = header
        cur += b + "\n\n"
    parts.append(cur)
    for i, text in enumerate(parts, 1):
        suffix = f"_part{i}" if len(parts) > 1 else ""
        path = os.path.join(DST, f"{name}{suffix}.txt")
        open(path, "w", encoding="utf-8").write(text)
        print(f"{os.path.basename(path):<32} {len(blocks) if len(parts) == 1 else '':>6} {len(text.encode()) / 1e6:.2f} MB")


plans = read("plans").set_index("plan_id")
members = read("members")
acc = read("accumulators").set_index("member_id")
names = dict(zip(members.member_id, members.name))


def who(mid):
    return f"member {mid} ({names.get(mid, 'unknown')})"


write("plans", "Cedarline Health Plans", [
    f"Plan {p.plan_id}: {p.plan_name}. Tier: {p.tier}. Annual deductible: {money(p.deductible)}. "
    f"Out-of-pocket maximum: {money(p.oop_max)}."
    for p in plans.reset_index().itertuples()])

blocks = []
for m in members.itertuples():
    plan = plans.loc[m.plan_id] if m.plan_id in plans.index else None
    b = (f"Member {m.member_id}: {m.name}. Date of birth: {m.dob}. Email: {m.email}. ZIP: {zip5(m.zip)}. "
         f"Membership status: {m.status}. Plan: {m.plan_id}"
         + (f" ({plan.plan_name}, {plan.tier} tier, deductible {money(plan.deductible)}, "
            f"out-of-pocket maximum {money(plan.oop_max)})." if plan is not None else "."))
    if m.member_id in acc.index:
        a = acc.loc[m.member_id]
        b += (f" Plan year {a.plan_year} accumulators as of {a.as_of}: deductible met {money(a.deductible_met)}, "
              f"out-of-pocket met {money(a.oop_met)}.")
        if plan is not None:
            b += (f" Remaining deductible: {money(max(float(plan.deductible) - float(a.deductible_met), 0))}. "
                  f"Remaining out-of-pocket: {money(max(float(plan.oop_max) - float(a.oop_met), 0))}.")
    blocks.append(b)
write("members", "Cedarline Members, Plans and Accumulators", blocks)

write("claims", "Cedarline Claims", [
    f"Claim {c.claim_id} for {who(c.member_id)}. Service date: {c.service_date}. Provider: {' '.join(c.provider.split())}. "
    f"Billed: {money(c.billed)}. Member owes: {money(c.member_owes)}. Status: {c.status}"
    + (f" (reason: {c.status_reason})" if c.status_reason else "") + f". Last updated: {when(c.updated_at)}."
    for c in read("claims").itertuples()])

write("prior_auths", "Cedarline Prior Authorizations", [
    f"Prior authorization {p.auth_id} for {who(p.member_id)}. Service code: {p.service_code}. Status: {p.status}. "
    f"Submitted: {when(p.submitted_at)}. Decided: {when(p.decided_at)}."
    for p in read("prior_auths").itertuples()])

write("service_requests", "Cedarline Service Requests", [
    f"Service request {s.request_id} for {who(s.member_id)}. Type: {s.type}. Status: {s.status}. "
    f"Opened: {when(s.opened_at)}. Closed: {when(s.closed_at)}."
    for s in read("service_requests").itertuples()])

write("case_notes", "Cedarline Service Request Case Notes", [
    f"Case note {n.note_id} on service request {n.request_id}, written by {n.author_role.replace('_', ' ')} "
    f"at {when(n.created_at)}: {n.text}"
    for n in read("case_notes").itertuples()])

write("call_transcripts", "Cedarline Call Transcripts", [
    f"Call transcript {t.transcript_id} (interaction {t.interaction_id}) with {who(t.member_id)}: {t.text}"
    for t in read("call_transcripts").itertuples()])

write("interactions", "Cedarline Member Interactions", [
    f"Interaction {i.interaction_id} with {who(i.member_id)} via {i.channel}. Intent: {i.intent.replace('_', ' ')}. "
    f"Started: {when(i.started_at)}. Handle time: {i.handle_secs} seconds. "
    f"Resolved: {'yes' if i.resolved_flag == 'true' else 'no'}. CSAT: {i.csat or 'not given'}."
    for i in read("interactions").itertuples()])
