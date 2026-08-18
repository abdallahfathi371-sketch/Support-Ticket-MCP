from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from state_graph.common.store import StateStore


def test_kill_restart_resumes_without_reexecution(tmp_path):
    db_path = tmp_path / "restart.db"
    side_effect_file = tmp_path / "side_effect.json"

    project_root = Path(__file__).resolve().parents[2]

    # ---------------------------------------------------------
    # PROCESS 1
    #
    # Execute STEP_ONE exactly once.
    # Persist the completed step.
    # Then hard-kill the process.
    # ---------------------------------------------------------

    process_one_script = r"""
import json
import os
import sys
from pathlib import Path

from state_graph.common.store import StateStore


db_path = sys.argv[1]
side_effect_file = Path(sys.argv[2])

store = StateStore(db_path)

# Simulated external / irreversible side effect.
if side_effect_file.exists():
    data = json.loads(
        side_effect_file.read_text(
            encoding="utf-8"
        )
    )
else:
    data = {
        "step_one_executions": 0
    }

data["step_one_executions"] += 1

side_effect_file.write_text(
    json.dumps(data),
    encoding="utf-8",
)

state = {
    "ticket_id": 77,
    "step_one_completed": True,
    "step_two_completed": False,
}

run_id = store.create_run(
    graph_name="no_reexecution_demo",
    ticket_id=77,
    state=state,
    current_state="STEP_ONE",
)

store.checkpoint(
    run_id,
    "STEP_ONE_COMPLETED",
    state,
)

print(
    run_id,
    flush=True,
)

# Simulate actual hard process death.
os._exit(17)
"""

    process_one = subprocess.run(
        [
            sys.executable,
            "-c",
            process_one_script,
            str(db_path),
            str(side_effect_file),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    assert process_one.returncode == 17

    run_id = process_one.stdout.strip()

    assert run_id

    # STEP_ONE happened exactly once.
    side_effect = json.loads(
        side_effect_file.read_text(
            encoding="utf-8"
        )
    )

    assert (
        side_effect["step_one_executions"]
        == 1
    )

    # ---------------------------------------------------------
    # PROCESS 2
    #
    # Recover from SQLite.
    # STEP_ONE is already completed.
    # Do NOT execute it again.
    # Continue directly with STEP_TWO.
    # ---------------------------------------------------------

    process_two_script = r"""
import json
import sys
from pathlib import Path

from state_graph.common.store import StateStore


db_path = sys.argv[1]
side_effect_file = Path(sys.argv[2])
run_id = sys.argv[3]

store = StateStore(db_path)

checkpoint = store.latest_checkpoint(
    run_id
)

if checkpoint is None:
    raise SystemExit(
        "NO_CHECKPOINT"
    )

if checkpoint["state_name"] != "STEP_ONE_COMPLETED":
    raise SystemExit(
        f"UNEXPECTED_STATE:{checkpoint['state_name']}"
    )

state = checkpoint["state"]

if state["step_one_completed"] is not True:
    raise SystemExit(
        "STEP_ONE_NOT_COMPLETED"
    )

# Critical proof:
# the previously completed side effect must not execute again.
side_effect = json.loads(
    side_effect_file.read_text(
        encoding="utf-8"
    )
)

if side_effect["step_one_executions"] != 1:
    raise SystemExit(
        "STEP_ONE_WAS_REEXECUTED"
    )

# Continue from the recovered checkpoint.
state["step_two_completed"] = True

store.checkpoint(
    run_id,
    "STEP_TWO_COMPLETED",
    state,
)

print(
    "RECOVERED_AND_CONTINUED"
)
"""

    process_two = subprocess.run(
        [
            sys.executable,
            "-c",
            process_two_script,
            str(db_path),
            str(side_effect_file),
            run_id,
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert (
        process_two.stdout.strip()
        == "RECOVERED_AND_CONTINUED"
    )

    # ---------------------------------------------------------
    # FINAL VERIFICATION
    # ---------------------------------------------------------

    store = StateStore(db_path)

    checkpoint = store.latest_checkpoint(
        run_id
    )

    assert checkpoint is not None

    assert (
        checkpoint["state_name"]
        == "STEP_TWO_COMPLETED"
    )

    state = checkpoint["state"]

    assert (
        state["step_one_completed"]
        is True
    )

    assert (
        state["step_two_completed"]
        is True
    )

    # Final proof that STEP_ONE's external side effect
    # occurred exactly once despite the process restart.
    final_side_effect = json.loads(
        side_effect_file.read_text(
            encoding="utf-8"
        )
    )

    assert (
        final_side_effect["step_one_executions"]
        == 1
    )