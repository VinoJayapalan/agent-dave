import subprocess
from dataclasses import dataclass


@dataclass
class BuildResult:
    success: bool
    output: str    # stdout from the build
    error: str     # stderr from the build


def run_build(repo_path: str) -> BuildResult:
    """Run `npm run build` inside repo_path and return the result."""
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return BuildResult(
            success=result.returncode == 0,
            output=result.stdout.strip(),
            error=result.stderr.strip(),
        )
    except subprocess.TimeoutExpired:
        return BuildResult(
            success=False,
            output="",
            error="Build timed out after 120 seconds.",
        )
    except FileNotFoundError:
        return BuildResult(
            success=False,
            output="",
            error="npm not found. Ensure Node.js and npm are installed and on PATH.",
        )
