# Conversation Metadata Auto-Fill Rollout

Current issues: new conversations are always titled “New Chat”, the `summary` and `system_prompt` fields stay empty, and the lightweight LLM for query rewrites only runs when a feature flag is enabled. Objective: enable the lightweight LLM by default so every conversation is classified, and automatically populate the title, summary, and system prompt to improve retrieval and multi-turn chat context.

## Goals
- Drop the `QUERY_REWRITE_ENABLED` toggle and make the lightweight LLM classifier run for every user query.
- Reuse the classifier output to auto-populate `Conversation.title`, `Conversation.summary`, and `Conversation.system_prompt`.
- Ensure existing conversations continue to function without retroactive metadata.

## Work Breakdown

### 1. Remove the Query Rewrite feature flag
- `backend/app/core/config.py`
  - Delete `QUERY_REWRITE_ENABLED` field and its entry inside `dynamic_settings_defaults`.
  - Regenerate any derived settings or cached defaults that referenced the flag.
- `backend/app/modules/admin_settings/schemas.py`
  - Drop `QUERY_REWRITE_ENABLED` from request/response models.
- `backend/app/modules/llm/strategy.py`
  - Remove `StrategyContext.query_rewrite_enabled`; always assume rewriting is on.
  - Simplify `resolve_rag_parameters` so it no longer reads the flag from Redis/admin overrides.
- `frontend/src/components/AdminSettings/settingDefinitions.ts` and `frontend/src/types/adminSettings.ts`
  - Delete the setting definition, labels, and type unions.
- Update any documentation or `.env.example` references to the flag.

### 2. Extend the classifier response contract
- `backend/app/modules/llm/intent_classifier.py`
  - Keep the existing prompt focused on scenario classification plus query rewrite; no new fields needed from this call.
  - Ensure sanitizers for scenario/confidence/tags/rewritten query remain robust (length checks, normalized casing).
  - Extend `ClassificationResult` to expose any structured data required by downstream consumers (e.g., include the original payload, sanitized dict, tags, and scenario).
  - Keep `rewritten_query` for retrieval use but remove the gate that blanked it when the old flag was false.
- Ensure logging redacts or truncates the new strings as needed.

### 3. Persist metadata on conversations
- `backend/app/modules/llm/repository.py`
  - Accept the default `"New Chat"` title until the async metadata job updates it; no schema change required.
- `backend/app/modules/llm/service.py` (or create a new `conversation_metadata.py`)
  - Implement `generate_conversation_metadata(conversation_id, messages, classifier_result)`:
    - Collect recent messages (e.g., 6 most recent user/assistant pairs) via `get_recent_messages`.
    - Build a templated prompt combining the classifier output with the conversation transcript.
    - Call the same lightweight model to produce refined `title` and `summary` only.
    - Apply safety clamps (max length, ensure multilingual support by matching detected language).
    - Choose the system prompt by mapping the classifier’s scenario/tags to the predefined templates (Step 5); no LLM generation for this field.
  - Return a dataclass with sanitized fields (title, summary, selected system prompt) for repository consumption.
  - Add helper method `update_conversation_metadata(...)` that writes the generated title, summary, and system prompt only.

### 4. Invoke metadata refresh on new chat turns
- `backend/app/modules/tasks/workers/chat_tasks.py`
  - After persisting the user + assistant messages, enqueue an async job (via the existing task queue) that calls the metadata generator.
  - The job should:
    1. Fetch the latest classifier result from the request context (pass the `ClassificationResult` instance or a serializable form through the worker payload).
    2. Generate metadata with the helper from step 3.
    3. Persist via `update_conversation_metadata`.
  - Add retry + timeout handling so failed metadata generation does not block the chat response.
- `backend/app/modules/llm/strategy.py`
  - Extend `StrategyResult` to carry the `ClassificationResult` object so the worker can forward it to the metadata job without relying on logs alone.

### 5. System prompt templates
- Define a richer catalogue of templates that cover the assistant’s common modes; minimum set:
  - `question_troubleshooting`: Q&A, diagnostics, incident handling.
  - `precise_instruction`: concise step-by-step guidance or command sequences.
  - `broad_overview`: high-level explanations, comparisons, summaries.
  - `document_focus`: answers constrained to supplied documents.
  - `analysis_reasoning`: deep reasoning, trade-off analysis, root-cause exploration.
  - `coding_help`: code generation, review, refactoring, API usage.
  - `brainstorming`: idea generation, creative exploration.
  - `translation_localization`: translation or localization requests.
  - `unknown_fallback`: safety net when no template matches confidently.
- Recommended defaults:
  - `question_troubleshooting`: “You are an expert troubleshooting assistant. Ask for missing details, reason step-by-step, and provide actionable fixes grounded in verified knowledge.”
  - `precise_instruction`: “You are a concise technical assistant. Provide exact instructions or factual answers with clear steps or code snippets when helpful.”
  - `broad_overview`: “You deliver high-level overviews and comparisons. Summarize key points, highlight trade-offs, and keep explanations accessible.”
  - `document_focus`: “Act as a retrieval-grounded assistant. Only reference the supplied document(s); cite relevant sections and avoid fabricating external facts.”
  - `analysis_reasoning`: “You are a critical analyst. Decompose problems, evaluate alternatives, and explain your reasoning transparently before concluding.”
  - `coding_help`: “You are a senior software engineer. Produce idiomatic, well-commented code, explain the approach, and point out potential pitfalls or tests.”
  - `brainstorming`: “You are a creative collaborator. Generate diverse, high-quality ideas, explore variations, and note constraints or next steps.”
  - `translation_localization`: “You are a professional translator. Preserve meaning, tone, and domain-specific terminology while adapting content to the target locale.”
  - `unknown_fallback`: “Default to a helpful AI assistant. Clarify the user’s intent when needed and keep responses accurate, polite, and safe.”
- Define a mapping of classifier scenarios/tags to the templates (e.g., `SCENARIO_SYSTEM_PROMPTS` constant). Examples:
  - `question`/`troubleshooting` → `question_troubleshooting`.
  - `precise`/`procedural` → `precise_instruction`.
  - `broad`/`overview` → `broad_overview`.
  - `document_focus` → `document_focus`.
  - `analysis`/`root_cause` → `analysis_reasoning`.
  - `code`/`api_usage` → `coding_help`.
  - `brainstorm`/`creative` → `brainstorming`.
  - `translation`/`localization` → `translation_localization`.
- Keep the mapping close to the metadata generator and expose an override hook (admin setting or config) if future tenants need custom wording.
- The metadata job selects the highest-priority matching template; if nothing matches, fall back to `unknown_fallback`.

### 6. API surface updates
- `backend/app/modules/llm/schemas.py`
  - Expose the enriched fields (`title`, `summary`, `system_prompt`) in the conversation response DTOs if not already present.
- `backend/app/api/v1/routes/...` (conversation endpoints)
  - Ensure response models include the enriched fields and update serializers if they previously defaulted to `"New Chat"`.
- Ensure GET/list endpoints include the new data, including summaries in list previews.
- Frontend conversation list/detail pages
  - Replace the hard-coded "New Chat" label with the server-provided title.
  - Show the summary (if present) in conversation previews/tooltips.

### 7. Testing & validation
- Unit tests:
  - Sanitizers for classifier outputs and metadata results.
  - Repository updates ensuring partial updates (e.g., only summary changes).
- Integration tests (requires Docker stack):
  - Simulate a conversation and verify metadata is written after the assistant reply.
- Manual QA:
  - Verify conversation list shows AI-generated titles.
  - Check multilingual conversations for correct language handling.
  - Confirm system prompts influence subsequent assistant responses as expected.

### 8. Operational considerations
- Monitor classifier usage metrics; the removal of the feature flag increases baseline traffic.
- Add logging around metadata generation failures with conversation IDs for easy replays.
- Document the new behaviour in `doc/` and update any runbook sections that referenced manual title editing.

## Decisions (previously open questions)
- We will NOT store the last classifier JSON on `Conversation`; logs are sufficient.
- Summaries may vary in length; no hard character cap beyond generator safeguards.
- Generated system prompts remain internal and are not exposed for user editing.
