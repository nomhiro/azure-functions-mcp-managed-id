"""surveys.json を Cosmos DB の surveys コンテナーへ投入するスクリプト。

前提: dataset/generate_surveys.py により dataset/surveys.json が生成済み

コンテナー:
  - 名前は環境変数 COSMOS_SURVEYS_CONTAINER (既定 surveys)
  - パーティションキー: /courseId  (講座別集計想定)

フィールド (id はここで自動生成 uuid4):
  courseId, userId, satisfactionRating, satisfactionComment,
  difficultyRating, difficultyComment, improvementRequest
"""
from __future__ import annotations
import os
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any
from azure.cosmos import CosmosClient, exceptions, PartitionKey  # type: ignore
from dotenv import load_dotenv  # type: ignore

INPUT_FILE = Path("dataset") / "surveys.json"

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
        raise SystemExit("環境変数 COSMOS_ENDPOINT, COSMOS_KEY を設定してください")
    return {
        "endpoint": endpoint,
        "key": key,
        "db": os.getenv("COSMOS_DB", "course-surveys"),
        "container": os.getenv("COSMOS_SURVEYS_CONTAINER", "surveys"),
    }


def ensure_container(client: CosmosClient, db_name: str, container_name: str):
    db = client.create_database_if_not_exists(id=db_name)
    return db.create_container_if_not_exists(
        id=container_name,
        partition_key=PartitionKey(path="/courseId"),
        offer_throughput=400,
    )


def main():
    if not INPUT_FILE.exists():
        raise SystemExit(f"{INPUT_FILE} が存在しません。先に generate_surveys.py を実行してください。")
    cfg = load_env()
    client = CosmosClient(cfg["endpoint"], credential=cfg["key"])
    container = ensure_container(client, cfg["db"], cfg["container"])
    data: List[Dict[str, Any]] = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    count = 0
    for doc in data:
        if "id" not in doc:
            doc["id"] = str(uuid.uuid4())
        container.upsert_item(doc)
        count += 1
    print(f"Imported {count} survey documents into {cfg['db']}/{cfg['container']}")


if __name__ == "__main__":
    main()
