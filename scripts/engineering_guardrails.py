from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_NAV = [
    ("找机会", None),
    ("产品调研", "/market-opportunity"),
    ("竞品分析", "/competitor-analysis"),
    ("做上架", None),
    ("上架准入", "/prelaunch-check"),
    ("承接转化", "/conversion-diagnosis"),
    ("跑验证", None),
    ("今日决策", "/today-decisions"),
    ("执行测试", "/traffic-strategy"),
    ("执行记录", "/execution-records"),
    ("经营验证", "/business-validation"),
    ("昨日战报", "/yesterday-report"),
    ("账号中心", "/account"),
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def fail(message: str) -> None:
    print(f"[guardrail] FAIL: {message}")
    sys.exit(1)


def check_sidebar() -> None:
    text = read("frontend/src/components/Sidebar.tsx")
    found = re.findall(r'label: "([^"]+)"(?:,\s*icon: [^}\n]+)?|to: "([^"]+)", label: "([^"]+)"', text)
    labels_and_routes: list[tuple[str, str | None]] = []
    for group_label, route, item_label in found:
        if group_label:
            labels_and_routes.append((group_label, None))
        elif route and item_label:
            labels_and_routes.append((item_label, route))

    compact = []
    seen = set()
    for item in labels_and_routes:
        if item not in seen:
            compact.append(item)
            seen.add(item)

    if compact != EXPECTED_NAV:
        fail(f"sidebar navigation changed: {compact}")


def check_no_direct_report_upload_to_execution_records() -> None:
    for path in ["frontend/src/pages/ExecutionRecords.tsx", "frontend/src/pages/YesterdayReport.tsx"]:
        text = read(path)
        if "/execution-records" in text:
            fail(f"{path} posts uploaded report rows outside staging")


def check_no_default_user_fallback() -> None:
    for path in (ROOT / "backend/app/services").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "user_id or DEFAULT_USER_ID" in text:
            fail(f"{path.relative_to(ROOT)} still falls back to DEFAULT_USER_ID")


def check_report_upload_row_source_id() -> None:
    text = read("backend/app/services/report_uploads.py")
    if "source_record_id=batch.id" in text:
        fail("report upload staging source_record_id must be row-level, not batch-level")


def main() -> None:
    check_sidebar()
    check_no_direct_report_upload_to_execution_records()
    check_no_default_user_fallback()
    check_report_upload_row_source_id()
    print("[guardrail] OK")


if __name__ == "__main__":
    main()
