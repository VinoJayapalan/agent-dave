import re

from config import TARGET_REPO_PATH
from model_adapter import get_tester_adapter
from tools.file_tools import read_file, write_file
from tools.git_tools import commit_changes, create_branch, push_branch
from tools.github_tools import create_pull_request
from tools.repo_tools import list_repo_files
from tools.validator_tools import run_tests


def _slugify(text: str, max_length: int = 50) -> str:
    """Convert a feature string into a safe git branch name."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")[:max_length]
    return f"tester/{slug}"


def run_tester(feature: str) -> str:
    files = list_repo_files(TARGET_REPO_PATH, limit=300)

    # Separate source files and existing test files for context
    source_files = [
        f for f in files
        if f.startswith("src/") and f.endswith((".js", ".jsx", ".ts", ".tsx"))
        and ".test." not in f and ".spec." not in f
    ]
    test_files = [
        f for f in files
        if ".test." in f or ".spec." in f
    ]

    # Collect previews of source files (first 8) for planning context
    preview_targets = source_files[:8]
    file_previews: dict[str, str] = {}
    for file in preview_targets:
        full_path = f"{TARGET_REPO_PATH}/{file}"
        file_previews[file] = read_file(full_path)[:1200]

    adapter = get_tester_adapter()
    plan = adapter.plan_tests(feature, source_files + test_files, file_previews)

    relevant_source = "\n".join(plan.target_source_files) if plan.target_source_files else "(none)"

    # Read full content of targeted source files and the existing test file (if any)
    full_file_contents: dict[str, str] = {}
    for file in plan.target_source_files:
        full_path = f"{TARGET_REPO_PATH}/{file}"
        try:
            full_file_contents[file] = read_file(full_path)
        except (FileNotFoundError, OSError):
            pass

    if plan.test_file_path in files:
        full_path = f"{TARGET_REPO_PATH}/{plan.test_file_path}"
        try:
            full_file_contents[plan.test_file_path] = read_file(full_path)
        except (FileNotFoundError, OSError):
            pass

    # Generate test files
    edits = adapter.generate_test_files(feature, plan, full_file_contents)

    written_files: list[str] = []
    for edit in edits.edits:
        full_path = f"{TARGET_REPO_PATH}/{edit.path}"
        write_file(full_path, edit.new_content)
        written_files.append(edit.path)

    output = (
        f"Feature: {feature}\n\n"
        f"Plan summary: {plan.summary}\n\n"
        f"Source files targeted:\n{relevant_source}\n\n"
        f"Test cases:\n{plan.test_cases}"
    )

    if written_files:
        output += "\n\nTest files written:\n" + "\n".join(f"  {f}" for f in written_files)

        # Run tests
        print("Running tests...")
        test_result = run_tests(TARGET_REPO_PATH)

        status = "✅ PASSED" if test_result.success else "❌ FAILED"
        output += f"\n\nTests: {status}"
        if test_result.passed or test_result.failed:
            output += f"  ({test_result.passed} passed, {test_result.failed} failed)"

        if test_result.success:
            # Branch → commit → push → PR
            branch_name = _slugify(feature)
            commit_msg = f"test: {feature[:72]}"
            pr_body = (
                f"## Summary\n{plan.summary}\n\n"
                f"## Test cases\n{plan.test_cases}\n\n"
                f"## Files\n" +
                "\n".join(f"- `{f}`" for f in written_files) +
                f"\n\n## Results\n✅ {test_result.passed} passed, {test_result.failed} failed"
                "\n\n_Opened by agent-tester_"
            )

            print(f"Creating branch: {branch_name}")
            branch_result = create_branch(TARGET_REPO_PATH, branch_name)
            if not branch_result.success:
                output += f"\n\nGit branch failed: {branch_result.error}"
                return output

            print("Committing test files...")
            commit_result = commit_changes(TARGET_REPO_PATH, written_files, commit_msg)
            if not commit_result.success:
                output += f"\n\nGit commit failed: {commit_result.error}"
                return output

            print(f"Pushing branch: {branch_name}")
            push_result = push_branch(TARGET_REPO_PATH, branch_name)
            if not push_result.success:
                output += f"\n\nGit push failed: {push_result.error}"
                return output

            print("Opening pull request...")
            pr = create_pull_request(
                title=f"test: {feature[:72]}",
                body=pr_body,
                branch=branch_name,
            )
            output += f"\n\nPull request opened: {pr.url}"

        else:
            output += "\n\nTests failed — no PR created."
            if test_result.error:
                output += f"\n\nTest errors:\n{test_result.error}"
            if test_result.output:
                output += f"\n\nTest output:\n{test_result.output}"
    else:
        output += "\n\nNo test files were generated."

    return output
