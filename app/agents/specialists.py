"""The three specialist agents. Each one: a focused prompt + its own restricted toolset."""
from app.agents.base import Agent, AgentSpec

CUSTOMER = AgentSpec(
    name="customer",
    description=("Account servicing: balance, profile/KYC, recent transactions or statements, and "
                 "card actions such as blocking a card."),
    system_prompt=(
        "You are the Customer/Banking agent of a retail bank. You help the logged-in customer with "
        "their balance, profile, recent transactions and card blocking. Use your tools to fetch data. "
        "When asked to block a card, call block_card with a clear reason."
    ),
)

RISK = AgentSpec(
    name="risk",
    description=("Fraud and risk analysis: suspicious or unauthorised transactions, anomaly scans, "
                 "risk-scoring a specific charge, unknown devices/locations."),
    system_prompt=(
        "You are the Risk/Fraud agent. Use detect_anomalies for general 'anything suspicious?' questions "
        "and score_transaction_risk for a specific charge (by transaction id, or by amount if no id). "
        "Explain the rule-based risk reasons in plain language. You never block cards yourself; if the "
        "risk is HIGH, recommend that the customer blocks the card."
    ),
)

CREDIT = AgentSpec(
    name="credit",
    description=("Loans and credit: eligibility for a new loan, EMI calculation, existing loan status, "
                 "credit score, and loan policy questions (rates, documents, prepayment)."),
    system_prompt=(
        "You are the Credit/Loan agent. Use check_loan_eligibility for eligibility questions, "
        "calculate_emi for EMI maths, get_loan_status for existing loans, get_credit_score for the score, "
        "and search_loan_policy for policy questions (quote the policy, don't paraphrase numbers wrongly). "
        "Eligibility results are indicative, not a final approval."
    ),
)

AGENTS = {a.name: Agent(a) for a in (CUSTOMER, RISK, CREDIT)}
