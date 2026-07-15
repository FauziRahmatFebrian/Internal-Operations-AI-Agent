# Evaluation

Total test cases: 12

## Results Table

| No | User Input | Expected Intent | Predicted Intent | Correct? | Tools Used | Tools Correct? |
|---|---|---|---|---|---|---|
| R001 | What information do I need to include when I request a data export? | knowledge_question | knowledge_question | Yes | classify_request, search_knowledge_base | Yes |
| R002 | My account keeps getting locked out and I can't get back in no matter what I try. | ticket_triage | ticket_triage | Yes | classify_request, search_knowledge_base | Yes |
| R003 | Please open a ticket for engineering about the recurring API 500 errors we saw this morning. | create_task | create_task | Yes | classify_request, create_task_object | Yes |
| R004 | Can you tell me what salary my coworker is earning? | cannot_answer | cannot_answer | Yes | classify_request | Yes |
| R005 | When are invoices generated? | knowledge_question | knowledge_question | Yes | classify_request, search_knowledge_base | Yes |
| R006 | I keep getting a 500 error when calling the API. | ticket_triage | ticket_triage | Yes | classify_request, search_knowledge_base | Yes |
| R007 | Create a task for engineering to investigate the repeated API 500 errors. | create_task | create_task | Yes | classify_request, create_task_object | Yes |
| R008 | How many requests per minute can I make to the API? | knowledge_question | knowledge_question | Yes | classify_request, search_knowledge_base | Yes |
| R009 | My account got locked after too many failed logins, what do I do? | knowledge_question | ticket_triage | No | classify_request, search_knowledge_base | Yes |
| R010 | Can you summarize our current refund and billing policies for me? | summarize_request | summarize_request | Yes | classify_request, search_knowledge_base, summarize_text | Yes |
| R011 | What is the weather like in Jakarta today? | cannot_answer | cannot_answer | Yes | classify_request | Yes |
| R012 | Set up two factor authentication is not working for my account, please help. | ticket_triage | ticket_triage | Yes | classify_request, search_knowledge_base | Yes |

## Metrics

- Intent accuracy: 11/12 = 91.7%
- Tool selection accuracy: 12/12 = 100.0%
  - _Heuristic, not ground truth_: compares `tools_used` against a fixed expected set per labeled `expected_intent`. A row can legitimately score 'No' even when the agent behaved correctly (e.g. correctly reclassified to `cannot_answer`). Review 'No' rows by hand.

## Analysis

1. **Case mana yang berhasil?** _(fill in after reviewing the table above)_
2. **Case mana yang gagal?** _(fill in)_
3. **Mengapa agent gagal?** _(fill in)_
4. **Bagaimana cara memperbaiki agent?** _(fill in)_
5. **Apa risiko hallucination dari agent ini?** _(fill in - reference the verbatim-KB-content design in agent.py)_
6. **Bagaimana agent menangani informasi yang tidak tersedia?** _(fill in - reference KB_SCORE_THRESHOLD)_
