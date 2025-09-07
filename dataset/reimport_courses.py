"""courses コンテナーへ既存ローカル JSON を再投入し、講座実施日時フィールドを追加するスクリプト。

目的:
  - dataset/courses/*.json を読み込み
  - 各アイテムに `conductedAt` (講座研修を実施した日時, ISO8601 UTC) を付与 / 上書き
  - Cosmos DB の courses コンテナーへ upsert

フィールド名 (英語):
  conductedAt : UTC 時刻 (例: 2025-09-07T12:34:56Z)

日時割り当てポリシー:
  デフォルト: 過去 PAST_DAYS 日以内のランダム日時
  環境変数で調整可能:
    COURSE_DATE_MODE = random-past | random-future | fixed
    COURSE_PAST_DAYS (既定 120)
    COURSE_FUTURE_DAYS (既定 30)
    COURSE_FIXED_DATETIME (mode=fixed のとき使用, 例 "2025-01-15T09:00:00Z")

Cosmos 関連環境変数 (.env 可):
  COSMOS_ENDPOINT (必須)
  COSMOS_KEY      (必須)
  COSMOS_DB (既定 course-surveys)
  COSMOS_COURSES_CONTAINER (既定 courses)

使用例:
  python dataset/reimport_courses.py

再実行すると conductedAt は毎回再計算 (random 系) / fixed モードなら同値。
既に conductedAt が存在する場合も上書きします (保持したい場合はスクリプト内で条件を変更してください)。
"""
from __future__ import annotations
import os
import sys
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any
from azure.cosmos import CosmosClient, exceptions, PartitionKey  # type: ignore
from dotenv import load_dotenv  # type: ignore

COURSES_DIR = Path("dataset") / "courses"


def load_env() -> Dict[str, str]:
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
        "container": os.getenv("COSMOS_COURSES_CONTAINER", "courses"),
    }


def build_datetime_generator():
    mode = os.getenv("COURSE_DATE_MODE", "random-past").lower()
    past_days = int(os.getenv("COURSE_PAST_DAYS", "120"))
    future_days = int(os.getenv("COURSE_FUTURE_DAYS", "30"))
    fixed_dt = os.getenv("COURSE_FIXED_DATETIME")

    def rand_past():
        delta = timedelta(seconds=random.randint(0, past_days * 24 * 3600))
        dt = datetime.now(timezone.utc) - delta
        return dt.replace(microsecond=0)

    def rand_future():
        delta = timedelta(seconds=random.randint(0, future_days * 24 * 3600))
        dt = datetime.now(timezone.utc) + delta
        return dt.replace(microsecond=0)

    if mode == "fixed":
        if not fixed_dt:
            print("ERROR: COURSE_DATE_MODE=fixed ですが COURSE_FIXED_DATETIME が未設定", file=sys.stderr)
            sys.exit(1)
        try:
            dt_parsed = datetime.fromisoformat(fixed_dt.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            print("ERROR: COURSE_FIXED_DATETIME の形式が不正です (ISO8601 例: 2025-01-15T09:00:00Z)", file=sys.stderr)
            sys.exit(1)
        def fixed():  # type: ignore
            return dt_parsed
        return fixed
    elif mode == "random-future":
        return rand_future
    else:  # default random-past
        return rand_past


def ensure_container(client: CosmosClient, db_name: str, container_name: str):
    # 既存想定だが存在しなければ作成 (パーティションキーは targetCompany を想定していないので id ベースでも可)
    # ここでは安全に c.id を唯一キーとみなして /id パーティションは不可 (id は自動 PK にはならない) ので
    # 既存設計流用: パーティションキー未指定 (既存コンテナを前提)。新規作成時は /targetCompany が良ければ修正。
    db = client.create_database_if_not_exists(id=db_name)
    try:
        container = db.get_container_client(container_name)
        # 軽い読みで存在確認
        _ = list(container.query_items(query="SELECT TOP 1 * FROM c", enable_cross_partition_query=True))
        return container
    except exceptions.CosmosResourceNotFoundError:
        # 作成 (targetCompany をパーティションキーに)
        return db.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path="/targetCompany"),
            offer_throughput=400,
        )


def reimport():
    cfg = load_env()
    gen_dt = build_datetime_generator()
    client = CosmosClient(cfg["endpoint"], credential=cfg["key"])
    container = ensure_container(client, cfg["db"], cfg["container"])
    if not COURSES_DIR.exists():
        print(f"ERROR: {COURSES_DIR} が存在しません", file=sys.stderr)
        sys.exit(1)

    total = 0
    updated = 0
    for fp in sorted(COURSES_DIR.glob("*.json")):
        try:
            data: Dict[str, Any] = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"WARN: {fp.name} 読み込み失敗: {e}")
            continue
        if "id" not in data:
            print(f"WARN: {fp.name} に id が無いためスキップ")
            continue
        conducted_at = gen_dt().isoformat().replace("+00:00", "Z")
        data["conductedAt"] = conducted_at
        container.upsert_item(data)
        total += 1
        updated += 1
    print(f"Reimported {updated} / {total} courses with conductedAt field into {cfg['db']}/{cfg['container']}")


def main():
    reimport()


if __name__ == "__main__":
    main()
