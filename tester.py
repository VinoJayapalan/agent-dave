import argparse
from tester_orchestrator import run_tester


def main() -> None:
    parser = argparse.ArgumentParser(description="agent-tester: generate and run tests via Claude")
    parser.add_argument("feature", help="Component or feature to write tests for")
    args = parser.parse_args()

    result = run_tester(args.feature)
    print(result)


if __name__ == "__main__":
    main()
