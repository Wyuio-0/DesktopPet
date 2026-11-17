"""Check a built executable with legacy source leftovers and isolated app data."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    executable = args.executable.resolve(strict=True)
    # Only create sentinels where no real file exists, and remove only our own
    # files afterwards. The executable and all user documents remain intact.
    sentinels = [executable.parent / "web" / "server.py",
                 executable.parent / "_internal" / "web" / "server.py"]
    for sentinel in sentinels:
        if sentinel.exists():
            raise RuntimeError(f"Use a clean build directory; file exists: {sentinel}")
    created = []
    try:
        for sentinel in sentinels:
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text('def make_app():\n    raise RuntimeError("LEGACY_SERVICE_OVERRIDE_EXECUTED")\n', encoding="utf-8")
            created.append(sentinel)
        with tempfile.TemporaryDirectory(prefix="amiya-workspace-check-") as temporary:
            root = Path(temporary)
            report_path = root / "result.json"
            environment = dict(os.environ, APPDATA=str(root / "appdata"),
                               XDG_CONFIG_HOME=str(root / "config"),
                               AMIYA_LOG_FILE=str(root / "pet.log"))
            result = subprocess.run(
                [str(executable), "--check-knowledge-workspace", str(report_path)],
                cwd=root, env=environment, timeout=90, capture_output=True,
            )
            if not report_path.is_file():
                raise RuntimeError(f"Executable produced no report (exit {result.returncode})")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            print(json.dumps(report, ensure_ascii=False, indent=2))
            if result.returncode or not report.get("success"):
                raise RuntimeError("Packaged knowledge workspace check failed")
    finally:
        for sentinel in created:
            sentinel.unlink()


if __name__ == "__main__":
    main()
