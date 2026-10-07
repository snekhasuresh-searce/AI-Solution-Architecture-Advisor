"""Export a saved recommendation to DOCX and/or PDF.

Examples:
  python scripts/export.py 6934db91                 # both formats, next to the .md
  python scripts/export.py 6934db91 --format pdf
  python scripts/export.py outputs/recommendation_6934db91.md --out ~/Desktop
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from advisor import report  # noqa: E402
from advisor.export import EXPORTERS  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Export a recommendation to DOCX / PDF")
    p.add_argument("run", help="Run id (e.g. 6934db91) or path to a recommendation .md file")
    p.add_argument("--format", choices=[*EXPORTERS, "all"], default="all")
    p.add_argument("--out", help="Output directory (default: next to the Markdown file)")
    args = p.parse_args()

    source = Path(args.run) if args.run.endswith(".md") else report.path_for(args.run)
    if not source.exists():
        sys.exit(f"Not found: {source}")
    markdown = source.read_text(encoding="utf-8")
    out_dir = Path(args.out).expanduser() if args.out else source.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    for fmt in EXPORTERS if args.format == "all" else [args.format]:
        render, _ = EXPORTERS[fmt]
        target = out_dir / f"{source.stem}.{fmt}"
        target.write_bytes(render(markdown))
        print(target)


if __name__ == "__main__":
    main()
