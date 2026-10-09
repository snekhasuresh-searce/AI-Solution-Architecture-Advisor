"""Run the advisor from the command line, without the web UI.

Examples:
  python scripts/run.py --scenario 1
  python scripts/run.py --text "Build a REST API with PostgreSQL"
  python scripts/run.py --file requirements.pdf
  python scripts/run.py --all            # all demo scenarios
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from advisor.agent import root_agent  # noqa: E402
from advisor.intake import read_requirement_file  # noqa: E402

APP = "solution_advisor"


async def run_once(text: str, verbose: bool = False) -> None:
    runner = InMemoryRunner(agent=root_agent, app_name=APP)
    session = await runner.session_service.create_session(app_name=APP, user_id="cli")
    message = types.Content(role="user", parts=[types.Part(text=text)])
    print(f"\n{'=' * 80}\nREQUIREMENT: {text[:200]}\n{'=' * 80}")
    async for event in runner.run_async(user_id="cli", session_id=session.id, new_message=message):
        if not (event.content and event.content.parts):
            # Sub-agent JSON is kept out of the chat; show it from the state update instead.
            if verbose and event.author != root_agent.name and event.actions and event.actions.state_delta:
                print(f"\n[{event.author}] {json.dumps(event.actions.state_delta, default=str)[:300]}...")
            continue
        text_out = "".join(p.text or "" for p in event.content.parts)
        if event.author == root_agent.name:
            print(f"\n[{event.author}]\n{text_out}")
        elif verbose:
            print(f"\n[{event.author}] {text_out[:300]}...")


def main() -> None:
    p = argparse.ArgumentParser(description="Nexora — AI solution architecture advisor (CLI)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="Requirement as free text")
    g.add_argument("--file", help="Requirement as .txt, .md, .pdf or .docx")
    g.add_argument("--scenario", type=int, help="Demo scenario number (1-5)")
    g.add_argument("--all", action="store_true", help="Run demo scenarios 1-4")
    p.add_argument("-v", "--verbose", action="store_true", help="Also print agent outputs")
    args = p.parse_args()

    scenarios = sorted((ROOT / "scenarios").glob("*.txt"))
    if args.all:
        texts = [s.read_text().strip() for s in scenarios[:4]]
    elif args.scenario:
        texts = [scenarios[args.scenario - 1].read_text().strip()]
    elif args.file:
        texts = [read_requirement_file(args.file)]
    else:
        texts = [args.text]

    for t in texts:
        asyncio.run(run_once(t, args.verbose))


if __name__ == "__main__":
    main()
