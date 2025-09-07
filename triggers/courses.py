import os
import logging
from typing import List, Dict, Any, Callable
from difflib import SequenceMatcher

from azure.cosmos import CosmosClient, PartitionKey, exceptions  # type: ignore
from azure.functions import FunctionApp

# 共通: FunctionApp インスタンス取得

def _get_app() -> FunctionApp:
    from function_app import app  # type: ignore
    return app

# ---------------------------------------------------------------------------
# Cosmos DB クライアント (lazy singleton)
# ---------------------------------------------------------------------------
_client: CosmosClient | None = None
_database = None
_courses_container = None


def _init_client():
    global _client, _database, _courses_container
    if _client is not None:
        return
    endpoint = os.getenv("COSMOS_ENDPOINT")
    key = os.getenv("COSMOS_KEY")
    db_name = os.getenv("COSMOS_DB", "course-surveys")
    container_name = os.getenv("COSMOS_COURSES_CONTAINER", "courses")

    if not endpoint or not key:
        logging.warning("COSMOS_ENDPOINT か COSMOS_KEY が設定されていません")
        return
    try:
        _client = CosmosClient(endpoint, credential=key)
        _database = _client.get_database_client(db_name)
        _courses_container = _database.get_container_client(container_name)
    except exceptions.CosmosResourceNotFoundError:
        logging.error("指定された DB/Container が存在しません")
    except Exception as e:
        logging.error(f"Cosmos クライアント初期化失敗: {e}")


# ---------------------------------------------------------------------------
# 共通: ドキュメント取得 (最大 max_items)
# ---------------------------------------------------------------------------

def _fetch_courses(max_items: int) -> List[Dict[str, Any]]:
    _init_client()
    if _courses_container is None:
        return []
    items: List[Dict[str, Any]] = []
    try:
        # シンプルに全件スキャン (本番はクエリ/インデックス設計が望ましい)
        for doc in _courses_container.read_all_items(max_item_count=max_items):
            items.append(doc)
            if len(items) >= max_items:
                break
    except Exception as e:
        logging.error(f"courses コンテナー読み込み失敗: {e}")
    return items


# ---------------------------------------------------------------------------
# 共通: Fuzzy 検索ロジック
# ---------------------------------------------------------------------------

def _score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a in b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _fuzzy_search(field: str, term: str, top_k: int, max_scan: int, min_score: float) -> Dict[str, Any]:
    term_norm = term.strip().lower()
    docs = _fetch_courses(max_scan)
    scored: List[Dict[str, Any]] = []
    for d in docs:
        value = d.get(field)
        if not isinstance(value, str):
            continue
        v_norm = value.lower()
        s = _score(term_norm, v_norm)
        if s >= min_score:
            snippet = value[:120]
            if len(value) > 120:
                snippet += "..."
            scored.append({
                "id": d.get("id"),
                "score": round(s, 4),
                "snippet": snippet,
                "fieldValue": value,
                "doc": d,
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {
        "query": term,
        "field": field,
        "topK": top_k,
        "maxScan": max_scan,
        "minScore": min_score,
        "matched": len(scored[:top_k]),
        "results": scored[:top_k],
    }


# ---------------------------------------------------------------------------
# 汎用 Trigger 生成ヘルパ (同様3種)
# ---------------------------------------------------------------------------

class _SearchSpec:
    def __init__(self, tool_name: str, description: str, field: str):
        self.tool_name = tool_name
        self.description = description
        self.field = field


def _register_search_trigger(spec: _SearchSpec):
    tool_properties = [
        {
            "propertyName": "searchTerm",
            "propertyType": "string",
            "description": "検索語 (必須)"
        },
        {
            "propertyName": "topK",
            "propertyType": "integer",
            "description": "最大返却件数 (default 5)"
        },
        {
            "propertyName": "maxScan",
            "propertyType": "integer",
            "description": "最大スキャン件数 (default 200)"
        },
        {
            "propertyName": "minScore",
            "propertyType": "number",
            "description": "最小スコア閾値 0.0-1.0 (default 0.4)"
        },
    ]
    import json as _json

    @_get_app().generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName=spec.tool_name,
        description=spec.description,
        toolProperties=_json.dumps(tool_properties),
    )
    def _handler(context):  # noqa: D401
        import json as _json2
        args = {}
        try:
            if isinstance(context, str):
                parsed = _json2.loads(context)
            else:
                parsed = context
            if isinstance(parsed, dict):
                if isinstance(parsed.get("arguments"), dict):
                    args = parsed["arguments"]
                elif isinstance(parsed.get("mcpToolArgs"), dict):
                    args = parsed["mcpToolArgs"]
                else:
                    args = parsed
        except Exception as e:  # pragma: no cover - defensive
            return {"error": "入力解析に失敗", "details": str(e)}

        term = (args.get("searchTerm") or "").strip()
        if not term:
            return {"error": "searchTerm は必須です"}
        top_k = int(args.get("topK") or 5)
        max_scan = int(args.get("maxScan") or 200)
        min_score = float(args.get("minScore") or 0.4)

        try:
            return _fuzzy_search(spec.field, term, top_k, max_scan, min_score)
        except Exception as e:
            logging.exception("検索処理中にエラー")
            return {"error": "検索失敗", "details": str(e)}

    return _handler


# 3 種類の検索トリガーを登録
_register_search_trigger(_SearchSpec(
    tool_name="search_courses_by_name",
    description="講座名 (courseName) を対象にあいまい検索します。",
    field="courseName",
))

_register_search_trigger(_SearchSpec(
    tool_name="search_courses_by_description",
    description="講座概要 (description) を対象にあいまい検索します。",
    field="description",
))

_register_search_trigger(_SearchSpec(
    tool_name="search_courses_by_company",
    description="会社名 (targetCompany) を対象にあいまい検索します。",
    field="targetCompany",
))
