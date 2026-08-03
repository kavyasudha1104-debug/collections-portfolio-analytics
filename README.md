Collections Portfolio Analytics Dashboard

Business question: Given limited collection capacity, where is portfolio risk concentrated, how do accounts move between delinquency stages, and which accounts should agents work first?

A collections analytics project on a simulated NBFC-style loan portfolio — 5,000 loans, 60,000 monthly performance records — analyzed with PostgreSQL (window functions, CTEs) and visualized in Power BI and an interactive HTML dashboard.

View the live dashboard https://kavyasudha1104-debug.github.io/collections-portfolio-analytics/dashboard.html

Key findings
Roll rates reveal the intervention window: 29.6% of accounts in the 1–30 DPD bucket roll into 31–60 DPD the next month, while 48.9% cure back to current — early-bucket contact has the highest save probability.
Cure rate decays as the book seasons: monthly cure rate fell from 50.0% to 27.4% over the year, signalling rising hard-core delinquency.
Risk is concentrated by grade: delinquency runs 7.7% for Grade A vs 26.4% for Grade D, and Grade C–E loans hold the majority of charged-off balance — supporting grade-differentiated collection strategies.
Post-charge-off recovery averages 17.7% of written-off balance, underlining that prevention (early buckets) beats cure (recovery).
What's inside
File	Purpose
generate_data.py	Builds the synthetic portfolio. Delinquency is simulated with a Markov chain over DPD states, with grade-dependent transition risk — so roll rates and segmentation behave realistically
data/loans.csv	5,000 loans: principal, rate, term, risk grade, purpose, state
data/monthly_performance.csv	60,000 loan-month records: DPD, balance, status, recoveries
collections_analysis.sql	The six core queries (PostgreSQL dialect): DPD bucket distribution, roll-rate matrix (LEAD), cure rate, recovery rate, risk segmentation, prioritization list (RANK)
run_analysis.py	Executes every query (DuckDB engine, Postgres-compatible), exports results to outputs/, renders charts to charts/
build_dashboard.py / dashboard.html	Single-file interactive dashboard (Chart.js): KPI cards, ageing stack, roll-rate heat table, cure trend, grade bars, priority list
outputs/	Query results as CSVs
charts/	Rendered analysis charts
The core metric: roll rates

The roll-rate matrix answers "of accounts in bucket X this month, what share lands in bucket Y next month?" — computed with a LEAD() window function over each loan's monthly history:

sql
WITH transitions AS (
    SELECT loan_id, report_month, status AS from_bucket,
           LEAD(status) OVER (PARTITION BY loan_id
                              ORDER BY report_month) AS to_bucket
    FROM monthly_performance
)
SELECT from_bucket, to_bucket,
       ROUND(100.0 * COUNT(*) /
             SUM(COUNT(*)) OVER (PARTITION BY from_bucket), 2) AS roll_rate_pct
FROM transitions
WHERE to_bucket IS NOT NULL
GROUP BY from_bucket, to_bucket;
Run it yourself
bash
pip install duckdb matplotlib
python generate_data.py      # regenerate the portfolio (seeded)
python run_analysis.py       # run all queries, export outputs + charts
python build_dashboard.py    # rebuild dashboard.html

Or load data/*.csv into PostgreSQL with the DDL at the top of collections_analysis.sql and run the queries directly.

Note on the data

The portfolio is synthetic by design — generated with a seeded Markov model so the analysis is fully reproducible and shareable without any borrower privacy concerns. The analytical methods (ageing, roll rates, cure/recovery rates, prioritization) are exactly those used on real collections books.
