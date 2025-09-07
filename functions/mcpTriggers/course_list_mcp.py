"""courses コンテナーの全件 (上限1000) を返す MCP ツール。

引数なしで呼び出し可能。サイズ肥大化防止のため 1000 件を超える場合は打ち切り、
"truncated": true を付加する。
"""
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
    container_name = os.getenv("COSMOS_COURSES_CONTAINER", "courses")
    if not endpoint or not key:
        logging.warning("[list_all_courses] COSMOS_ENDPOINT / COSMOS_KEY 未設定")
        return
    try:
        _client = CosmosClient(endpoint, credential=key)
        db = _client.get_database_client(db_name)
        _container = db.get_container_client(container_name)
    except exceptions.CosmosHttpResponseError as e:
        logging.error(f"Cosmos 初期化失敗: {e}")
    except Exception as e:  # pragma: no cover
        logging.error(f"Cosmos 初期化予期せぬ失敗: {e}")


def list_all_courses_mcp(context):  # context は未使用（将来拡張用）
    try:
        # 引数があっても無視。将来的にフィルタ追加する際は parse_args を使う。
        parse_args(context)  # 解析だけ実行（副作用なし）
        _init_cosmos()
        if _container is None:
            return build_error("Cosmos コンテナー未初期化", kind="DependencyNotReady")

        query = "SELECT * FROM c"
        items: List[Dict[str, Any]] = []
        truncated = False
        try:
            for doc in _container.query_items(query=query, enable_cross_partition_query=True):
                items.append(doc)
                if len(items) >= 1000:  # 上限
                    truncated = True
                    break
        except exceptions.CosmosHttpResponseError as e:
            logging.warning(f"[list_all_courses] Cosmos クエリ失敗: {e}")
            return build_error("Cosmos クエリ失敗", details=str(e), kind="CosmosQueryError", extra={"query": query})

        return {
            "query": query,
            "count": len(items),
            "truncated": truncated,
            "results": items,
        }
    except Exception as e:  # pragma: no cover
        return log_and_build_unhandled(e, tool="list_all_courses")

__all__ = ["list_all_courses_mcp"]
