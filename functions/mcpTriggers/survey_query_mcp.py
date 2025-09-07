import os
import logging
from typing import Any, Dict, List

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
    container_name = os.getenv("COSMOS_SURVEYS_CONTAINER", "surveys")
    if not endpoint or not key:
        logging.warning("[query_surveys] COSMOS_ENDPOINT / COSMOS_KEY 未設定")
        return
    try:
        _client = CosmosClient(endpoint, credential=key)
        db = _client.get_database_client(db_name)
        _container = db.get_container_client(container_name)
    except exceptions.CosmosHttpResponseError as e:
        logging.error(f"Cosmos 初期化失敗: {e}")
    except Exception as e:  # pragma: no cover
        logging.error(f"Cosmos 初期化予期せぬ失敗: {e}")


def _build_query(by_course: bool) -> str:
    if by_course:
        return "SELECT * FROM c WHERE c.courseId = @id"
    return "SELECT * FROM c WHERE c.userId = @id"


def query_surveys_mcp(context):
    """courseId か userId のどちらか 1 つで surveys を検索する MCP ツール。

    仕様:
      - 両方指定 → ValidationError
      - どちらも未指定 → ヘルプ (エラーにしない)
      - raw 文字列のみ → ヘルプ (usageExamples 付き)
      - topK 省略時 20
    """
    args = parse_args(context)
    course_id = (args.get("courseId") or "").strip()
    user_id = (args.get("userId") or "").strip()
    top_k = int(args.get("topK") or 20)

    # raw だけ来た場合 (JSON でキー不明)
    if not course_id and not user_id and args.get("raw"):
        return {
            "mode": None,
            "id": None,
            "query": None,
            "count": 0,
            "results": [],
            "info": "courseId か userId を JSON で指定してください",
            "raw": args.get("raw"),
            "usageExamples": [
                {"courseId": "<course-id>"},
                {"userId": "<user-id>"}
            ]
        }

    if course_id and user_id:
        return build_error("courseId と userId は同時指定できません", kind="ValidationError")

    if not course_id and not user_id:
        return {
            "mode": None,
            "id": None,
            "query": None,
            "count": 0,
            "results": [],
            "info": "courseId か userId のいずれかを指定するとアンケートを取得します",
            "usageExamples": [
                {"courseId": "<course-id>"},
                {"userId": "<user-id>"}
            ]
        }

    by_course = bool(course_id)
    target_id = course_id or user_id

    _init_cosmos()
    if _container is None:
        return build_error("Cosmos コンテナー未初期化", kind="DependencyNotReady")

    query = _build_query(by_course)
    params = [{"name": "@id", "value": target_id}]
    items: List[Dict[str, Any]] = []
    try:
        for doc in _container.query_items(query=query, parameters=params, enable_cross_partition_query=True):
            items.append(doc)
            if len(items) >= top_k:
                break
    except exceptions.CosmosHttpResponseError as e:
        logging.warning(f"[query_surveys] Cosmos クエリ失敗 id={target_id}: {e}")
        return build_error("Cosmos クエリ失敗", details=str(e), kind="CosmosQueryError", extra={"query": query, "id": target_id})
    except Exception as e:  # pragma: no cover
        return log_and_build_unhandled(e, tool="query_surveys")

    return {
        "mode": "courseId" if by_course else "userId",
        "id": target_id,
        "query": query,
        "count": len(items),
        "results": items,
    }

__all__ = ["query_surveys_mcp"]
