import random
from datetime import datetime, timezone
from ._common import parse_args, build_error, log_and_build_unhandled

_weather_choices = [
    "Sunny","Partly cloudy","Cloudy","Rain","Light rain","Thunderstorm","Snow","Fog"
]

def get_weather_mcp(context):
    try:
        args = parse_args(context)
        city = args.get("city")
        if not city:
            return build_error("city が指定されていません", kind="ValidationError", extra={"field": "city"})
        time_value = args.get("time") or datetime.now(timezone.utc).isoformat()
        temp_c = random.randint(-10, 35)
        temp_f = round(temp_c * 9 / 5 + 32, 1)
        return {
            "city": city,
            "time": time_value,
            "weather": {
                "tempC": str(temp_c),
                "tempF": str(temp_f),
                "weatherDesc": random.choice(_weather_choices),
                "windspeedKmph": str(random.randint(0, 40)),
                "humidity": str(random.randint(20, 100)),
            },
        }
    except Exception as e:  # pragma: no cover
        return log_and_build_unhandled(e, tool="get_weather")

__all__ = ["get_weather_mcp"]
