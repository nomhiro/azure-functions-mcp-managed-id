"""Shared helpers for MCP trigger modules."""
import json
import logging
import traceback
import uuid
from typing import Any, Dict

def parse_args(context) -> Dict[str, Any]:
    """MCP コンテキスト文字列/辞書を安全に解析して引数辞書を返す。

    受理フォーマット:
      - {"arguments": {...}}
      - {"mcpToolArgs": {...}}
      - {...} 直接辞書
      - 非JSONのプレーン文字列 → {"raw": "..."} としてフォールバック
    """
    if context is None:
        return {}
    # 文字列の場合 JSON として読めなければ raw へフォールバック
    if isinstance(context, str):
        txt = context.strip()
        if not txt:
            return {}
        try:
            parsed = json.loads(txt)
        except Exception:  # JSON でない → raw
            return {"raw": txt}
    else:
        parsed = context

    if isinstance(parsed, dict):
        # 標準的なラップキー
        if isinstance(parsed.get("arguments"), dict):
            return parsed["arguments"]
        if isinstance(parsed.get("mcpToolArgs"), dict):
            return parsed["mcpToolArgs"]
        return parsed
    return {}

def build_error(message: str, *, details: str | None = None, kind: str = "Error", extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """標準化されたエラーペイロードを生成。
    traceId を付与し、呼び出し側ログと突合しやすくする。
    """
    payload: Dict[str, Any] = {
        "error": message,
        "type": kind,
        "traceId": uuid.uuid4().hex,
    }
    if details:
        payload["details"] = details
    if extra:
        payload.update(extra)
    return payload


def log_and_build_unhandled(exc: Exception, tool: str) -> Dict[str, Any]:
    """未捕捉例外をログ出力し統一レスポンスを返す。"""
    logging.exception(f"[{tool}] Unhandled exception: {exc}")
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return build_error(
        "内部エラーが発生しました",
        details="".join(tb)[-4000:],  # 長すぎる場合末尾のみ
        kind="UnhandledException",
        extra={"tool": tool},
    )

__all__ = ["parse_args", "build_error", "log_and_build_unhandled"]
