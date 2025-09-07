import logging
from datetime import datetime, timezone
import json

from .. import function_app  # relative import to get the shared app instance is not possible (Azure functions loader) so we import via absolute name at runtime
from azure.functions import FunctionApp

# Azure Functions のホストは `function_app.py` の module 名をエントリとして読むため
# そこですでに生成済みの app を import する。 (循環参照を避けるため遅延取得関数を利用)

def _get_app() -> FunctionApp:
    from function_app import app  # type: ignore
    return app

class ToolProperty:
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description

    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }

# ---- 現在時刻取得ツール用設定 ----
_tool_properties_now_object = []  # 引数なし
_tool_properties_now_json = json.dumps([prop.to_dict() for prop in _tool_properties_now_object])

@_get_app().generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_current_time",
    description="現在の UTC 時刻を ISO8601 で返します。",
    toolProperties=_tool_properties_now_json,
)
def get_current_time(context):
    now = datetime.now(timezone.utc).isoformat()
    logging.info(f"現在時刻(UTC): {now}")
    return {"utcTime": now}
