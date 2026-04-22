#!/bin/bash
set -e

PLAN_FILE="${1:-}"
if [ -z "$PLAN_FILE" ]; then
    echo "Usage: init-harness.sh <plan-file.md>"
    exit 1
fi

if [ ! -f "$PLAN_FILE" ]; then
    echo "Error: Plan file not found: $PLAN_FILE"
    exit 1
fi

# Check for review file
REVIEW_FILE="${PLAN_FILE%.md}-review.md"
if [ ! -f "$REVIEW_FILE" ]; then
    echo "ERROR: Plan review is required before harness initialization."
    echo "Expected review file: $REVIEW_FILE"
    echo ""
    echo "To generate a review:"
    echo "  /ralph-loop \"\$(cat .claude/harness/review-prompt.md)\" --max-iterations 10 --completion-promise \"REVIEW COMPLETE\""
    echo ""
    echo "After review, revise the plan based on findings, then re-run init-harness."
    exit 1
else
    # Check if review has been merged
    MERGED_AT=$(grep -m1 "MERGED_AT:" "$REVIEW_FILE" | sed 's/.*MERGED_AT: \(.*\) -->/\1/' || echo "")
    if [ -n "$MERGED_AT" ]; then
        echo "Review merged at $MERGED_AT. Proceeding with initialization."
    else
        # Check review verdict
        VERDICT=$(grep -m1 "^overall_verdict:" "$REVIEW_FILE" | cut -d: -f2- | sed 's/^[[:space:]]*//' || echo "unknown")
        if [ "$VERDICT" = "blocked" ]; then
            echo "ERROR: Plan review verdict is BLOCKED."
            echo "Review file: $REVIEW_FILE"
            echo "Please address the review concerns before proceeding."
            exit 1
        elif [ "$VERDICT" = "proceed-with-caution" ]; then
            echo "NOTICE: Plan review verdict is PROCEED-WITH-CAUTION."
            echo "Review file: $REVIEW_FILE"
            echo "Please review the warnings before continuing."
            echo ""
            read -p "Continue? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi
fi

mkdir -p .claude/state

# Try to extract plan metadata from frontmatter
PLAN_ID=$(grep -m1 "^plan_id:" "$PLAN_FILE" | cut -d: -f2- | sed 's/^[[:space:]]*//' || echo "unknown-plan")
PLAN_VERSION=$(grep -m1 "^version:" "$PLAN_FILE" | cut -d: -f2- | sed 's/^[[:space:]]*//' || echo "1.0.0")
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%SZ)

# Try to extract first phase and task
FIRST_PHASE=$(grep -m1 "^phase_id:" "$PLAN_FILE" | cut -d: -f2- | sed 's/^[[:space:]]*//' || echo "phase-1")
FIRST_TASK=$(grep -m1 "^task_id:" "$PLAN_FILE" | cut -d: -f2- | sed 's/^[[:space:]]*//' || echo "task-1-1")

# Try to extract first checkpoint
FIRST_CHECKPOINT=$(grep -m1 "^checkpoint_id:" "$PLAN_FILE" | cut -d: -f2- | sed 's/^[[:space:]]*//' || echo "${FIRST_PHASE}-complete")

# Create harness-state.json
cat > .claude/state/harness-state.json <<EOF
{
  "\$schema": "harness-state",
  "plan_id": "$PLAN_ID",
  "plan_version": "$PLAN_VERSION",
  "started_at": "$STARTED_AT",
  "status": "initialized",
  "current_phase": "$FIRST_PHASE",
  "current_task": "$FIRST_TASK",
  "completed_tasks": [],
  "failed_attempts": 0,
  "max_retries_per_task": 3,
  "last_iteration_at": null,
  "iteration_count": 0,
  "context_compression_level": "normal",
  "checkpoint_reached": false,
  "next_checkpoint": "$FIRST_CHECKPOINT",
  "user_stop_requested": false
}
EOF

# Create progress-log.jsonl
touch .claude/state/progress-log.jsonl

# Create checkpoint-status.json
cat > .claude/state/checkpoint-status.json <<EOF
{
  "checkpoint_id": "$FIRST_CHECKPOINT",
  "phase": "$FIRST_PHASE",
  "required_tasks": [],
  "completed_tasks": [],
  "status": "pending",
  "triggered_at": null,
  "user_approved_continue": false
}
EOF

# Create initial current-task.md
cat > .claude/state/current-task.md <<EOF
# Current Task: $FIRST_TASK

## Context
- Phase: $FIRST_PHASE
- Task: $FIRST_TASK

## Description
[Please review and update this file with the actual task description from the plan]

## Acceptance Criteria
- [ ] Criterion 1

## Dependencies
- None

## Verification Command
[Add verification command here]

## Notes from Previous Iterations
EOF

echo "Harness initialized successfully!"
echo ""
echo "Plan:       $PLAN_ID"
echo "Version:    $PLAN_VERSION"
echo "Phase:      $FIRST_PHASE"
echo "Task:       $FIRST_TASK"
echo "Checkpoint: $FIRST_CHECKPOINT"
echo ""
echo "Next steps:"
echo "  1. Review and edit .claude/state/current-task.md with the actual task details"
echo "  2. Start Ralph Loop with:"
echo "     /ralph-loop \"\$(cat .claude/harness/PROMPT.md)\" --max-iterations 50 --completion-promise \"CHECKPOINT REACHED\""
