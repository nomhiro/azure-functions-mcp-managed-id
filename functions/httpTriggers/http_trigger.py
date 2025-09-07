import logging
import json
import traceback
import uuid
from azure.functions import HttpRequest, HttpResponse

def http_trigger(req: HttpRequest) -> HttpResponse:
    trace_id = uuid.uuid4().hex
    logging.info(f'[http_trigger] start traceId={trace_id}')
    try:
        name = req.params.get('name')
        if not name:
            try:
                req_body = req.get_json()
            except ValueError:
                req_body = None
            if isinstance(req_body, dict):
                name = req_body.get('name')

        if name:
            body = {"message": f"こんにちは、{name} さん。この HTTP トリガー関数は正常に実行されました。", "traceId": trace_id}
        else:
            body = {"message": "HTTP トリガーは正常に実行されました。クエリまたは JSON ボディで name を指定すると挨拶します。", "traceId": trace_id}
        return HttpResponse(json.dumps(body, ensure_ascii=False), status_code=200, mimetype="application/json")
    except Exception as e:  # pragma: no cover
        logging.exception(f"[http_trigger] unhandled traceId={trace_id} error={e}")
        tb = ''.join(traceback.format_exception(type(e), e, e.__traceback__))[-4000:]
        body = {"error": "内部エラー", "traceId": trace_id, "details": tb}
        return HttpResponse(json.dumps(body, ensure_ascii=False), status_code=500, mimetype="application/json")
