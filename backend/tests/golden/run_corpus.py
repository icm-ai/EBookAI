from __future__ import annotations

import argparse
import json
from pathlib import Path

from book.publication import ExternalEpubCheckRunner
from book.regression import GoldenCaseSpec, GoldenCorpusHarness, GoldenSuiteReport

from fixtures import build_fixture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=Path(__file__).parent / "cases")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--external-epubcheck", action="store_true")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    runner = ExternalEpubCheckRunner() if args.external_epubcheck else None
    harness = GoldenCorpusHarness(epubcheck_runner=runner)

    results = []
    for spec_path in sorted(args.cases.glob("*.json")):
        spec = GoldenCaseSpec.load(spec_path)
        case_dir = args.output / spec.id
        case_dir.mkdir(parents=True, exist_ok=True)
        source = build_fixture(spec.fixture_kind, case_dir / "source.pdf")
        results.append(harness.evaluate(source, spec, case_dir))

    report = GoldenSuiteReport(results)
    report_path = args.output / "golden-report.json"
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
