ClaimFlow — AI-Powered Multi-Agent Expense Claims Platform


A production-grade B2B expense management system where a LangGraph-orchestrated agent pipeline processes expense claims end-to-end — running OCR, fraud detection, policy validation (RAG), and approval recommendations — while keeping the final decision behind deterministic business rules and human approval for full auditability.



🔗 Live: https://claimflow-production-176f.up.railway.app


Architecture

![Uploading ChatGPT Image Jun 24, 2026, 07_36_27 PM.png…]()


Flow: An employee submits a claim → FastAPI (JWT + RBAC) → the OCR agent extracts receipt data → a deterministic rule engine runs BLOCK-level checks → the LangGraph pipeline runs the agents (fraud → policy RAG → approval → save) over a shared state → results are persisted to PostgreSQL → the claim enters the manager's review queue with a risk score, policy verdict, and recommendation. The manager makes the final call, and every step is audit-logged.


Why ClaimFlow

Most "AI agent" demos let the LLM make the final decision. In a financial system, that's a liability — you can't audit a black box that approves money. ClaimFlow takes a deliberate stance:


The LLM analyzes. Deterministic Python decides. Humans approve.



The agent pipeline gathers evidence — is this fraudulent? does it comply with policy? — but the approval recommendation is computed by deterministic logic, and the final approve/reject is always made by a human approver. Every decision is traceable through an audit log. This is the design principle that separates a demo from a system you could actually run in a finance team.


Key Features


Multi-agent orchestration — a LangGraph pipeline runs fraud → policy → approval → save on each submission
Policy RAG — semantic search over an enterprise policy PDF (ChromaDB + all-MiniLM-L6-v2), with a hybrid extract-then-decide pattern: the LLM extracts policy facts as structured JSON, and Python computes the verdict, so the model cannot contradict itself
OCR receipt processing — an OCR agent extracts merchant, amount, and date from uploaded receipts, with image-tamper detection fields
Rule engine — fast deterministic pre-checks (BLOCK / HIGH / WARNING severities) before the agent pipeline
Fraud detection — rule-based scoring with severity levels (low / medium / high / critical), persisted as fraud alerts
Human-in-the-loop — claims land in a manager review queue with full agent analysis attached; managers approve or reject
Rich policy model — per-category limits, approval hierarchy by amount, and per-beneficiary medical limits
Auth & audit — JWT authentication, role-based access control (employee / manager / finance / admin), and an audit log on every action
Evaluated — the policy RAG is validated with an LLM-as-judge suite (see Evaluation)
Analytics — employee, manager, and admin summary endpoints



Agent Pipeline (LangGraph — app/agents/claim_pipeline.py)

NodeResponsibilityfraud_nodeRule-based fraud scoring (duplicates, frequency anomalies); writes a fraud alertpolicy_nodePolicy RAG — retrieves relevant chunks, extracts limit/eligibility, returns a verdictapproval_nodeDeterministic recommendation from amount + fraud score + policy verdictsave_nodePersists all agent results to the claim and sets status to under_review

Nodes communicate through a shared state dict (not autonomous messaging) — a deliberate choice for auditability and to avoid cycles.

What the agents produce (agent_decision + agent_reasoning)

After a claim is submitted, the pipeline writes its analysis back onto the claim so the manager sees why before deciding:


agent_decision — the recommendation: APPROVE, REVIEW_CAREFULLY, or REJECT. The agent advises; it never auto-approves. The manager makes the final call.
agent_reasoning — a human-readable explanation referencing the actual claim, e.g. "Claim of Rs 4,500 is policy-compliant with low fraud risk (0.10) and a normal amount. Recommend approval. Policy: matched Max/Night limit Rs 5,000, claim within limit."
risk_score — the fraud score (0.0–1.0) from the fraud node.
policy_violations — a structured JSON object with the full breakdown (policy verdict, policy reason, fraud severity, triggered rules, recommendation, priority).


Example of a processed claim:

json{
  "status": "under_review",
  "risk_score": 0.10,
  "agent_decision": "APPROVE",
  "agent_reasoning": "Claim of Rs 4,500 is policy-compliant with low fraud risk (0.10)...",
  "policy_violations": {
    "policy_verdict": "approved",
    "policy_reason": "Matched Max/Night: limit Rs 5,000. Claim Rs 4,500 within limit.",
    "fraud_severity": "low",
    "recommendation": "APPROVE",
    "priority": "low"
  }
}

This is the human-in-the-loop handoff: the agents analyze, the manager sees the decision + reasoning + evidence, then approves or rejects.


Tech Stack

LayerTechnologyOrchestrationLangGraphBackendFastAPI, PythonDatabasePostgreSQL, SQLAlchemy (11-table schema)Vector storeChromaDBEmbeddingssentence-transformers (all-MiniLM-L6-v2)LLMGroq (llama-3.3-70b-versatile)OCRTesseract, pdf2image, pdfplumberAuthJWT, role-based access controlDeploymentRailway (Docker / nixpacks)


Data Model — PostgreSQL + SQLAlchemy

ClaimFlow uses PostgreSQL as the relational database and SQLAlchemy (ORM) as the data-access layer.


PostgreSQL was chosen for strong relational integrity — claims have real foreign-key relationships (a claim has line items, line items have receipts, claims have approval steps and fraud alerts). It also provides native ENUM types (roles, claim status, expense categories) and JSONB columns (policy_violations, fraud reasons, audit old_value/new_value) for flexible structured data alongside the relational schema.
SQLAlchemy ORM maps each table to a Python model class (in app/models/models.py), so the application works with typed objects and relationships instead of raw SQL. Relationships (e.g. ExpenseClaim.line_items, ClaimLineItem.receipts) use relationship() with cascades, and enums are enforced at the model level.
Sessions are managed per-request; the service layer (app/services/) owns all commits and transaction boundaries. A sync_enum.py utility keeps Postgres enum types in sync with the Python enums.


The 11-table schema

TablePurposeusersAccounts with roles (employee/manager/finance/admin) and employee levelsdepartmentsOrg structure, BAU project codes, department managersexpense_claimsClaim header — status, risk score, agent decision/reasoning, RAG chunksclaim_line_itemsIndividual expense lines — category, amount, beneficiary, city tier, OCR mismatchreceiptsUploaded receipts + OCR-extracted fields + tamper-detection flagspoliciesPer-category spending limits, deadlines, project-code rulespolicy_approval_rulesApproval hierarchy by claim amount (manager → finance → CFO)policy_beneficiary_rulesMedical limits per beneficiary (self/spouse/child/parent)approval_stepsMulti-step approval workflow with SLA trackingfraud_alertsAI fraud detection results with severity and resolutionaudit_logsEvery action recorded for full traceability

The claim lifecycle is a 10-state machine: draft → submitted → under_review → approved / rejected / paid / on_hold / escalated / appealed / fraud_alert.


Evaluation

The policy RAG was evaluated with an LLM-as-judge suite across 18 test questions (category limits + policy FAQ), measuring the four standard RAG metrics:

MetricScoreFaithfulness100%Answer Relevancy94%Context Recall83%Answer Correctness83%Overall90%

Show Image

Faithfulness 100% — zero hallucination, the most important property for a policy system. The weak spot is context recall (83%) on broad/process-oriented queries, which would improve with better chunking or hybrid retrieval.


Ragas was evaluated but dropped due to dependency conflicts; the suite uses Groq directly as the judge — same metrics, full control over grading prompts.




API

FastAPI routers under app/api/v1/:

RouterEndpointsusersregister, login, set employee levelclaimscreate, list, get, delete, submit, approve, rejectreceiptsupload, get, delete, OCR extractragingest policy, chat-policy, check-policydepartmentsCRUD, assign userpoliciespolicy managementapprovalsapproval workflowanalyticsemployee / manager / admin summaries

Interactive docs at /docs.


Getting Started

Prerequisites


Python 3.11+
PostgreSQL
A Groq API key
Tesseract OCR + Poppler (for receipt processing)


Setup

bashgit clone https://github.com/Yash1-23/Claimflow.git
cd Claimflow/backend

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# configure .env: DATABASE_URL, GROQ_API_KEY, SECRET_KEY
# create tables, then ingest the policy PDF (POST /api/v1/rag/ingest-policy)

uvicorn main:app --reload

Interactive API docs at http://127.0.0.1:8000/docs.


Project Structure

backend/
├── app/
│   ├── agents/         # claim_pipeline (LangGraph), policy_agent, approval_agent, ocr_agent
│   ├── api/v1/         # users, claims, receipts, rag, departments, policies, approvals, analytics
│   ├── core/           # config, database, security
│   ├── models/         # SQLAlchemy models (11 tables)
│   ├── schemas/        # Pydantic schemas
│   └── services/       # claim, fraud, rag, approval, audit services + rule_engine
├── rag_eval_dataset.py # evaluation test cases
├── rag_evaluation.py   # LLM-as-judge evaluation
├── sync_enum.py        # Postgres enum sync utility
├── dockerfile
├── nixpacks.toml
└── main.py


Roadmap

Finance payment step — a dedicated finance role processes reimbursement after manager approval (the paid status, paid_at, and payment_reference fields already model this; it enforces separation of duties — approvers don't release money). The role and schema are in place; the payment endpoint is next.
Rate limiting — slowapi is configured; applying per-endpoint limits (e.g. on login) is next.
Async pipeline execution (Celery + Redis) for higher throughput
Email notifications on claim status changes
ML-based fraud model (currently rule-based)
Hybrid retrieval to improve context recall
