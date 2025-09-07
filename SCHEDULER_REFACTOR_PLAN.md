# Scheduler Refactor Plan — schedule_id-first (direct refactor)

Goal: keep TaskConfig as a static template (what/when/how), and make Redis/TaskIQ the single source of truth for runtime scheduling state. All runtime operations (start/stop/pause/resume/unregister) are driven by `schedule_id` (TaskIQ schedule identifier), not `config_id`.

Why: deleting a DB `config_id` currently leaves an orphan schedule in Redis that cannot be managed because operations are `config_id`-based. Using `schedule_id` for control removes DB coupling and enables future multi-instance support.

Final Decisions (authoritative)
- schedule_id format: `scheduled_task:{config_id}:{uuid}` (uuid v4).
- Persistence: do NOT persist `schedule_id` in the database. Use a Redis index as the exclusive runtime mapping between `config_id` and `schedule_id`.
- UI/UX: “expandable parent-child list” — parent is TaskConfig; expand to list all active schedule instances (children) with per-instance actions.

High‑Level Design
- `schedule_id` is the primary runtime identifier for schedules and state/history.
- `config_id` is metadata and an index key to group schedules: `config_id -> {schedule_id...}` (Set in Redis).

Direct Refactor Steps (no backward compatibility)

Step 1 — Keyspace and ID helpers
1. Update `backend/app/infrastructure/redis/keyspace.py`:
   - Add schedule-scoped keys:
     - `schedule_status(schedule_id)` -> `status:{schedule_id}`
     - `schedule_metadata(schedule_id)` -> `meta:{schedule_id}`
     - `schedule_history(schedule_id)` -> `history:{schedule_id}`
     - `schedule_stats(schedule_id)` -> `stats:{schedule_id}` (optional)
   - Add config index key:
     - `config_index(config_id)` -> `index:config:{config_id}` (Set of schedule_ids)
   - Remove/stop using config-scoped status/meta/history keys.
   - Provide a pure helper for building schedule IDs: `def build_schedule_id(config_id: Union[int,str], uid: Optional[str] = None) -> str` returning `scheduled_task:{config_id}:{uuid or uid}`. Do not persist this anywhere.

Step 2 — State/History service (schedule_id-only)
1. Rewrite `backend/app/infrastructure/scheduler/status.py` to be schedule_id-centric:
   - `set_schedule_status(schedule_id: str, status)` / `get_schedule_status(schedule_id: str)`
   - `set_schedule_metadata(schedule_id: str, metadata)` / `get_schedule_metadata(schedule_id: str)`
   - `add_schedule_history_event(schedule_id: str, event)` / `get_schedule_history(schedule_id: str, limit=...)`
   - Composite: `get_schedule_full_info(schedule_id: str, history_limit=...)`
2. Add index helpers:
   - `add_schedule_to_index(config_id: int, schedule_id: str)`
   - `remove_schedule_from_index(config_id: int, schedule_id: str)`
   - `list_schedule_ids(config_id: int) -> List[str]`
3. Delete/replace all `config_id`-based status/history/metadata methods.

Step 3 — Core (TaskIQ) operations by schedule_id
1. Modify `backend/app/infrastructure/scheduler/core.py`:
   - `register_task(self, config: TaskConfig) -> str`: build `schedule_id = scheduled_task:{config_id}:{uuid4}`; create `ScheduledTask` with this id and labels `{config_id, task_type, scheduler_type}`; return the `schedule_id` on success (raise/return None on failure).
   - `unregister_task(self, schedule_id: str) -> bool`: delete by `schedule_id` only.
   - `get_all_schedules(self) -> List[Dict]]`: must include `schedule_id`, `config_id`, `labels`, `next_run`.
   - Optional: `list_schedule_ids_by_config(config_id: int)` using labels or (preferably) the Redis index maintained by Step 2.

Step 4 — Service layer (schedule_id-only public API)
1. Update `backend/app/infrastructure/scheduler/scheduler.py`:
   - `register_task(config: TaskConfig) -> Tuple[bool, str]`: call core.register_task → `schedule_id`; set status ACTIVE and metadata by `schedule_id`; add to `config_index(config_id)`; record history by `schedule_id`.
   - `pause(schedule_id: str)`, `resume(schedule_id: str)`, `unregister(schedule_id: str)` operate only by `schedule_id` and update state/history accordingly.
   - `get_schedule_full_info(schedule_id: str)` returns consolidated info via state service.
   - `list_config_schedules(config_id: int) -> List[str]` reads the Redis index.

Step 5 — API, Schemas, and UI
1. Schemas (`backend/app/modules/tasks/schemas.py`):
   - Include `schedule_id` on schedule DTOs/responses and in any list/detail views.
2. API routes (`app/api/v1/routes/*`):
   - Mutating endpoints by `schedule_id` only:
     - `POST /tasks/schedules/{schedule_id}/pause`
     - `POST /tasks/schedules/{schedule_id}/resume`
     - `DELETE /tasks/schedules/{schedule_id}` (unregister)
   - Listing endpoints:
     - `GET /tasks/configs/{config_id}/schedules` → uses the Redis index to list child schedule_ids.
     - `GET /tasks/schedules/{schedule_id}` → returns full info.
3. Frontend UI/UX (expandable parent-child list):
   - Parent list: TaskConfig cards/rows with name, type, base schedule template, actions to add a new schedule instance from the template.
   - Expand reveals child instances (active schedules) with `schedule_id`, next run time, status, and actions (pause/resume/unregister).
   - New instance dialog derives defaults from the TaskConfig template; on success, UI adds the new child row.

Step 6 — Startup and Orphan handling
1. `backend/app/main.py` startup:
   - For each TaskConfig that should be scheduled: register a schedule instance and capture returned `schedule_id`; index and set state by id.
   - If you only want a single default instance per template at boot, check `list_config_schedules(config_id)` first and only create one if none exists.
2. Orphan cleanup:
   - Add `list_orphan_schedules()` to find schedules whose `config_id` label does not exist in DB; call `unregister(schedule_id)` and record a history event by `schedule_id`.

Step 7 — One-time cleanup (destructive)
1. Remove all legacy config-scoped keys in Redis: `schedule:status:{config_id}`, `schedule:meta:{config_id}`, `schedule:history:{config_id}`.
2. Remove any schedules created with the old id pattern (e.g., `scheduled_task_{config_id}`) and recreate using `scheduled_task:{config_id}:{uuid}` as needed.

Step 8 — Tests (no compatibility tests)
1. Keyspace/index unit tests (create/read/remove from `config_index`).
2. Core/service tests registering returns `schedule_id` and allows pause/resume/unregister by id.
3. Orphan detection and cleanup tests.

Concrete File‑Level TODOs
- `backend/app/infrastructure/redis/keyspace.py`
  - Add: `build_schedule_id(config_id, uid=None)`, `schedule_status(schedule_id)`, `schedule_metadata(schedule_id)`, `schedule_history(schedule_id)`, `schedule_stats(schedule_id)`, `config_index(config_id)`.
  - Remove old config-scoped helpers from usage.
- `backend/app/infrastructure/scheduler/status.py`
  - Replace with schedule_id-based state/meta/history methods and index helpers only.
- `backend/app/infrastructure/scheduler/core.py`
  - `register_task(config) -> schedule_id` using the new format; `unregister_task(schedule_id)`.
- `backend/app/infrastructure/scheduler/scheduler.py`
  - Public API operates only on `schedule_id`; register writes state/meta/history by id and updates the index.
- `backend/app/modules/tasks/schemas.py`
  - Add `schedule_id` fields to schedule-related models.
- `app/api/v1/routes/*`
  - Replace mutating endpoints to accept `schedule_id` path params; add listing/detail endpoints as specified.
- `backend/app/main.py`
  - Capture `schedule_id` on startup registration; skip creating if index already contains one (if single default instance desired).

Acceptance Criteria
- All runtime control paths operate using `schedule_id` only.
- Redis index is the sole mapping between `config_id` and `schedule_id` at runtime.
- UI shows TaskConfig parents with expandable schedule instance children; each child is independently controllable by `schedule_id`.
