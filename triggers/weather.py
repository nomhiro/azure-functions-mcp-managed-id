import logging
import json
import random
from datetime import datetime, timezone

from azure.functions import FunctionApp

# function_app モジュールの app を取得するためのヘルパ

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

_WEATHER_CITY_PROPERTY_NAME = "city"
_WEATHER_TIME_PROPERTY_NAME = "time"
_tool_properties_weather_object = [
    ToolProperty(_WEATHER_CITY_PROPERTY_NAME, "string", "都市名 (例: Tokyo)。"),
    ToolProperty(_WEATHER_TIME_PROPERTY_NAME, "string", "基準となる現在時刻 (ISO8601)。"),
]
_tool_properties_weather_json = json.dumps([prop.to_dict() for prop in _tool_properties_weather_object])

@_get_app().generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_weather",
    description="都市と現在時刻を基に簡易な天気情報を返します。",
    toolProperties=_tool_properties_weather_json,
)
def get_weather(context):
    raw_context = context
    args: dict = {}
    try:
        if isinstance(raw_context, str):
            parsed = json.loads(raw_context)
        else:
            parsed = raw_context
        if isinstance(parsed, dict):
            if isinstance(parsed.get("arguments"), dict):
                args = parsed.get("arguments")
            elif isinstance(parsed.get("mcpToolArgs"), dict):
                args = parsed.get("mcpToolArgs")
            else:
                args = parsed
        else:
            logging.warning(f"get_weather: context が dict ではありません: {type(parsed)}")
    except Exception as e:
        logging.error(f"get_weather: context パース失敗: {e}; raw={raw_context}")
        return {"error": "context の解析に失敗しました", "details": str(e)}

    city = args.get(_WEATHER_CITY_PROPERTY_NAME)
    time_value = args.get(_WEATHER_TIME_PROPERTY_NAME)

    if not city:
        return {"error": "city が指定されていません"}
    if not time_value:
        time_value = datetime.now(timezone.utc).isoformat()

    try:
        tempC = random.randint(-10, 35)
        tempF = round(tempC * 9 / 5 + 32, 1)
        weather_choices = [
            "Sunny",
            "Partly cloudy",
            "Cloudy",
            "Rain",
            "Light rain",
            "Thunderstorm",
            "Snow",
            "Fog",
        ]
        weatherDesc = random.choice(weather_choices)
        wind = random.randint(0, 40)
        humidity = random.randint(20, 100)
        simplified = {
            "tempC": str(tempC),
            "tempF": str(tempF),
            "weatherDesc": weatherDesc,
            "windspeedKmph": str(wind),
            "humidity": str(humidity),
        }
        result = {"city": city, "time": time_value, "weather": simplified}
        logging.info(f"天気(仮)生成成功: {result}")
        return result
    except Exception as e:
        logging.error(f"天気(仮)生成失敗: {e}")
        return {"error": "天気情報生成に失敗しました", "details": str(e), "city": city}
