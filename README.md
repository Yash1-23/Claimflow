## ClaimFlow — AI-Powered Multi-Agent Expense Claims Platform

A production-grade B2B expense management system where a LangGraph-orchestrated agent pipeline processes expense claims end-to-end — running OCR, fraud detection, policy validation (RAG), and approval recommendations — while keeping the final decision behind deterministic business rules and human approval for full auditability.

🔗 Live: https://claimflow-production-176f.up.railway.app

## The Problem Statement

Expense reimbursement workflows in many organizations are slow, manual, difficult to audit, and vulnerable to policy violations and fraudulent claims. Employees submit receipts and expense reports, managers manually verify policy compliance, finance teams review supporting documents, and reimbursement decisions often depend on time-consuming human checks. As claim volume increases, approval delays, inconsistent policy enforcement, and operational overhead become significant challenges.

Many AI-powered workflow systems attempt to automate these decisions entirely through LLMs. However, financial approvals require auditability, deterministic decision-making, and human accountability. A black-box model should not be trusted to approve the movement of money.


### The Solution
ClaimFlow is a production-grade AI-powered expense claims platform that combines OCR, deterministic business rules, policy-aware RAG, fraud detection, and human-in-the-loop approvals into a single auditable workflow.

The system automatically extracts receipt data, validates claims against company policies, identifies potential fraud signals, and generates approval recommendations — but the final decision stays under deterministic business rules and human approval.

This enables organizations to reduce manual effort, improve policy compliance, strengthen auditability, and scale reimbursement workflows without sacrificing control or trust.

## Architecture

<img width="1024" height="1536" alt="Architecture_claimflow" src="https://github.com/user-attachments/assets/0ec48bf9-a9d6-40a7-a28c-dbdc98289da3" />

Flow: An employee submits a claim → FastAPI (JWT + RBAC) → the OCR agent extracts receipt data → a deterministic rule engine runs BLOCK-level checks → the LangGraph pipeline runs the agents (fraud → policy RAG → approval → save) over a shared state → results are persisted to PostgreSQL → the claim enters the manager's review queue with a risk score, policy verdict, and recommendation. The manager makes the final call, and every step is audit-logged.


## Key Features
- Multi-agent orchestration — a LangGraph pipeline runs fraud → policy → approval → save on each submission.
  
- Policy RAG — semantic search over an enterprise policy PDF (ChromaDB + all-MiniLM-L6-v2), with a hybrid extract-then-decide pattern: the LLM extracts policy facts as structured JSON, and Python computes the verdict, so the model cannot contradict itself.

- OCR receipt processing — an OCR agent extracts merchant, amount, and date from uploaded receipts, with image-tamper detection fields.

- Rule engine — fast deterministic pre-checks (BLOCK / HIGH / WARNING severities) before the agent pipeline.

- Fraud detection — rule-based scoring with severity levels (low / medium / high / critical), persisted as fraud alerts.

- Human-in-the-loop — claims land in a manager review queue with full agent analysis attached; managers approve or reject.

- Rich policy model — per-category limits, approval hierarchy by amount, and per-beneficiary medical limits.

- Auth & audit — JWT authentication, role-based access control (employee / manager / admin), and an audit log on every action.

- Evaluated — the policy RAG is validated with an LLM-as-judge suite.

- Analytics — employee, manager, and admin summary endpoints.


## Agent Pipeline (LangGraph — app/agents/claim_pipeline.py)

Node                Responsibility

fraud_node          Rule-based fraud scoring (duplicates, frequency anomalies); writes a fraud alert.

policy_node         Policy RAG — retrieves relevant chunks, extracts limit/eligibility, returns a verdict.

approval_node       Deterministic recommendation from amount + fraud score + policy verdict.

save_node           Persists all agent results to the claim and sets status to under_review.

Nodes communicate through a shared state dict (not autonomous messaging) — a deliberate choice for auditability and to avoid cycles.


## What the agents produce (agent_decision + agent_reasoning)

After a claim is submitted, the pipeline writes its analysis back onto the claim so the manager sees why before deciding:

- agent_decision — the recommendation: APPROVE, REVIEW_CAREFULLY, or REJECT. The agent advises; it never auto-approves. The manager makes the final call.

- agent_reasoning — a human-readable explanation referencing the actual claim
  
  e.g. "Claim of Rs 4,500 is policy-compliant with low fraud risk (0.10) and a normal amount. Recommend approval. Policy: matched Max/Night limit Rs 5,000, claim within limit."

- risk_score — the fraud score (0.0–1.0) from the fraud node.

- policy_violations — a structured JSON object with the full breakdown (policy verdict, policy reason, fraud severity, triggered rules, recommendation, priority).


Example of a processed claim:

{
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

## Tech Stack

Layer              Technology

Orchestration        LangGraph

Backend              Python, FastAPI

Database             PostgreSQL,SQLAlchemy

VectorStore          ChromaDB

Embeddings           sentence-transformers (all-MiniLM-L6-v2)

LLM                  Groq (llama-3.3-70b-versatile)

OCR                  Tesseract, pdf2image, pdfplumber

Auth                 JWT, role-based access control

Deployment           Railway (Docker / nixpacks)


## Data Model — PostgreSQL + SQLAlchemy

ClaimFlow uses PostgreSQL as the relational database and SQLAlchemy (ORM) as the data-access layer.

- PostgreSQL was chosen for strong relational integrity — claims have real foreign-key relationships (a claim has line items, line items have receipts, claims have approval steps and fraud alerts). It also provides native ENUM types (roles, claim status, expense categories) and JSONB columns (policy_violations, fraud reasons, audit old_value/new_value) for flexible structured data alongside the relational schema.

- SQLAlchemy ORM maps each table to a Python model class (in app/models/models.py), so the application works with typed objects and relationships instead of raw SQL. Relationships (e.g. ExpenseClaim.line_items, ClaimLineItem.receipts) use relationship() with cascades, and enums are enforced at the model level.

- Sessions are managed per-request; the service layer (app/services/) owns all commits and transaction boundaries. A sync_enum.py utility keeps Postgres enum types in sync with the Python enums.


## The 11-table schema

Table                                         Purpose

users                        Accounts with roles (employee/manager/admin) and employee levels.

departments                  Org structure, BAU project codes, department managers,assging department.

expense_claims               Claim header — status, risk score, agent decision/reasoning, RAG chunks.

claim_line_items             Individual expense lines — category, amount, beneficiary, city tier, OCR mismatch.

receipts                     Uploaded receipts + OCR-extracted fields.

policies                     Per-category spending limits, deadlines, project-code rules.

policy_approval_rules        Approval hierarchy by claim amount (manager)

policy_beneficiary_rules     Medical limits per beneficiary (self/spouse/child/parent)

approval_steps               Multi-step approval workflow with SLA tracking

fraud_alerts                 Rule based Fraud detection results with severity and resolution.

audit_logs                   Every action recorded for full traceability



## Evaluation

The policy RAG was evaluated with an LLM-as-judge suite across 18 test questions (category limits + policy FAQ), measuring the four standard RAG metrics:

<img width="1103" height="390" alt="Screenshot 2026-06-17 190952" src="https://github.com/user-attachments/assets/48aa3385-e207-4713-b344-832539949f2e" />

Faithfulness 100% — zero hallucination, the most important property for a policy system. The weak spot is context recall (83%) on broad/process-oriented queries, which would improve with better chunking or hybrid retrieval.

## API

FastAPI routers under app/api/v1/:

Router                                   Endpoints

users                            register, login, set employee level

claims                           create, list, get, delete, submit, approve, reject

receipts                         upload, get, delete, OCR extract

rag                              ingest policy, chat-policy, check-policy

departments                      CRUD, assign user

analytics                        employee / manager / admin summaries


## Getting Started

## Prerequisites

- Python 3.11+
- PostgreSQL
- A Groq API key
- Tesseract OCR + Poppler (for receipt processing)

Setup

git clone https://github.com/Yash1-23/Claimflow.git

cd Claimflow/backend

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

uvicorn main:app --reload

Interactive API docs at https://claimflow-production-176f.up.railway.app/docs

## Project Structure

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
├── dockerfile
├── nixpacks.toml
└── main.py


















































































