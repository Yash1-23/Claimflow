"""
Ragas Evaluation Dataset for ClaimFlow Policy Chatbot

The QUESTION + GROUND_TRUTH pairs below are authored by hand from the policy document
(category limits + the Section 13 FAQ). The 'answer' and 'contexts' fields are filled
automatically at eval time by running each question through answer_policy_question().

>>> Verify the limit-based ground_truths against your PDF; FAQ answers are taken
    directly from Section 13. <<<
"""

EVAL_QA = [
    # ============================================
    # CATEGORY LIMIT QUESTIONS (from policy tables)
    # ============================================
    {
        "question": "What is the training course budget for a junior employee?",
        "ground_truth": "A junior employee (L1-L3) has a Courses/Certs training budget of Rs 10,000.",
    },
    {
        "question": "What is the hotel accommodation limit per night in a metro city?",
        "ground_truth": "In a metro (Tier 1) city like Mumbai or Bengaluru, the accommodation limit is Rs 5,000 per night for a 3-star hotel.",
    },
    {
        "question": "Who is eligible to book a domestic flight?",
        "ground_truth": "Domestic flights are limited to Manager level and above, or with special approval. The limit is Rs 12,000, economy only, booked 14+ days in advance.",
    },
    {
        "question": "What is the medical OPD limit per claim for an employee?",
        "ground_truth": "The per-claim medical limit for an employee (self) is Rs 15,000, with a submission window of 30 days from treatment.",
    },
    {
        "question": "What is the AC train travel limit for employees?",
        "ground_truth": "AC train travel is allowed for all employees up to Rs 3,500, in 3-Tier AC, booked 7+ days in advance.",
    },
    {
        "question": "What is the conference budget for a senior employee?",
        "ground_truth": "A senior employee (L4-L6) has a conference budget of Rs 12,000.",
    },

    # ============================================
    # FAQ QUESTIONS (from Section 13, answers verbatim from policy)
    # ============================================
    {
        "question": "I lost my original receipt. Can I still claim?",
        "ground_truth": "Yes, in most categories. Provide a bank statement showing the transaction plus secondary proof (email confirmation or booking screenshot), and the manager must certify the expense was genuine. Food claims above Rs 300 without a receipt are auto-rejected with no exception.",
    },
    {
        "question": "My manager is on leave and I need urgent approval. What do I do?",
        "ground_truth": "Contact the next level manager (your manager's manager) for interim approval and document this in the claim form. The system accepts delegation approval.",
    },
    {
        "question": "I paid for a colleague's expense from my account. Can I claim it?",
        "ground_truth": "Yes. Submit the claim with both employees' names. Your colleague must confirm via email that they did not and will not file a separate claim for the same expense.",
    },
    {
        "question": "Can I claim an expense that is 3 months old?",
        "ground_truth": "No. All categories have hard deadlines and claims older than the maximum extension period are auto-rejected. No CFO-level override is available for claims older than 90 days, except hospitalization.",
    },
    {
        "question": "My claim was approved but I haven't received payment. Who do I contact?",
        "ground_truth": "Check the claim status in the portal. If it shows 'Approved' but payment is not received within the SLA, raise a ticket to finance@claimflow.in with your claim ID and bank details.",
    },
    {
        "question": "Can I claim in USD for a domestic expense paid via international card?",
        "ground_truth": "No. All domestic expenses must be claimed in INR. If you paid in USD domestically, convert using the RBI rate on the transaction date and claim in INR.",
    },
    {
        "question": "I booked a flight in advance and the price changed. Can I rebook?",
        "ground_truth": "Yes, if cancellation plus rebooking is cheaper than the original. Attach both tickets and a price comparison; if the net saving is positive, Finance will approve.",
    },
    {
        "question": "Can I claim alcohol served at a client dinner?",
        "ground_truth": "No. Alcohol is never reimbursable under any category or circumstances. Request an itemized bill and claim only food and non-alcoholic beverages.",
    },
    {
        "question": "My project code hasn't been created yet but I need to travel now. What do I do?",
        "ground_truth": "Use the temporary code TEMP-PENDING-2026 and update the actual code within 5 days of claim submission. Claims older than 10 days with a TEMP code are auto-rejected.",
    },
    {
        "question": "I'm on probation. What can I claim?",
        "ground_truth": "During probation you can claim travel, accommodation, and food during official outstation travel (all with pre-approval), and medical for self only. No equipment and no training budget during probation.",
    },
    {
        "question": "The AI system flagged my claim as suspicious but it's genuine. What do I do?",
        "ground_truth": "Do not panic. The compliance team reviews flagged claims within 2 working days and will contact you for clarification. Provide supporting documents promptly; most legitimate flagged claims are cleared within 3 working days.",
    },
    {
        "question": "Can my spouse claim medical expenses directly?",
        "ground_truth": "No. All claims must be filed by the employee. The spouse's medical expenses are claimed by the employee, as the covered person, on their behalf.",
    },
]

if __name__ == "__main__":
    print(f"{len(EVAL_QA)} evaluation Q&A pairs defined.")
    for i, qa in enumerate(EVAL_QA, 1):
        print(f"[{i}] {qa['question']}")