from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_sla_breach_checkpoint_survives_process_restart(tmp_path):
    """
    Kill-process proof for Graph #2: a second Python process must
    resume from the durable checkpoint without redoing DETECT_BREACH.
    """

    db_path = tmp_path / "sla_restart.db"
    project_root = Path(__file__).resolve().parents[2]

    create_script = r"""
import sys

from state_graph.graphs.sla_breach_escalation import (
    start_sla_breach_escalation,
)

db_path = sys.argv[1]

run_id, result = start_sla_breach_escalation(
    ticket_id=1,
    priority="High",
    hours_open=48.0,
    issue_summary="Login API returns 500",
    db_path=db_path,
)

print(run_id)
print(result)
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

    lines = [
        line.strip()
        for line in process_one.stdout.splitlines()
        if line.strip()
    ]

    assert len(lines) >= 2
    run_id = lines[0]
    assert lines[1].startswith("WAITING_HITL:")

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

print(json.dumps({
    "state_name": checkpoint["state_name"],
    "completed_steps": checkpoint["state"].get("completed_steps"),
    "selected_strategy": checkpoint["state"].get("selected_strategy"),
    "status": checkpoint["state"].get("status"),
}))
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

    recovered = json.loads(process_two.stdout)

    assert recovered["state_name"] == "WAITING_FOR_ADMIN"
    assert recovered["status"] == "WAITING_HITL"
    assert "DETECT_BREACH" in recovered["completed_steps"]
    assert "TREE_OF_THOUGHTS" in recovered["completed_steps"]
    assert recovered["selected_strategy"] is not None
