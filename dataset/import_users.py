"""users コンテナーへユーザデータ(JSON)を投入するスクリプト。

対象入力: dataset/users/*.json  (各ファイルはユーザ配列)
  要素例:
    {
        "userName": "斎藤 太郎",
        "companyName": "ABC商事株式会社",
        "departmentName": "人事部",
        "jobTitle": "主任"
    }

仕様:
  - JSON 上に id フィールドは不要 (Cosmos へ投入時に自動的に UUID を付与)
  - コンテナー未作成の場合は /companyName をパーティションキーとして作成
  - 既存レコードとの差分チェックは行わず常に upsert (重複を避けたい場合は HASH_ID_MODE を利用)

環境変数:
  COSMOS_ENDPOINT (必須)
  COSMOS_KEY      (必須)
  COSMOS_DB (既定: course-surveys)
  COSMOS_USERS_CONTAINER (既定: users)
  USERS_HASH_ID_MODE = 1 の場合: id を companyName + userName のハッシュで生成 (再実行で同一 id)
                            未設定/0 の場合: 毎回 uuid4

使用例:
    python dataset/import_users.py

"""
from __future__ import annotations
import os
import sys
import json
import hashlib
import uuid
from pathlib import Path
from typing import Iterable, List, Dict, Any
from azure.cosmos import CosmosClient, exceptions, PartitionKey  # type: ignore
from dotenv import load_dotenv  # type: ignore

ROOT_DIR = Path(__file__).resolve().parents[1]
USERS_DIR = Path("dataset") / "users"

DB_ENV = "COSMOS_DB"
CONTAINER_ENV = "COSMOS_USERS_CONTAINER"
ENDPOINT_ENV = "COSMOS_ENDPOINT"
KEY_ENV = "COSMOS_KEY"
DEFAULT_DB = "course-surveys"
DEFAULT_CONTAINER = "users"


def _load_dotenvs():
    root_env = ROOT_DIR / ".env"
    dataset_env = Path(__file__).parent / ".env"  # 通常なし
    if root_env.exists():
        load_dotenv(root_env, override=False)
    if dataset_env.exists():
        load_dotenv(dataset_env, override=True)


def fail(msg: str):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_env() -> dict[str, str]:
    _load_dotenvs()
    endpoint = os.getenv(ENDPOINT_ENV)
    key = os.getenv(KEY_ENV)
    if not endpoint or not key:
        fail(f"環境変数 {ENDPOINT_ENV}, {KEY_ENV} を設定してください")
    db = os.getenv(DB_ENV, DEFAULT_DB)
    container = os.getenv(CONTAINER_ENV, DEFAULT_CONTAINER)
    return {"endpoint": endpoint, "key": key, "db": db, "container": container}


def iter_user_arrays() -> Iterable[List[Dict[str, Any]]]:
    if not USERS_DIR.exists():
        fail(f"ユーザディレクトリが見つかりません: {USERS_DIR}")
    for fp in sorted(USERS_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(data, list):
                yield data
            else:
                print(f"WARN: {fp} は配列ではないためスキップ")
        except json.JSONDecodeError as e:
            print(f"WARN: {fp} 読み込み失敗: {e}")


def ensure_container(client: CosmosClient, db_name: str, container_name: str):
    try:
        db = client.create_database_if_not_exists(id=db_name)
        container = db.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path="/companyName"),
            offer_throughput=400,
        )
        return container
    except exceptions.CosmosHttpResponseError as e:
        fail(f"コンテナー作成/取得に失敗: {e}")


def make_id(user: Dict[str, Any], deterministic: bool) -> str:
    if deterministic:
        base = f"{user.get('companyName','')}-{user.get('userName','')}".encode("utf-8")
        return hashlib.sha256(base).hexdigest()[:32]
    return str(uuid.uuid4())


def main():
    cfg = load_env()
    deterministic = os.getenv("USERS_HASH_ID_MODE", "0") == "1"
    client = CosmosClient(cfg["endpoint"], credential=cfg["key"])
    container = ensure_container(client, cfg["db"], cfg["container"])

    total_files = 0
    total_users = 0
    for arr in iter_user_arrays():
        total_files += 1
        for user in arr:
            # 入力に id があるなら尊重、無ければ生成
            if "id" not in user:
                user["id"] = make_id(user, deterministic)
            # upsert
            container.upsert_item(user)
            total_users += 1
    print(f"Imported {total_users} users from {total_files} files into {cfg['db']}/{cfg['container']}")


if __name__ == "__main__":
    main()
