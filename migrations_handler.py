import subprocess
import sys


def handler(event, context):
    result = subprocess.run(
        ["python3", "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"Migration failed:\n{result.stderr}")
    return {"status": "ok", "output": result.stdout}