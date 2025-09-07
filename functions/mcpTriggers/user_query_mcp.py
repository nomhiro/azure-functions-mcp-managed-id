"""ユーザ情報取得用 MCP ツール群。

1. get_users_by_ids_mcp: userIds(配列/カンマ区切り文字列) からユーザドキュメントをまとめて取得。
2. get_users_by_company_mcp: companyName で同一企業のユーザ一覧を取得。

設計メモ:
- users コンテナー (環境変数: COSMOS_USERS_CONTAINER / 既定 'users') を参照。
- パーティションキーは companyName を想定。company 単位検索は単一パーティションなので高速。
- 複数 ID 取得は全パーティション跨ぎ → cross partition query 有効化。
- ヒント: ARRAY_CONTAINS(@ids, c.id) パターンで ID リストを一度に検索。
"""
from __future__ import annotations
from typing import Any, Dict, List
import os
import logging
from azure.cosmos import CosmosClient, exceptions  # type: ignore
from ._common import parse_args, build_error, log_and_build_unhandled

_client = None
_container = None


def _init_cosmos():
    global _client, _container
    if _client is not None:
        return
    endpoint = os.getenv("COSMOS_ENDPOINT")
    key = os.getenv("COSMOS_KEY")
    db_name = os.getenv("COSMOS_DB", "course-surveys")
    container_name = os.getenv("COSMOS_USERS_CONTAINER", "users")
    if not endpoint or not key:
        logging.warning("[user_query] COSMOS_ENDPOINT / COSMOS_KEY 未設定")
        return
    try:
        _client = CosmosClient(endpoint, credential=key)
        db = _client.get_database_client(db_name)
        _container = db.get_container_client(container_name)
    except exceptions.CosmosHttpResponseError as e:
        logging.error(f"Cosmos 初期化失敗: {e}")
    except Exception as e:  # pragma: no cover
        logging.error(f"Cosmos 初期化予期せぬ失敗: {e}")


def _normalize_ids(raw) -> List[str]:
    """userIds のカンマ区切り文字列を配列に変換する。

    後方互換の list 入力サポートは削除済み。list / dict / その他型が来た場合は空リスト。
    例: "id1,id2 , id3" -> ["id1","id2","id3"]
    空や非文字列は []
    """
    if not isinstance(raw, str):
        return []
    raw = raw.strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return [p for p in parts if p]


def get_users_by_ids_mcp(context):
    try:
        args = parse_args(context)
        ids = _normalize_ids(args.get("userIds"))
        if not ids:
            # エラーではなく利用方法ガイド
            return {
                "query": None,
                "count": 0,
                "results": [],
                "info": "userIds にカンマ区切り文字列を指定してください (例: id1,id2,id3)",
                "usageExample": {"userIds": "id1,id2,id3"},
            }

        _init_cosmos()
        if _container is None:
            return build_error("Cosmos コンテナー未初期化", kind="DependencyNotReady")

        # ARRAY_CONTAINS(@ids, c.id) で一括取得
        query = "SELECT * FROM c WHERE ARRAY_CONTAINS(@ids, c.id)"
        params = [{"name": "@ids", "value": ids}]
        items: List[Dict[str, Any]] = []
        try:
            for doc in _container.query_items(query=query, parameters=params, enable_cross_partition_query=True):
                items.append(doc)
                if len(items) >= len(ids):  # 早期打ち切り（全ID 想定件数超過で停止）
                    break
        except exceptions.CosmosHttpResponseError as e:
            logging.warning(f"[get_users_by_ids] Cosmos クエリ失敗 ids={ids[:5]}..: {e}")
            return build_error("Cosmos クエリ失敗", details=str(e), kind="CosmosQueryError", extra={"query": query, "ids": ids[:10]})

        # 見つからなかった ID (差集合)
        found_ids = {d.get("id") for d in items}
        missing = [i for i in ids if i not in found_ids]
        return {
            "query": query,
            "requested": len(ids),
            "count": len(items),
            "missingIds": missing,
            "results": items,
        }
    except Exception as e:  # pragma: no cover
        return log_and_build_unhandled(e, tool="get_users_by_ids")


def get_users_by_company_mcp(context):
    try:
        args = parse_args(context)
        company = (args.get("companyName") or "").strip()
        top_k = int(args.get("topK") or 200)
        if not company:
            return {
                "query": None,
                "count": 0,
                "results": [],
                "info": "companyName を指定してください",
                "usageExample": {"companyName": "ABC商事株式会社"},
            }

        _init_cosmos()
        if _container is None:
            return build_error("Cosmos コンテナー未初期化", kind="DependencyNotReady")

        # パーティションキーが companyName である前提で単一パーティションクエリ: ORDER BY userName
        query = "SELECT * FROM c WHERE c.companyName = @company ORDER BY c.userName"
        params = [{"name": "@company", "value": company}]
        items: List[Dict[str, Any]] = []
        truncated = False
        try:
            # 単一パーティションなので enable_cross_partition_query 不要だが True でも可
            for doc in _container.query_items(query=query, parameters=params, partition_key=company):
                items.append(doc)
                if len(items) >= top_k:
                    truncated = True
                    break
        except exceptions.CosmosHttpResponseError as e:
            logging.warning(f"[get_users_by_company] Cosmos クエリ失敗 company={company}: {e}")
            return build_error("Cosmos クエリ失敗", details=str(e), kind="CosmosQueryError", extra={"query": query, "company": company})

        return {
            "query": query,
            "companyName": company,
            "count": len(items),
            "truncated": truncated,
            "results": items,
        }
    except Exception as e:  # pragma: no cover
        return log_and_build_unhandled(e, tool="get_users_by_company")


__all__ = [
    "get_users_by_ids_mcp",
    "get_users_by_company_mcp",
]
