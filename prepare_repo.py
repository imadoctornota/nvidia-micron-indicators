"""Copy the notebook and its outputs into this repo, scrubbed for publishing.

Usage (from inside this repo folder):
    python prepare_repo.py --src "<folder you ran the notebook in>"

What it does:
  1. Copies metrics_nvda_mu_v6.ipynb to nvidia_micron_indicators.ipynb, with the SEC
     user agent replaced by a placeholder and any home-folder paths removed.
  2. Copies the 200-dpi camera figures (outputs_metrics_v6/camera/*.png) into figures/.
  3. Copies the result tables (*.csv), results.json and recording_brief.txt into results/.
  4. Runs a privacy check over everything in the repo and refuses to finish if it
     finds an email address (other than example.com) or a home-folder path.

Prices and SEC downloads (cache_metrics/) are never copied: Yahoo's terms don't allow
redistributing the raw prices, and anyone can rebuild the cache by running the notebook.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NB_IN = "metrics_nvda_mu_v6.ipynb"
NB_OUT = "nvidia_micron_indicators.ipynb"
OUT_DIR = "outputs_metrics_v6"
PLACEHOLDER = 'SEC_USER_AGENT = ""   # SEC asks every script to identify itself: "Your Name you@example.com"'

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ALLOWED_EMAIL_DOMAINS = {"example.com"}
# Home paths, including the double-escaped Windows form that appears inside notebook JSON
HOME = re.compile(r"(/Users/[^/\s\"'\\]+|/home/[^/\s\"'\\]+|[A-Za-z]:(?:\\+|/)Users(?:\\+|/)[^\\/\s\"']+)")
TEXT_EXT = {".ipynb", ".py", ".md", ".txt", ".csv", ".json", ".gitignore", ""}


def scrub_text(s: str) -> str:
    s = HOME.sub("~", s)
    return s


def scrub_notebook(src: Path, dst: Path) -> None:
    nb = json.loads(src.read_text(encoding="utf-8"))
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            lines = cell["source"] if isinstance(cell["source"], list) else cell["source"].splitlines(True)
            new = []
            for line in lines:
                if line.lstrip().startswith("SEC_USER_AGENT ="):
                    line = PLACEHOLDER + ("\n" if line.endswith("\n") else "")
                new.append(scrub_text(line))
            cell["source"] = new
        else:
            src_ = cell["source"] if isinstance(cell["source"], list) else [cell["source"]]
            cell["source"] = [scrub_text(x) for x in src_]
        for out in cell.get("outputs", []):
            if "text" in out:
                t = out["text"] if isinstance(out["text"], list) else [out["text"]]
                out["text"] = [scrub_text(x) for x in t]
            data = out.get("data", {})
            for k in ("text/plain", "text/html"):
                if k in data:
                    v = data[k] if isinstance(data[k], list) else [data[k]]
                    data[k] = [scrub_text(x) for x in v]
    nb.get("metadata", {}).pop("widgets", None)
    text = json.dumps(nb, indent=1, ensure_ascii=False)
    # second pass on the serialized JSON catches paths split oddly across escapes
    dst.write_text(scrub_text(text) + "\n", encoding="utf-8")


def privacy_check(root: Path) -> list:
    problems = []
    for p in root.rglob("*"):
        if not p.is_file() or ".git" in p.parts or p.name == "prepare_repo.py":
            continue
        if p.suffix.lower() not in TEXT_EXT and p.name != ".gitignore":
            continue
        try:
            s = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in EMAIL.finditer(s):
            if m.group(0).split("@")[-1].lower() not in ALLOWED_EMAIL_DOMAINS:
                problems.append(f"{p.relative_to(root)}: email {m.group(0)}")
        for m in HOME.finditer(s):
            problems.append(f"{p.relative_to(root)}: home path {m.group(0)}")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="folder that holds the notebook and outputs_metrics_v6/")
    ap.add_argument("--nb", default=NB_IN, help=f"notebook file name inside --src (default {NB_IN})")
    ap.add_argument("--check-only", action="store_true", help="only run the privacy check on this repo")
    a = ap.parse_args()

    if not a.check_only:
        src = Path(a.src).expanduser().resolve()
        nb = src / a.nb
        out = src / OUT_DIR
        if not nb.exists():
            sys.exit(f"Can't find {nb}")
        scrub_notebook(nb, HERE / NB_OUT)
        print(f"notebook  -> {NB_OUT}")

        cam = out / "camera"
        if cam.exists():
            (HERE / "figures").mkdir(exist_ok=True)
            for old in (HERE / "figures").glob("*.png"):   # the notebook-preview copies the repo ships with
                old.unlink()
            n = 0
            for f in sorted(cam.glob("*.png")):
                shutil.copy2(f, HERE / "figures" / f.name)
                n += 1
            print(f"figures   -> figures/ ({n} PNGs)")
        else:
            print(f"no {cam}; keeping the figures already in figures/")

        if out.exists():
            (HERE / "results").mkdir(exist_ok=True)
            n = 0
            for f in sorted(list(out.glob("*.csv")) + list(out.glob("*.json")) + list(out.glob("*.txt"))):
                txt = f.read_text(encoding="utf-8", errors="ignore")
                (HERE / "results" / f.name).write_text(scrub_text(txt), encoding="utf-8")
                n += 1
            print(f"tables    -> results/ ({n} files)")
        else:
            print(f"no {out}; keeping the files already in results/")

    problems = privacy_check(HERE)
    if problems:
        print("privacy check: FOUND PROBLEMS, don't push yet")
        for x in problems:
            print("  ", x)
        sys.exit(1)
    print("privacy check: clean")


if __name__ == "__main__":
    main()
