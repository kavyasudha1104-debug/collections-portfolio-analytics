#!/usr/bin/env python3
"""
Run the full collections analysis: execute every query in
collections_analysis.sql against the CSV data (via DuckDB, PostgreSQL-
compatible), export results to outputs/, and render charts to charts/.
"""
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

con = duckdb.connect()
con.execute("CREATE TABLE loans AS SELECT * FROM read_csv_auto('data/loans.csv')")
con.execute("CREATE TABLE monthly_performance AS SELECT * FROM read_csv_auto('data/monthly_performance.csv')")

sql = open("collections_analysis.sql").read()
stmts = [s.strip() for s in sql.split(";")
         if s.strip() and not all(l.strip().startswith("--") or not l.strip()
                                  for l in s.splitlines())]

names = ["dpd_bucket_distribution", "roll_rate_matrix", "cure_rate_by_month",
         "recovery_rate_by_grade", "portfolio_by_risk_grade",
         "collection_priority_list"]

results = {}
for name, stmt in zip(names, stmts):
    df = con.execute(stmt).fetchdf()
    df.to_csv(f"outputs/{name}.csv", index=False)
    results[name] = df
    print(f"{name}: {len(df)} rows -> outputs/{name}.csv")

# ---------- Charts ----------
BUCKETS = ["current", "dpd_1_30", "dpd_31_60", "dpd_61_90", "dpd_90_plus", "charged_off"]
LABELS  = ["Current", "1-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD", "Charged Off"]
COLORS  = ["#2e7d32", "#fbc02d", "#f57c00", "#e64a19", "#c62828", "#4a148c"]

# 1. Portfolio ageing (100% stacked area)
d = results["dpd_bucket_distribution"]
months = sorted(d["report_month"].unique())
fig, ax = plt.subplots(figsize=(10, 5))
stack = []
for b in BUCKETS:
    vals = [float(d[(d.report_month == m) & (d.dpd_bucket == b)]["pct_of_book"].sum()) for m in months]
    stack.append(vals)
ax.stackplot(range(len(months)), stack, labels=LABELS, colors=COLORS, alpha=0.9)
ax.set_xticks(range(len(months))); ax.set_xticklabels(months, rotation=45)
ax.set_ylabel("% of book"); ax.set_ylim(0, 100)
ax.set_title("Portfolio Ageing - DPD Bucket Mix Over Time")
ax.legend(loc="lower left", fontsize=8)
plt.tight_layout(); plt.savefig("charts/1_portfolio_ageing.png", dpi=130); plt.close()

# 2. Roll-rate heatmap
r = results["roll_rate_matrix"]
mat = np.zeros((len(BUCKETS), len(BUCKETS)))
for _, row in r.iterrows():
    i = BUCKETS.index(row["from_bucket"]); j = BUCKETS.index(row["to_bucket"])
    mat[i, j] = row["roll_rate_pct"]
fig, ax = plt.subplots(figsize=(8, 6))
im = ax.imshow(mat, cmap="YlOrRd", vmin=0, vmax=100)
ax.set_xticks(range(len(LABELS))); ax.set_xticklabels(LABELS, rotation=45, ha="right")
ax.set_yticks(range(len(LABELS))); ax.set_yticklabels(LABELS)
ax.set_xlabel("To bucket (next month)"); ax.set_ylabel("From bucket (this month)")
ax.set_title("Roll-Rate Matrix (%)")
for i in range(len(BUCKETS)):
    for j in range(len(BUCKETS)):
        if mat[i, j] > 0:
            ax.text(j, i, f"{mat[i,j]:.1f}", ha="center", va="center",
                    fontsize=8, color="black" if mat[i,j] < 60 else "white")
fig.colorbar(im, shrink=0.8)
plt.tight_layout(); plt.savefig("charts/2_roll_rate_matrix.png", dpi=130); plt.close()

# 3. Cure rate trend
c = results["cure_rate_by_month"]
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.plot(c["report_month"], c["cure_rate_pct"], marker="o", color="#1565c0", lw=2)
ax.set_ylabel("Cure rate (%)"); ax.set_title("Monthly Cure Rate - Delinquent Accounts Returning to Current")
ax.grid(alpha=0.3); plt.xticks(rotation=45)
plt.tight_layout(); plt.savefig("charts/3_cure_rate_trend.png", dpi=130); plt.close()

# 4. Delinquency & charge-off by grade
g = results["portfolio_by_risk_grade"]
x = np.arange(len(g)); w = 0.38
fig, ax = plt.subplots(figsize=(9, 5))
ax.bar(x - w/2, g["delinquency_rate_pct"], w, label="Delinquency %", color="#f57c00")
ax.bar(x + w/2, g["chargeoff_rate_pct"], w, label="Charge-off %", color="#c62828")
ax.set_xticks(x); ax.set_xticklabels(g["risk_grade"])
ax.set_xlabel("Risk grade"); ax.set_ylabel("% of accounts (latest month)")
ax.set_title("Delinquency & Charge-off Concentration by Risk Grade")
ax.legend(); ax.grid(axis="y", alpha=0.3)
plt.tight_layout(); plt.savefig("charts/4_risk_segmentation.png", dpi=130); plt.close()

print("charts rendered")

# ---------- Key findings for README ----------
early_roll = r[(r.from_bucket == "dpd_1_30") & (r.to_bucket == "dpd_31_60")]["roll_rate_pct"].iloc[0]
cure_first, cure_last = c["cure_rate_pct"].iloc[0], c["cure_rate_pct"].iloc[-1]
dq_a = g[g.risk_grade == "A"]["delinquency_rate_pct"].iloc[0]
dq_d = g[g.risk_grade == "D"]["delinquency_rate_pct"].iloc[0]
rec = results["recovery_rate_by_grade"]
overall_rec = 100 * rec["total_recovered"].sum() / rec["total_charged_off"].sum()
print(f"\nFINDINGS:")
print(f"- 1-30 DPD -> 31-60 DPD roll rate: {early_roll:.1f}%")
print(f"- Cure rate decayed {cure_first:.1f}% -> {cure_last:.1f}%")
print(f"- Delinquency by grade: A {dq_a:.1f}% vs D {dq_d:.1f}%")
print(f"- Overall recovery rate on charge-offs: {overall_rec:.1f}%")
