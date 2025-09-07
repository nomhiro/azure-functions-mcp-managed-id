"""Cosmos DB の courses コンテナー内の全アイテムを個別 JSON ファイルにエクスポートするスクリプト。

出力先: dataset/courses/<id>.json

実行例 (PowerShell):
    $env:COSMOS_ENDPOINT="https://<acct>.documents.azure.com:443/"
    $env:COSMOS_KEY="<key>"
    python dataset/export_courses.py

オプション環境変数:
    COSMOS_DB (既定: course-surveys)
    COSMOS_COURSES_CONTAINER (既定: courses)
"""
from __future__ import annotations
import os
import json
import sys
from pathlib import Path
from typing import Any
from azure.cosmos import CosmosClient, exceptions  # type: ignore
from dotenv import load_dotenv  # type: ignore

DB_ENV = "COSMOS_DB"
CONTAINER_ENV = "COSMOS_COURSES_CONTAINER"
ENDPOINT_ENV = "COSMOS_ENDPOINT"
KEY_ENV = "COSMOS_KEY"
DEFAULT_DB = "course-surveys"            # 既定のデータベース名
DEFAULT_CONTAINER = "courses"            # 既定のコンテナー名

OUTPUT_DIR = Path("dataset") / "courses"


def _load_dotenvs():
    """dataset/.env と ルート .env を読み込む。

    読み込み順: ルート -> dataset  (dataset/.env を優先したいので最後に読み込む)
    既に設定されている環境変数は dataset/.env で override=True により上書き可能。
    """
    root_env = Path(__file__).resolve().parents[1] / ".env"
    dataset_env = Path(__file__).parent / ".env"
    if root_env.exists():
        load_dotenv(root_env, override=False)
    if dataset_env.exists():
        load_dotenv(dataset_env, override=True)


def _fail(msg: str):
    """致命的エラーを表示して終了"""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_env() -> dict[str, str]:
    """環境変数から設定値を読み込む。

    必須: COSMOS_ENDPOINT, COSMOS_KEY
    任意: COSMOS_DB, COSMOS_COURSES_CONTAINER
    """
    # まず .env ファイル群を読み込む (存在しない場合は無視)
    _load_dotenvs()
    endpoint = os.getenv(ENDPOINT_ENV)
    key = os.getenv(KEY_ENV)
    if not endpoint or not key:
        _fail(f"環境変数 {ENDPOINT_ENV}, {KEY_ENV} を設定してください")
    db = os.getenv(DB_ENV, DEFAULT_DB)
    container = os.getenv(CONTAINER_ENV, DEFAULT_CONTAINER)
    return {"endpoint": endpoint, "key": key, "db": db, "container": container}


def ensure_output_dir():
    """出力先ディレクトリを作成 (既に存在する場合は何もしない)"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_container(cfg) -> Any:
    """Cosmos のコンテナクライアントを取得"""
    try:
        client = CosmosClient(cfg["endpoint"], credential=cfg["key"])
        db_client = client.get_database_client(cfg["db"])
        return db_client.get_container_client(cfg["container"])
    except exceptions.CosmosHttpResponseError as e:
        _fail(f"Cosmos へのアクセスに失敗しました: {e}")


def export_items(container):
    """コンテナ内すべてのアイテムをファイルへ書き出し件数を返す"""
    count = 0
    for item in container.read_all_items(max_item_count=1000):  # 上限は適宜調整
        item_id = item.get("id")
        if not item_id:
            continue  # id が無いものはスキップ
        path = OUTPUT_DIR / f"{item_id}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)
        count += 1
    return count


def main():
    """エクスポートのエントリポイント"""
    cfg = load_env()
    ensure_output_dir()
    container = get_container(cfg)
    total = export_items(container)
    print(f"{total} 件を {OUTPUT_DIR} にエクスポートしました")


if __name__ == "__main__":
    main()
