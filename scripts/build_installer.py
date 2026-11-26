"""Build the standalone installer from readable source files."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def build():
    source = (SRC / "installer.py").read_text(encoding="utf-8")
    translations = {lang: json.loads((SRC / "translations" / f"{lang}.json").read_text(encoding="utf-8"))
                    for lang in ("en", "pl")}
    assets = {
        "PAYLOAD": json.dumps((SRC / "wiked.py").read_text(encoding="utf-8"), ensure_ascii=False),
        "INPUT_PAYLOAD": json.dumps((SRC / "wiked_inputs.py").read_text(encoding="utf-8"), ensure_ascii=False),
        "TRANSLATIONS": "json.loads(" + json.dumps(json.dumps(translations, ensure_ascii=False, separators=(",", ":")), ensure_ascii=False) + ")",
    }
    lines = []
    for line in source.splitlines():
        key = line.partition(" = ")[0]
        lines.append(f"{key} = {assets[key]}" if key in assets else line)
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = ROOT / "blebox_wiked_install_0.1.5.py"
    generated = build()
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != generated:
            raise SystemExit("Generated installer is out of date")
    else:
        output.write_text(generated, encoding="utf-8")
