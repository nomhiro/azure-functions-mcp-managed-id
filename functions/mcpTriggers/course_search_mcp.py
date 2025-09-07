import os
import logging
from typing import Any, Dict, List

from azure.cosmos import CosmosClient, exceptions  # type: ignore
from ._common import parse_args, build_error, log_and_build_unhandled

_client = None
_container = None


def _init_cosmos():
    """Lazy 初期化。"""
    global _client, _container
    if _client is not None:
        return
    endpoint = os.getenv("COSMOS_ENDPOINT")
    key = os.getenv("COSMOS_KEY")
    db_name = os.getenv("COSMOS_DB", "course-surveys")
    container_name = os.getenv("COSMOS_COURSES_CONTAINER", "courses")
    if not endpoint or not key:
        logging.warning("[course_search] COSMOS_ENDPOINT / COSMOS_KEY 未設定")
        return
    try:
        _client = CosmosClient(endpoint, credential=key)
        db = _client.get_database_client(db_name)
        _container = db.get_container_client(container_name)
    except exceptions.CosmosHttpResponseError as e:
        logging.error(f"Cosmos 初期化失敗: {e}")
    except Exception as e:  # pragma: no cover
        logging.error(f"Cosmos 初期化予期せぬ失敗: {e}")


def _tokenize(term: str) -> List[str]:
    # シンプルに空白分割 (全角スペース対応)
    if not term:
        return []
    return [t for t in term.replace("\u3000", " ").split(" ") if t]


def _build_query(field: str, tokens: List[str]) -> str:
    # LOWER(c.field) に対して CONTAINS を AND 連結
    if not tokens:
        return f"SELECT * FROM c WHERE IS_DEFINED(c.{field})"
    conds = [f"CONTAINS(LOWER(c.{field}), @t{i})" for i, _ in enumerate(tokens)]
    where = " AND ".join(conds)
    return f"SELECT * FROM c WHERE {where}"


def _search_field(field: str, context):
    args = parse_args(context)
    # JSON でないプレーン文字列入力の場合 parse_args が {"raw": "..."} を返すため救済
    term = (args.get("searchTerm") or args.get("raw") or "").strip()
    if not term:
        return build_error("searchTerm は必須です", kind="ValidationError", extra={"field": "searchTerm"})
    top_k = int(args.get("topK") or 5)
    # 旧: maxScan / minScore は廃止
    tokens = _tokenize(term.lower())
    _init_cosmos()
    if _container is None:
        return build_error("Cosmos コンテナー未初期化", kind="DependencyNotReady")

    query = _build_query(field, tokens)
    params = [ {"name": f"@t{i}", "value": tok} for i, tok in enumerate(tokens) ]
    items: List[Dict[str, Any]] = []
    try:
        for doc in _container.query_items(query=query, parameters=params, enable_cross_partition_query=True):
            items.append(doc)
            if len(items) >= top_k * 3:  # 多少余分に取得して後で slice
                break
    except exceptions.CosmosHttpResponseError as e:
        logging.warning(f"[course_search] Cosmos クエリ失敗 field={field} term='{term}': {e}")
        return build_error("Cosmos クエリ失敗", details=str(e), kind="CosmosQueryError", extra={"query": query})
    except Exception as e:  # pragma: no cover
        return log_and_build_unhandled(e, tool=f"search_{field}")

    # 簡易スコア: 各トークンが含まれる割合 + 長さ比
    results = []
    for d in items:
        val = d.get(field)
        if not isinstance(val, str):
            continue
        lv = val.lower()
        if not all(tok in lv for tok in tokens):
            continue  # 保険
        token_hits = sum(1 for tok in tokens if tok in lv)
        length_bonus = min(len(term) / max(len(val), 1), 1.0)
        score = round((token_hits / max(len(tokens),1)) * 0.7 + length_bonus * 0.3, 4)
        snippet = val[:120] + ("..." if len(val) > 120 else "")
        results.append({
            "id": d.get("id"),
            "score": score,
            "fieldValue": val,
            "snippet": snippet,
            "doc": d,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    trimmed = results[:top_k]
    return {
        "query": term,
        "field": field,
        "tokens": tokens,
        "cosmosQuery": query,
        "matched": len(trimmed),
        "topK": top_k,
        "results": trimmed,
    }


def search_courses_by_name_mcp(context):
    return _search_field("courseName", context)


def search_courses_by_description_mcp(context):
    return _search_field("description", context)


def search_courses_by_company_mcp(context):
    return _search_field("targetCompany", context)

__all__ = [
    "search_courses_by_name_mcp",
    "search_courses_by_description_mcp",
    "search_courses_by_company_mcp",
]
