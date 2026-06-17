"""
RAG Evaluation Runner - ClaimFlow Policy Chatbot
LLM-as-judge evaluation using Groq (no Ragas/LangSmith dependency conflicts).

Measures the same standard RAG metrics:
  - Faithfulness     : is the answer grounded in retrieved chunks (no hallucination)?
  - Answer Relevancy : does the answer address the question?
  - Context Recall   : did retrieval pull chunks that support the ground-truth answer?
  - Answer Correctness: does the answer match the ground truth?

Each metric is scored by an LLM judge (temperature 0) returning yes/no, then
aggregated to a percentage across all questions.

Usage:
    cd D:\\claim_flow\\backend
    python rag_eval_runner.py
"""

import json
import time
from app.agents.policy_agent import answer_policy_question, client
from rag_eval_dataset import EVAL_QA

JUDGE_MODEL = "llama-3.3-70b-versatile"


def judge(system_prompt: str, user_content: str) -> bool:
    """Ask the judge LLM a yes/no question. Returns True/False."""
    resp = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=150,
        response_format={"type": "json_object"},
    )
    try:
        return bool(json.loads(resp.choices[0].message.content).get("verdict", False))
    except Exception:
        return False


# ---------- the four judges ----------

def judge_faithfulness(answer, contexts):
    ctx = "\n\n".join(contexts)
    return judge(
        'You grade whether an ANSWER is fully grounded in the given CONTEXT (no invented facts). '
        'Return JSON {"verdict": true} if every claim in the answer is supported by the context, else {"verdict": false}.',
        f"CONTEXT:\n{ctx}\n\nANSWER:\n{answer}",
    )


def judge_relevancy(question, answer):
    return judge(
        'You grade whether an ANSWER actually addresses the QUESTION. '
        'Return JSON {"verdict": true} if it is relevant and on-topic, else {"verdict": false}.',
        f"QUESTION:\n{question}\n\nANSWER:\n{answer}",
    )


def judge_context_recall(ground_truth, contexts):
    ctx = "\n\n".join(contexts)
    return judge(
        'You grade whether the CONTEXT contains the information needed to produce the GROUND TRUTH answer. '
        'Return JSON {"verdict": true} if the key facts of the ground truth are present in the context, else {"verdict": false}.',
        f"CONTEXT:\n{ctx}\n\nGROUND TRUTH:\n{ground_truth}",
    )


def judge_correctness(question, answer, ground_truth):
    return judge(
        'You are grading a student answer against the correct (ground truth) answer. '
        'Return JSON {"verdict": true} if the student answer is factually consistent with the ground truth '
        '(it may have more detail, but must not contradict it), else {"verdict": false}.',
        f"QUESTION:\n{question}\n\nGROUND TRUTH:\n{ground_truth}\n\nSTUDENT ANSWER:\n{answer}",
    )


def run():
    print("=" * 72)
    print("ClaimFlow RAG Evaluation (LLM-as-judge, Groq)")
    print("=" * 72)

    scores = {"faithfulness": 0, "relevancy": 0, "context_recall": 0, "correctness": 0}
    n = len(EVAL_QA)
    rows = []

    for i, qa in enumerate(EVAL_QA, 1):
        q = qa["question"]
        gt = qa["ground_truth"]

        # run the bot
        result = answer_policy_question(q)
        answer = result["answer"]
        contexts = result["policy_chunks_used"]

        # grade
        f = judge_faithfulness(answer, contexts)
        r = judge_relevancy(q, answer)
        cr = judge_context_recall(gt, contexts)
        c = judge_correctness(q, answer, gt)

        scores["faithfulness"] += f
        scores["relevancy"] += r
        scores["context_recall"] += cr
        scores["correctness"] += c

        print(f"[{i:2}/{n}] F:{'Y' if f else 'N'} R:{'Y' if r else 'N'} "
              f"CR:{'Y' if cr else 'N'} C:{'Y' if c else 'N'}  {q[:50]}")
        rows.append((q, f, r, cr, c))
        time.sleep(0.3)  # gentle on rate limits

    print("\n" + "=" * 72)
    print("RESULTS (% of questions passing each metric)")
    print("=" * 72)
    for metric, total in scores.items():
        print(f"  {metric:16}: {total}/{n}  ({total/n:.0%})")

    overall = sum(scores.values()) / (4 * n)
    print(f"\n  OVERALL          : {overall:.0%}")
    print("=" * 72)


if __name__ == "__main__":
    run()