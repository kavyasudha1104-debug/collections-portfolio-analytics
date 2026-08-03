#!/usr/bin/env python3
"""Build dashboard.html - single-file interactive collections dashboard (Chart.js)."""
import csv, json

def load(name):
    with open(f"outputs/{name}.csv") as f:
        return list(csv.DictReader(f))

dpd   = load("dpd_bucket_distribution")
roll  = load("roll_rate_matrix")
cure  = load("cure_rate_by_month")
rec   = load("recovery_rate_by_grade")
grade = load("portfolio_by_risk_grade")
prio  = load("collection_priority_list")

months  = sorted({r["report_month"] for r in dpd})
BUCKETS = ["current","dpd_1_30","dpd_31_60","dpd_61_90","dpd_90_plus","charged_off"]
LABELS  = ["Current","1-30 DPD","31-60 DPD","61-90 DPD","90+ DPD","Charged Off"]
COLORS  = ["#2e7d32","#fbc02d","#f57c00","#e64a19","#c62828","#4a148c"]

ageing = {b: [next((float(r["pct_of_book"]) for r in dpd
                    if r["report_month"]==m and r["dpd_bucket"]==b), 0.0)
              for m in months] for b in BUCKETS}

roll_cells = {(r["from_bucket"], r["to_bucket"]): float(r["roll_rate_pct"]) for r in roll}
roll_rows = ""
for i, fb in enumerate(BUCKETS):
    tds = ""
    for tb in BUCKETS:
        v = roll_cells.get((fb, tb))
        if v is None:
            tds += "<td class='empty'>–</td>"
        else:
            alpha = min(v/100, 1)
            fg = "#fff" if v > 55 else "#222"
            tds += f"<td style='background:rgba(198,40,40,{alpha:.2f});color:{fg}'>{v:.1f}%</td>"
    roll_rows += f"<tr><th>{LABELS[i]}</th>{tds}</tr>"

total_out = sum(float(r["outstanding"]) for r in grade)
latest_m = months[-1]
dq_latest = sum(int(r["accounts"]) for r in dpd if r["report_month"]==latest_m and r["dpd_bucket"] not in ("current","charged_off"))
acct_latest = sum(int(r["accounts"]) for r in dpd if r["report_month"]==latest_m)
dq_pct = 100*dq_latest/acct_latest
cure_latest = float(cure[-1]["cure_rate_pct"])
rec_overall = 100*sum(float(r["total_recovered"]) for r in rec)/sum(float(r["total_charged_off"]) for r in rec)

prio_rows = "".join(
    f"<tr><td>{r['loan_id']}</td><td>{r['risk_grade']}</td><td>{r['state']}</td>"
    f"<td>{r['status'].replace('dpd_','').replace('_','-')} DPD</td><td>{int(r['dpd'])}</td>"
    f"<td style='text-align:right'>\u20b9{int(float(r['outstanding_balance'])):,}</td></tr>"
    for r in prio[:15])

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Collections Portfolio Analytics</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f5f7;color:#222}}
 header{{background:#15315b;color:#fff;padding:18px 28px}}
 header h1{{margin:0;font-size:22px}} header p{{margin:4px 0 0;opacity:.85;font-size:13px}}
 .kpis{{display:flex;gap:14px;padding:18px 28px 0;flex-wrap:wrap}}
 .kpi{{background:#fff;border-radius:10px;padding:14px 20px;flex:1;min-width:170px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
 .kpi .v{{font-size:26px;font-weight:700;color:#15315b}} .kpi .l{{font-size:12px;color:#666;margin-top:2px}}
 .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:18px 28px 28px}}
 .card{{background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
 .card h3{{margin:0 0 10px;font-size:15px;color:#15315b}}
 table{{border-collapse:collapse;width:100%;font-size:12px}}
 th,td{{padding:6px 8px;border:1px solid #e3e6ea;text-align:center}}
 thead th{{background:#15315b;color:#fff}} tbody th{{background:#eef1f5;text-align:left}}
 td.empty{{color:#bbb}}
 @media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>Collections Portfolio Analytics Dashboard</h1>
<p>5,000-loan NBFC-style portfolio &middot; 12 months of performance &middot; SQL (PostgreSQL) analysis &middot; latest month: {latest_m}</p></header>
<div class="kpis">
 <div class="kpi"><div class="v">&#8377;{total_out/1e7:.1f} Cr</div><div class="l">Outstanding book (latest month)</div></div>
 <div class="kpi"><div class="v">{dq_pct:.1f}%</div><div class="l">Delinquency rate (1&ndash;90+ DPD)</div></div>
 <div class="kpi"><div class="v">{cure_latest:.1f}%</div><div class="l">Cure rate (latest month)</div></div>
 <div class="kpi"><div class="v">{rec_overall:.1f}%</div><div class="l">Recovery rate on charge-offs</div></div>
</div>
<div class="grid">
 <div class="card"><h3>Portfolio Ageing &mdash; DPD bucket mix over time</h3><canvas id="ageing"></canvas></div>
 <div class="card"><h3>Cure Rate Trend</h3><canvas id="cure"></canvas></div>
 <div class="card"><h3>Roll-Rate Matrix (from &darr; / to &rarr;, % month-over-month)</h3>
   <table><thead><tr><th></th>{"".join(f"<th>{l}</th>" for l in LABELS)}</tr></thead>
   <tbody>{roll_rows}</tbody></table></div>
 <div class="card"><h3>Delinquency &amp; Charge-off by Risk Grade</h3><canvas id="grade"></canvas></div>
 <div class="card" style="grid-column:1/-1"><h3>Collection Priority List &mdash; top early-bucket accounts by balance at risk</h3>
   <table><thead><tr><th>Loan</th><th>Grade</th><th>State</th><th>Bucket</th><th>DPD</th><th>Outstanding</th></tr></thead>
   <tbody>{prio_rows}</tbody></table></div>
</div>
<script>
const months={json.dumps(months)};
new Chart(document.getElementById('ageing'),{{type:'bar',
 data:{{labels:months,datasets:[{",".join(
    f"{{label:'{LABELS[i]}',data:{json.dumps(ageing[b])},backgroundColor:'{COLORS[i]}'}}"
    for i,b in enumerate(BUCKETS))}]}},
 options:{{responsive:true,scales:{{x:{{stacked:true}},y:{{stacked:true,max:100,title:{{display:true,text:'% of book'}}}}}}}}}});
new Chart(document.getElementById('cure'),{{type:'line',
 data:{{labels:{json.dumps([r["report_month"] for r in cure])},
  datasets:[{{label:'Cure rate %',data:{json.dumps([float(r["cure_rate_pct"]) for r in cure])},
   borderColor:'#1565c0',backgroundColor:'rgba(21,101,192,.12)',fill:true,tension:.25}}]}},
 options:{{responsive:true,scales:{{y:{{title:{{display:true,text:'%'}}}}}}}}}});
new Chart(document.getElementById('grade'),{{type:'bar',
 data:{{labels:{json.dumps([r["risk_grade"] for r in grade])},
  datasets:[
   {{label:'Delinquency %',data:{json.dumps([float(r["delinquency_rate_pct"]) for r in grade])},backgroundColor:'#f57c00'}},
   {{label:'Charge-off %',data:{json.dumps([float(r["chargeoff_rate_pct"]) for r in grade])},backgroundColor:'#c62828'}}]}},
 options:{{responsive:true,scales:{{y:{{title:{{display:true,text:'% of accounts'}}}}}}}}}});
</script></body></html>"""

open("dashboard.html","w").write(html)
print("dashboard.html written,", len(html), "bytes")
