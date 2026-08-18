from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_checkpoint_survives_process_restart(tmp_path):
    db_path = tmp_path / "restart.db"

    project_root = Path(__file__).resolve().parents[2]

    # ---------------------------------------------------------
    # Process 1:
    # create run + checkpoint, then terminate.
    # ---------------------------------------------------------

    create_script = r"""
import sys

from state_graph.common.store import StateStore


db_path = sys.argv[1]

store = StateStore(db_path)

state = {
    "ticket_id": 99,
    "step_one_completed": True,
    "step_two_completed": False,
}

run_id = store.create_run(
    graph_name="restart_demo",
    ticket_id=99,
    state=state,
    current_state="STEP_ONE",
)

state["step_two_completed"] = True

store.checkpoint(
    run_id,
    "STEP_TWO",
    state,
)

print(run_id)
"""

    process_one = subprocess.run(
        [
            sys.executable,
            "-c",
            create_script,
            str(db_path),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    run_id = process_one.stdout.strip()

    assert run_id

    # ---------------------------------------------------------
    # Process 2:
    # completely new Python process loads the checkpoint.
    # ---------------------------------------------------------

    recover_script = r"""
import json
import sys

from state_graph.common.store import StateStore


db_path = sys.argv[1]
run_id = sys.argv[2]

store = StateStore(db_path)

checkpoint = store.latest_checkpoint(run_id)

if checkpoint is None:
    raise SystemExit("NO_CHECKPOINT")

print(json.dumps(checkpoint))
"""

    process_two = subprocess.run(
        [
            sys.executable,
            "-c",
            recover_script,
            str(db_path),
            run_id,
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    recovered = json.loads(
        process_two.stdout
    )

    # ---------------------------------------------------------
    # Verify exact persisted state.
    # ---------------------------------------------------------

    assert recovered["state_name"] == "STEP_TWO"

    state = recovered["state"]

    assert state["ticket_id"] == 99
    assert state["step_one_completed"] is True
    assert state["step_two_completed"] is True