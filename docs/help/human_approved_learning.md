# Human-Approved Learning Loop

The learning loop lets humans verify actual fixes before they become reusable knowledge.

Navigation path: AI Chat -> Developer feedback -> Learning Loop.

Steps:
1. Run an investigation from AI Chat.
2. Open the generated report.
3. Review root cause and recommendation.
4. In Developer feedback, mark whether the answer was helpful.
5. Add actual root cause, actual fix, changed SQL/procedure, tests, proof of fix, rollback, and notes.
6. Submit feedback.
7. A DBA, lead, or admin opens Learning Loop.
8. Review Pending Approval.
9. Approve or reject the feedback.
10. Approved feedback becomes reusable knowledge for future investigations.

Warnings:
- Do not approve unverified fixes.
- Feedback does not train the LLM automatically.
- Only approved human-verified knowledge is reused.
