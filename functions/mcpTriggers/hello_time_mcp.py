import logging
from datetime import datetime, timezone
from ._common import parse_args, build_error, log_and_build_unhandled


def hello_world_mcp(context):
    try:
        args = parse_args(context)
        name = args.get("name") or "World"
        return {"message": f"Hello {name}!"}
    except Exception as e:  # pragma: no cover
        return log_and_build_unhandled(e, tool="hello_world")


def get_current_time_mcp(context):
    try:
        # 引数不要。context が {} / None / 空文字でも無視して現在時刻を返す。
        now = datetime.now(timezone.utc).isoformat()
        logging.info(f"UTC now: {now}")
        return {"utcTime": now}
    except Exception as e:  # pragma: no cover
        return log_and_build_unhandled(e, tool="get_current_time")

__all__ = ["hello_world_mcp", "get_current_time_mcp"]
