import json
import time
from fastapi import APIRouter, Request, Depends
from starlette.responses import StreamingResponse
from core.route_handler import RouteHandler
from integrations.prometheus import PrometheusLogger
from auth.auth_manager import user_token_auth
from utils.config_loader import config_loader
from utils.setting import settings
import litellm


router = APIRouter()
route_handler = RouteHandler()
prometheusLogger = PrometheusLogger(*config_loader.load_configs())
litellm.callbacks = [prometheusLogger]


async def streaming_chunk_generator(response):
    async for chunk in response:
        yield f"data: {json.dumps(chunk.json())}\n\n"

@router.post("/chat/completions", dependencies=[Depends(user_token_auth)])
@router.post("/v1/chat/completions", dependencies=[Depends(user_token_auth)])
@router.post("/completions", dependencies=[Depends(user_token_auth)])
@router.post("/v1/completions", dependencies=[Depends(user_token_auth)])
async def chat_completion(request: Request):
    start_time = time.time()
    api_token = request.headers.get("Authorization").replace("Bearer ", "").strip()
    req_body = await request.json()

    req_body.update({
        "master_token": settings.MASTER_TOKEN,
        "user_token": api_token,
        "routing_configs": config_loader.load_configs()[0],
        "user_configs": config_loader.load_configs()[1],
        "req_url_path": request.url.path
    })

    try:
        response = await route_handler.completion(**req_body)
        if req_body.get("stream", False):
            return StreamingResponse(streaming_chunk_generator(response), media_type='text/event-stream')

        return response
    except Exception as e:
        end_time = time.time()
        prometheusLogger.log_failure_event(req_body, getattr(e, 'status_code', None), start_time, end_time)
        raise e

@router.get("/v1/models", dependencies=[Depends(user_token_auth)])
@router.get("/models", dependencies=[Depends(user_token_auth)])
async def model_list():
    routing_configs, _ = config_loader.load_configs()
    return {
        "data": [{"id": model, "object": "model", "created": 1677610602, "owned_by": "xxxxx"} for model in routing_configs.keys()],
        "object": "list",
    }
