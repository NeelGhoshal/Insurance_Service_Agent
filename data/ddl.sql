-- Creates the Cedarline database/schema and tables. Run by load_snowflake.py.
-- Parents before children (FK columns aren't enforced by Snowflake).
CREATE DATABASE IF NOT EXISTS CEDARLINE;
CREATE SCHEMA IF NOT EXISTS CEDARLINE.SERVICE;
USE SCHEMA CEDARLINE.SERVICE;

CREATE OR REPLACE TABLE PLANS (
    plan_id       VARCHAR(10)    PRIMARY KEY,
    plan_name     VARCHAR(100)   NOT NULL,
    tier          VARCHAR(20)    NOT NULL,
    deductible    NUMBER(10,2)   NOT NULL,
    oop_max       NUMBER(10,2)   NOT NULL
);

CREATE OR REPLACE TABLE MEMBERS (
    member_id     VARCHAR(12)    PRIMARY KEY,
    name          VARCHAR(100)   NOT NULL,
    dob           DATE           NOT NULL,
    email         VARCHAR(150),
    zip           VARCHAR(10),
    plan_id       VARCHAR(10)    REFERENCES PLANS(plan_id),
    status        VARCHAR(20)    NOT NULL  -- active, terminated, pending
);

CREATE OR REPLACE TABLE ACCUMULATORS (
    member_id        VARCHAR(12)  REFERENCES MEMBERS(member_id),
    plan_year        NUMBER(4,0)  NOT NULL,
    deductible_met   NUMBER(10,2) NOT NULL,
    oop_met          NUMBER(10,2) NOT NULL,
    as_of            DATE         NOT NULL,
    PRIMARY KEY (member_id, plan_year)
);

CREATE OR REPLACE TABLE CLAIMS (
    claim_id       VARCHAR(14)   PRIMARY KEY,
    member_id      VARCHAR(12)   REFERENCES MEMBERS(member_id),
    service_date   DATE          NOT NULL,
    provider       VARCHAR(150)  NOT NULL,
    billed         NUMBER(10,2)  NOT NULL,
    member_owes    NUMBER(10,2)  NOT NULL,
    status         VARCHAR(20)   NOT NULL,  -- approved, denied, pending
    status_reason  VARCHAR(50),             -- e.g. MISSING_PRIOR_AUTH, null if approved
    updated_at     TIMESTAMP_NTZ NOT NULL
);

CREATE OR REPLACE TABLE PRIOR_AUTHS (
    auth_id        VARCHAR(14)   PRIMARY KEY,
    member_id      VARCHAR(12)   REFERENCES MEMBERS(member_id),
    service_code   VARCHAR(20)   NOT NULL,
    status         VARCHAR(20)   NOT NULL,  -- approved, denied, pending
    submitted_at   TIMESTAMP_NTZ NOT NULL,
    decided_at     TIMESTAMP_NTZ
);

CREATE OR REPLACE TABLE SERVICE_REQUESTS (
    request_id     VARCHAR(14)   PRIMARY KEY,
    member_id      VARCHAR(12)   REFERENCES MEMBERS(member_id),
    type           VARCHAR(30)   NOT NULL,  -- id_card, address_change, appeal, grievance
    status         VARCHAR(20)   NOT NULL,  -- open, closed
    opened_at      TIMESTAMP_NTZ NOT NULL,
    closed_at      TIMESTAMP_NTZ
);

CREATE OR REPLACE TABLE INTERACTIONS (
    interaction_id VARCHAR(14)   PRIMARY KEY,
    member_id      VARCHAR(12)   REFERENCES MEMBERS(member_id),
    channel        VARCHAR(20)   NOT NULL,  -- chat, phone, web
    intent         VARCHAR(50)   NOT NULL,
    started_at     TIMESTAMP_NTZ NOT NULL,
    handle_secs    NUMBER(6,0)   NOT NULL,
    resolved_flag  BOOLEAN       NOT NULL,
    csat           NUMBER(2,0)   -- 1-5, nullable (not every interaction gets surveyed)
);

CREATE OR REPLACE TABLE CALL_TRANSCRIPTS (
    transcript_id  VARCHAR(14)   PRIMARY KEY,
    interaction_id VARCHAR(14)   REFERENCES INTERACTIONS(interaction_id),
    member_id      VARCHAR(12)   REFERENCES MEMBERS(member_id),
    text           VARCHAR(16000) NOT NULL
);

CREATE OR REPLACE TABLE CASE_NOTES (
    note_id        VARCHAR(14)   PRIMARY KEY,
    request_id     VARCHAR(14)   REFERENCES SERVICE_REQUESTS(request_id),
    author_role    VARCHAR(30)   NOT NULL,  -- frontline_agent, supervisor, nurse_line
    text           VARCHAR(8000) NOT NULL,
    created_at     TIMESTAMP_NTZ NOT NULL
);
