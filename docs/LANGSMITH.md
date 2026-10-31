# LangSmith tracing - setup and how to read it (Assignment 1)

Project name used everywhere: **`aidtm-college-helpdesk`** (created automatically on the first trace).

## 1. Turn it on (2 minutes)
1. Sign in at https://smith.langchain.com -> **Settings -> API Keys -> Create API Key**. Copy it.
2. In your `.env` (never commit it) set:
```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<paste your key>
LANGSMITH_PROJECT=aidtm-college-helpdesk
LANGSMITH_ENDPOINT=https://api.smith.langchain.com      # EU accounts: https://eu.api.smith.langchain.com
LANGSMITH_MASK_PII=1
```
(The older `LANGCHAIN_API_KEY / LANGCHAIN_PROJECT / LANGCHAIN_TRACING_V2` names also work.)
3. Run the app. The sidebar must say **LangSmith ON** and `Tracing to project: aidtm-college-helpdesk`. If it says *LangSmith off*, the line below tells you why.
4. Ask a question, then open LangSmith -> **Tracing -> aidtm-college-helpdesk**. A run appears within a few seconds.

## 2. What one question looks like (1 question = 1 trace)
```
support_agent_turn              question, final answer, DATA SOURCES, total tokens, latency
 |- memory_lookup               retriever  -> which saved memory items were used (memory.json#key)
 |- groq_chat_completion  #1    llm        -> exact messages sent, the tool the model asked for, input/output tokens
 |- tool:get_fee_status         tool       -> arguments, data returned, source students.json#fees
 |- tool:search_policy          retriever  -> handbook sections returned, with score (e.g. HB-02)
 '- groq_chat_completion  #2    llm        -> final answer, input/output tokens
```

## 3. "Where did this answer come from?"
- Root run -> **Outputs -> `data_sources`**: `students.json#fees`, `student_handbook.md#HB-02`, `memory.json#preferred_contact` ...
  `model_only (no tool, document or memory used)` means the model answered without any data - a red flag for fee or policy questions.
- `tool:search_policy` -> the retrieved documents with `section`, `title`, `score`.
- First `groq_chat_completion` -> **Input** shows the exact context the model received.

## 4. "Where were my tokens used?"
- Runs table: **Tokens** per trace and per child run (Groq's own `usage` numbers).
- Root run -> Outputs -> **`token_breakdown`**: one row per model call ("asked for tool: ..." / "final answer").
- Each model call -> Metadata -> **`input_token_split_estimate`**: *estimated* split of the input tokens into `system_prompt`, `tool_schemas`, `memory`, `chat_history`, `current_question`, `tool_calls`, `tool_results` (characters / 4, scaled to the real total - totals are exact, the split is approximate).
- Typical finding for your video: most input tokens are the fixed system prompt + tool definitions; the second model call is larger because it also carries the tool result.
- The same table is in the app under every answer: **Trace details**.

## 5. Filtering and grouping
| Want | Do |
|---|---|
| One whole conversation | **Threads** view (metadata `thread_id`) |
| Evaluation runs | Tag `eval` plus the test id (`T1`..`T9`) after `python eval.py` |
| One student | Metadata `user_id` |
| One tool | Tag = the tool name, e.g. `search_policy` |

## 6. Privacy
Before anything is uploaded: OTP / password / PIN / CVV / card / Aadhaar patterns are **always redacted** (and removed before the model even sees them); emails become `b***@example.edu`, phone numbers `**********0001` (`LANGSMITH_MASK_PII=0` disables the last two). `tests/test_observability.py` captures exactly what would be uploaded and proves it.

## 7. Safe by design
Tracing is off unless `LANGSMITH_TRACING=true` **and** a real key is set. If LangSmith is down, blocked or the key is wrong, the app keeps working at normal speed. Traces upload in the background; `eval.py` flushes at the end.

## 8. Troubleshooting
| Symptom | Fix |
|---|---|
| Sidebar says "LangSmith off" | Read the reason line; set `LANGSMITH_TRACING=true` and a real `LANGSMITH_API_KEY`, restart |
| No runs in LangSmith | Check the project name and workspace; EU users need the EU endpoint; wait ~10 s |
| Console: `Failed to multipart ingest runs` | Network blocked or wrong endpoint/key; the app still works |
| `401/403` | Create a new API key |
| Trace limit reached | The free plan has a monthly trace limit (check your plan). One question = one trace; set `LANGSMITH_TRACING=false` when not demoing |

## 9. Add to your video (1 minute)
Ask 2-3 questions (or run `python eval.py`), switch to LangSmith -> project `aidtm-college-helpdesk`. Open one trace: show the tree, click `tool:search_policy` (HB-02 + score), click a `groq_chat_completion` (messages in, tokens out), show `data_sources` and `token_breakdown`. Say: "this proves where each answer came from and where every token went."
