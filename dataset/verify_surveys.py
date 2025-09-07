"""surveys.json 内の courseId / userId が Cosmos DB 上の courses / users コンテナー
に存在するか整合性検証するスクリプト。

出力例:
  Courses in surveys: 10 (missing: 0)
  Users in surveys: 300 (missing: 0)
  All survey references are consistent.

環境変数 (.env 経由可):
  COSMOS_ENDPOINT, COSMOS_KEY (必須)
  COSMOS_DB (既定 course-surveys)
  COSMOS_COURSES_CONTAINER (既定 courses)
  COSMOS_USERS_CONTAINER (既定 users)

Exit Code: 不整合があれば 1
"""
from __future__ import annotations
import os
import json
import sys
from pathlib import Path
from typing import Set
from azure.cosmos import CosmosClient  # type: ignore
from dotenv import load_dotenv  # type: ignore

SURVEYS_FILE = Path("dataset") / "surveys.json"


def load_env():
    root_env = Path(__file__).resolve().parents[1] / ".env"
    if root_env.exists():
        load_dotenv(root_env, override=False)
    dataset_env = Path(__file__).parent / ".env"
    if dataset_env.exists():
        load_dotenv(dataset_env, override=True)
    endpoint = os.getenv("COSMOS_ENDPOINT")
    key = os.getenv("COSMOS_KEY")
    if not endpoint or not key:
        print("ERROR: 環境変数 COSMOS_ENDPOINT, COSMOS_KEY を設定してください", file=sys.stderr)
        sys.exit(1)
    return {
        "endpoint": endpoint,
        "key": key,
        "db": os.getenv("COSMOS_DB", "course-surveys"),
        "courses": os.getenv("COSMOS_COURSES_CONTAINER", "courses"),
        "users": os.getenv("COSMOS_USERS_CONTAINER", "users"),
    }


def fetch_ids(container) -> Set[str]:
    return {doc["id"] for doc in container.read_all_items(max_item_count=2000) if "id" in doc}


def main():
    if not SURVEYS_FILE.exists():
        print(f"ERROR: {SURVEYS_FILE} が存在しません", file=sys.stderr)
        sys.exit(1)
    cfg = load_env()
    surveys = json.loads(SURVEYS_FILE.read_text(encoding="utf-8"))
    survey_course_ids = {s.get("courseId") for s in surveys if s.get("courseId")}
    survey_user_ids = {s.get("userId") for s in surveys if s.get("userId")}

    client = CosmosClient(cfg["endpoint"], credential=cfg["key"])
    db = client.get_database_client(cfg["db"])
    course_ids = fetch_ids(db.get_container_client(cfg["courses"]))
    user_ids = fetch_ids(db.get_container_client(cfg["users"]))

    missing_courses = sorted(survey_course_ids - course_ids)
    missing_users = sorted(survey_user_ids - user_ids)

    print(f"Courses in surveys: {len(survey_course_ids)} (missing: {len(missing_courses)})")
    if missing_courses:
        print("  Missing courseIds (first 20):", missing_courses[:20])
    print(f"Users in surveys: {len(survey_user_ids)} (missing: {len(missing_users)})")
    if missing_users:
        print("  Missing userIds (first 20):", missing_users[:20])

    if not missing_courses and not missing_users:
        print("All survey references are consistent.")
    else:
        print("Inconsistencies detected.")
        sys.exit(1)


if __name__ == "__main__":
    main()
