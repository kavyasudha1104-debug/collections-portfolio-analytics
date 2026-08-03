-- ============================================================
-- COLLECTIONS PORTFOLIO ANALYTICS - core queries
-- Dialect: PostgreSQL (also runs on DuckDB / Redshift)
-- Tables: loans, monthly_performance  (see generate_data.py)
-- ============================================================

-- ------------------------------------------------------------
-- 0. Table setup (PostgreSQL). Load the CSVs with \copy.
-- ------------------------------------------------------------
-- CREATE TABLE loans (
--   loan_id            VARCHAR PRIMARY KEY,
--   origination_date   DATE,
--   principal_amount   NUMERIC,
--   interest_rate      NUMERIC,
--   term_months        INT,
--   risk_grade         VARCHAR,
--   purpose            VARCHAR,
--   state              VARCHAR,
--   monthly_income     NUMERIC
-- );
-- CREATE TABLE monthly_performance (
--   loan_id             VARCHAR REFERENCES loans(loan_id),
--   report_month        VARCHAR,   -- 'YYYY-MM'
--   dpd                 INT,
--   outstanding_balance NUMERIC,
--   emi_amount          NUMERIC,
--   status              VARCHAR,
--   recovery_amount     NUMERIC
-- );
-- \copy loans FROM 'loans.csv' CSV HEADER;
-- \copy monthly_performance FROM 'monthly_performance.csv' CSV HEADER;

-- ------------------------------------------------------------
-- 1. DPD BUCKET DISTRIBUTION by month
--    "What does the ageing of the book look like over time?"
-- ------------------------------------------------------------
SELECT
    report_month,
    status                                        AS dpd_bucket,
    COUNT(*)                                      AS accounts,
    SUM(outstanding_balance)                      AS outstanding,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY report_month), 2)
                                                  AS pct_of_book
FROM monthly_performance
GROUP BY report_month, status
ORDER BY report_month, dpd_bucket;

-- ------------------------------------------------------------
-- 2. ROLL-RATE MATRIX  (the core collections metric)
--    "Of accounts in bucket X this month, what % moved to
--     bucket Y next month?"  Uses LEAD() window function.
-- ------------------------------------------------------------
WITH transitions AS (
    SELECT
        loan_id,
        report_month,
        status                                            AS from_bucket,
        LEAD(status) OVER (PARTITION BY loan_id
                           ORDER BY report_month)         AS to_bucket
    FROM monthly_performance
)
SELECT
    from_bucket,
    to_bucket,
    COUNT(*)                                              AS accounts,
    ROUND(100.0 * COUNT(*) /
          SUM(COUNT(*)) OVER (PARTITION BY from_bucket), 2) AS roll_rate_pct
FROM transitions
WHERE to_bucket IS NOT NULL
GROUP BY from_bucket, to_bucket
ORDER BY from_bucket, to_bucket;

-- ------------------------------------------------------------
-- 3. CURE RATE by month
--    "Of delinquent accounts, what % returned to current the
--     following month?"
-- ------------------------------------------------------------
WITH transitions AS (
    SELECT
        loan_id,
        report_month,
        status                                            AS from_bucket,
        LEAD(status) OVER (PARTITION BY loan_id
                           ORDER BY report_month)         AS to_bucket
    FROM monthly_performance
)
SELECT
    report_month,
    COUNT(*) FILTER (WHERE to_bucket = 'current')         AS cured,
    COUNT(*)                                              AS delinquent_accounts,
    ROUND(100.0 * COUNT(*) FILTER (WHERE to_bucket = 'current')
          / COUNT(*), 2)                                  AS cure_rate_pct
FROM transitions
WHERE from_bucket IN ('dpd_1_30', 'dpd_31_60', 'dpd_61_90', 'dpd_90_plus')
  AND to_bucket IS NOT NULL
GROUP BY report_month
ORDER BY report_month;

-- ------------------------------------------------------------
-- 4. RECOVERY RATE on charged-off loans
--    "Of the balance we wrote off, how much did we get back?"
-- ------------------------------------------------------------
WITH charged_off AS (
    SELECT
        loan_id,
        MAX(outstanding_balance)  AS balance_at_chargeoff,
        SUM(recovery_amount)      AS total_recovered
    FROM monthly_performance
    WHERE status = 'charged_off'
    GROUP BY loan_id
)
SELECT
    l.risk_grade,
    COUNT(*)                                              AS charged_off_loans,
    SUM(c.balance_at_chargeoff)                           AS total_charged_off,
    SUM(c.total_recovered)                                AS total_recovered,
    ROUND(100.0 * SUM(c.total_recovered)
          / NULLIF(SUM(c.balance_at_chargeoff), 0), 2)    AS recovery_rate_pct
FROM charged_off c
JOIN loans l ON l.loan_id = c.loan_id
GROUP BY l.risk_grade
ORDER BY l.risk_grade;

-- ------------------------------------------------------------
-- 5. PORTFOLIO BY RISK SEGMENT (latest month snapshot)
--    "Where is the delinquency concentrated?"
-- ------------------------------------------------------------
WITH latest AS (
    SELECT *
    FROM monthly_performance
    WHERE report_month = (SELECT MAX(report_month) FROM monthly_performance)
)
SELECT
    l.risk_grade,
    COUNT(*)                                              AS accounts,
    SUM(p.outstanding_balance)                            AS outstanding,
    ROUND(100.0 * COUNT(*) FILTER (WHERE p.status <> 'current'
                                     AND p.status <> 'charged_off')
          / COUNT(*), 2)                                  AS delinquency_rate_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE p.status = 'charged_off')
          / COUNT(*), 2)                                  AS chargeoff_rate_pct
FROM latest p
JOIN loans l ON l.loan_id = p.loan_id
GROUP BY l.risk_grade
ORDER BY l.risk_grade;

-- ------------------------------------------------------------
-- 6. COLLECTION PRIORITIZATION LIST
--    "Given limited agents, which accounts do we work first?"
--    Rank early-stage delinquents by balance at risk - the
--    highest expected saves. Uses RANK() window function.
-- ------------------------------------------------------------
WITH latest AS (
    SELECT *
    FROM monthly_performance
    WHERE report_month = (SELECT MAX(report_month) FROM monthly_performance)
),
at_risk AS (
    SELECT
        p.loan_id,
        l.risk_grade,
        l.state,
        p.status,
        p.dpd,
        p.outstanding_balance,
        RANK() OVER (PARTITION BY p.status
                     ORDER BY p.outstanding_balance DESC) AS priority_in_bucket
    FROM latest p
    JOIN loans l ON l.loan_id = p.loan_id
    WHERE p.status IN ('dpd_1_30', 'dpd_31_60')  -- early-stage: highest cure odds
)
SELECT *
FROM at_risk
WHERE priority_in_bucket <= 20
ORDER BY status, priority_in_bucket;
