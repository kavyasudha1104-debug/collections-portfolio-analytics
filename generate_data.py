#!/usr/bin/env python3
"""
Generate a realistic synthetic loan portfolio for collections analytics practice.
Produces:
  loans.csv               - one row per loan (origination attributes)
  monthly_performance.csv - one row per loan per month (DPD, balance, status)

The delinquency behaviour is simulated with a Markov chain over DPD buckets,
with transition probabilities that worsen for higher-risk grades - so roll
rates, cure rates, and risk segmentation all produce meaningful results.
"""
import csv
import random
from datetime import date

random.seed(42)

N_LOANS = 5000
MONTHS = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
          "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12"]

GRADES = ["A", "B", "C", "D", "E"]
GRADE_WEIGHTS = [0.30, 0.28, 0.22, 0.13, 0.07]
PURPOSES = ["personal", "vehicle", "business", "consumer_durable", "education"]
STATES = ["Maharashtra", "Karnataka", "Tamil Nadu", "Telangana", "Delhi",
          "Gujarat", "West Bengal", "Andhra Pradesh", "Rajasthan", "Kerala"]

# DPD bucket states: 0=current, 1=1-30, 2=31-60, 3=61-90, 4=90+ , 5=charged_off
# Transition matrix rows = from-state; base probabilities for grade A.
BASE_TRANSITIONS = {
    0: [0.965, 0.035, 0.000, 0.000, 0.000, 0.000],
    1: [0.55,  0.25,  0.20,  0.00,  0.00,  0.00],
    2: [0.20,  0.15,  0.25,  0.40,  0.00,  0.00],
    3: [0.08,  0.05,  0.12,  0.25,  0.50,  0.00],
    4: [0.03,  0.02,  0.03,  0.07,  0.60,  0.25],
    5: [0.00,  0.00,  0.00,  0.00,  0.00,  1.00],
}
# Risk multiplier: how much more likely to slip downward per grade
GRADE_RISK = {"A": 1.0, "B": 1.6, "C": 2.4, "D": 3.5, "E": 5.0}


def transition(state, grade):
    probs = list(BASE_TRANSITIONS[state])
    risk = GRADE_RISK[grade]
    if state == 0:
        p_bad = min(probs[1] * risk, 0.35)
        probs = [1 - p_bad, p_bad, 0, 0, 0, 0]
    else:
        # scale the "worse" tail, renormalise
        for i in range(len(probs)):
            if i > state:
                probs[i] = min(probs[i] * (1 + (risk - 1) * 0.5), 0.9)
        s = sum(probs)
        probs = [p / s for p in probs]
    r = random.random()
    cum = 0.0
    for i, p in enumerate(probs):
        cum += p
        if r <= cum:
            return i
    return len(probs) - 1


def dpd_for_state(state):
    return {0: 0,
            1: random.randint(1, 30),
            2: random.randint(31, 60),
            3: random.randint(61, 90),
            4: random.randint(91, 180),
            5: 999}[state]


loans = []
for i in range(1, N_LOANS + 1):
    grade = random.choices(GRADES, GRADE_WEIGHTS)[0]
    principal = random.choice([50, 100, 150, 200, 300, 500, 750, 1000]) * 1000
    rate = {"A": 11, "B": 14, "C": 17, "D": 21, "E": 26}[grade] + random.uniform(-1, 1)
    loans.append({
        "loan_id": f"L{i:05d}",
        "origination_date": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        "principal_amount": principal,
        "interest_rate": round(rate, 2),
        "term_months": random.choice([12, 24, 36, 48]),
        "risk_grade": grade,
        "purpose": random.choice(PURPOSES),
        "state": random.choice(STATES),
        "monthly_income": random.choice([25, 35, 50, 75, 100, 150]) * 1000,
    })

with open("loans.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=loans[0].keys())
    w.writeheader()
    w.writerows(loans)

perf_rows = []
for loan in loans:
    state = 0
    balance = loan["principal_amount"]
    emi = round(loan["principal_amount"] / loan["term_months"] * 1.12)
    charged_off_recovery_done = False
    for m in MONTHS:
        state = transition(state, loan["risk_grade"])
        dpd = dpd_for_state(state)
        if state == 0:
            balance = max(0, balance - emi)
        elif state == 5:
            pass  # charged off - balance frozen
        else:
            balance = max(0, balance - int(emi * random.uniform(0, 0.5)))
        recovery = 0
        if state == 5 and not charged_off_recovery_done and random.random() < 0.35:
            recovery = int(balance * random.uniform(0.05, 0.40))
            charged_off_recovery_done = True
        perf_rows.append({
            "loan_id": loan["loan_id"],
            "report_month": m,
            "dpd": dpd,
            "outstanding_balance": balance,
            "emi_amount": emi,
            "status": ["current", "dpd_1_30", "dpd_31_60", "dpd_61_90",
                       "dpd_90_plus", "charged_off"][state],
            "recovery_amount": recovery,
        })

with open("monthly_performance.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=perf_rows[0].keys())
    w.writeheader()
    w.writerows(perf_rows)

print(f"loans.csv: {len(loans)} loans")
print(f"monthly_performance.csv: {len(perf_rows)} monthly records")
