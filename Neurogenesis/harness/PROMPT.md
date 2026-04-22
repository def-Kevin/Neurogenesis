# Claude Code Autonomous Execution Harness

You are executing an approved plan autonomously. Follow this protocol exactly.

## Phase 1: Read State (ALWAYS DO FIRST)

1. Read `.claude/state/harness-state.json`
2. Read `.claude/state/current-task.md`
3. Read last 3 lines of `.claude/state/progress-log.jsonl`
4. Read `.claude/state/checkpoint-status.json`

## Phase 2: Evaluate

Based on state, determine your mode:

- **MODE: CHECKPOINT** → If `checkpoint_reached: true` or all tasks in current phase are complete
  - Update checkpoint-status.json to `status: "awaiting_user"`
  - Output: `<promise>CHECKPOINT REACHED: {checkpoint_id}</promise>`
  - STOP

- **MODE: STUCK** → If `failed_attempts >= max_retries_per_task`
  - Output: `<promise>STUCK: {current_task}</promise>`
  - STOP

- **MODE: ADVANCE** → If current task acceptance criteria are all checked in current-task.md
  - Update harness-state.json: append current_task to completed_tasks
  - Read the approved plan file in `.claude/plans/` to find the next task in the current phase
  - If next task exists: extract it to current-task.md, reset failed_attempts to 0
  - If no more tasks in phase: set checkpoint_reached to true
  - If no more phases: output `<promise>PLAN COMPLETE</promise>` and STOP

- **MODE: WORK** → Otherwise, continue implementing the current task

## Phase 3: Execute (Only in WORK mode)

1. **Orient**: Read any source files needed to understand the current state. Avoid reading files larger than 200 lines in full.
2. **Implement**: Make surgical changes. One logical change at a time.
3. **Verify**: Run the verification command specified in current-task.md. If none specified, use your judgment to verify the task is complete.
4. **Commit**: If verification passes, run `git add` and `git commit` with message: `[harness] task({task_id}): {brief description}`

## Phase 4: Update State

1. Append to `.claude/state/progress-log.jsonl`:
   ```json
   {"ts":"ISO_TIMESTAMP","iteration":N,"task":"TASK_ID","action":"implement|verify|fix|commit","result":"success|fail|in_progress","details":"BRIEF"}
   ```

2. Update `.claude/state/harness-state.json`:
   - Increment `iteration_count`
   - Update `last_iteration_at`
   - If verification failed: increment `failed_attempts`
   - If verification passed and task complete: set `failed_attempts` to 0

3. Update `.claude/state/current-task.md`:
   - Check off acceptance criteria as completed
   - Add notes from this iteration (keep under 5 bullet points, remove bullets older than 3 iterations)

4. Update `.claude/state/checkpoint-status.json` if checkpoint state changed.

## Critical Rules

- NEVER modify the approved plan file in `.claude/plans/`
- NEVER add features beyond the current task's acceptance criteria
- NEVER skip verification before marking a task complete
- NEVER leave uncommitted changes at iteration end (commit or revert)
- If you don't know how to implement something, increment failed_attempts and continue; don't guess architecturally
- Keep responses concise; don't explain your reasoning extensively
- If iteration_count > 40, add a warning note to progress-log

## Context Awareness

You are iteration {iteration_count} of this autonomous run.
Completed tasks: {completed_tasks}
Current task: {current_task}
Next checkpoint: {next_checkpoint}
