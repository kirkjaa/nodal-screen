"""Build the static copy of NODAL Screen for GitHub Pages into out/pages.

The app reads its data as plain files, so the static copy shows everything the
Cloud Run service does except live AI drafts (there is no API on a static host).
    python scripts/build_pages.py
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "pages"

DATA = ["samples", "replay", "cohort.json", "sources.json", "norms.csv", "cutoffs.csv"]


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "web", OUT)
    for name in DATA:
        src = ROOT / "data" / name
        dst = OUT / "data" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        elif src.exists():
            shutil.copy2(src, dst)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    files = sum(1 for p in OUT.rglob("*") if p.is_file())
    print(f"{OUT} ({files} files)")


if __name__ == "__main__":
    main()
