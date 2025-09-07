import logging
from azure.functions import HttpRequest, HttpResponse, FunctionApp


def _get_app() -> FunctionApp:
    from function_app import app  # type: ignore
    return app

@_get_app().route(route="http_trigger")
def http_trigger(req: HttpRequest) -> HttpResponse:
    logging.info('Python HTTP trigger function がリクエストを処理しました。')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = None
        if isinstance(req_body, dict):
            name = req_body.get('name')

    if name:
        return HttpResponse(f"こんにちは、{name} さん。この HTTP トリガー関数は正常に実行されました。")
    else:
        return HttpResponse(
            "この HTTP トリガー関数は正常に実行されました。クエリ文字列またはリクエストボディに name を渡すと、個別の応答が得られます。",
            status_code=200
        )
