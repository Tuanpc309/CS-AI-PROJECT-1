"""Build a self-contained GitHub Pages game, including the Python WASM engine."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import sys
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "Source"
LOCK = Path(__file__).with_name("pyodide-lock.json")


def runtime_files(cache: Path) -> list[Path]:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    cache.mkdir(parents=True, exist_ok=True)

    def fetch(item):
        name, expected = item
        target = cache / name
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            with urlopen(lock["baseUrl"] + name, timeout=90) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f"Pyodide checksum mismatch: {name}")
            target.write_bytes(data)
        return target

    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(fetch, lock["files"].items()))


def build(output: Path, cache: Path) -> Path:
    # Build only into an empty output directory; never remove user files.
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    runtime = output / "runtime" / "pyodide"
    runtime.mkdir(parents=True)
    for path in runtime_files(cache):
        shutil.copy2(path, runtime / path.name)

    web = SOURCE / "web"
    for path in sorted(web.iterdir()):
        if path.suffix in {".js", ".css", ".svg"}:
            shutil.copy2(path, output / path.name)
    shutil.copytree(web / "vendor", output / "vendor")
    html = (web / "index.html").read_text(encoding="utf-8")
    html = html.replace("<head>", '<head>\n  <meta name="bloxorz-runtime" content="browser">', 1)
    (output / "index.html").write_text(html, encoding="utf-8")
    (output / ".nojekyll").touch()

    sys.path.insert(0, str(SOURCE))
    from webapp import Catalog
    catalog = Catalog()
    optima = {item["id"]: catalog.optimum(item["id"]) for item in catalog.items}
    solutions = json.loads((web / "levels" / "solutions.json").read_text(encoding="utf-8"))
    for key, solution in solutions.items():
        if optima[key] != solution["optimal"]:
            raise ValueError(f"Campaign optimum mismatch: {key}")

    files = [SOURCE / name for name in (
        "models.py", "geometry.py", "advanced.py", "engine.py", "loader.py",
        "controller.py", "worker.py", "webapp.py", "browser_api.py")]
    files += sorted((SOURCE / "solvers").glob("*.py"))
    files += sorted((SOURCE / "levels").glob("*.json"))
    files += [web / "levels" / "campaign.json", web / "levels" / "quiet_01.json"]
    files += sorted((web / "levels").glob("campaign_*.json"))

    with zipfile.ZipFile(output / "engine.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            entry = zipfile.ZipInfo(path.relative_to(ROOT).as_posix())
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
        entry = zipfile.ZipInfo("Source/web_optima.json")
        entry.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(entry, json.dumps(optima, sort_keys=True))

    # Preserve both the WASM runtime and CPython license notices.
    shutil.copy2(LOCK.with_name("PYODIDE-LICENSE.txt"), runtime / "LICENSE.txt")
    shutil.copy2(LOCK.with_name("CPYTHON-LICENSE.txt"), runtime / "CPYTHON-LICENSE.txt")
    (output / "THIRD-PARTY.txt").write_text(
        "Three.js 0.186.1: vendor/LICENSE\n"
        "Pyodide 314.0.7: runtime/pyodide/LICENSE.txt\n"
        "CPython: runtime/pyodide/CPYTHON-LICENSE.txt\n",
        encoding="utf-8")
    print(f"Built {len(catalog.items)} levels in {output}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "pyodide")
    args = parser.parse_args()
    build(args.output, args.cache)
