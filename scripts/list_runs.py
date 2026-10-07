"""Print the most recent runs from the run log (Postgres or SQLite)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from advisor.storage import recent_runs  # noqa: E402

for row in recent_runs():
    run_id, created, domains, agents, status, overall, rounds = row
    print(f"{created[:19]}  {run_id}  {status:<9}  score={overall}  rounds={rounds}  domains={domains}  agents={agents}")
