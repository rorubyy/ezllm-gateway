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
from utils.openai import Completion
from my_guardrails.guardrails_ai import GuardrailsAI
from litellm.proxy._types import UserAPIKeyAuth
from litellm.types.guardrails import GuardrailEventHooks

router = APIRouter()
route_handler = RouteHandler()
prometheusLogger = PrometheusLogger(*config_loader.load_configs())
if prometheusLogger not in litellm.callbacks:
    litellm.callbacks.insert(0, prometheusLogger)


def streaming_chunk_generator(response):
    for chunk in response:
        yield f"data: {json.dumps(chunk.json())}\n\n"


def completion_streaming_chunk_generator(response):
    for chunk in response:
        completion_data = json.loads(chunk.json())
        completion_instance = Completion(**completion_data)

        yield f"data: {completion_instance.json()}\n\n"


def prepare_request_data(request: Request) -> dict:
    api_token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    routing_configs, user_configs = config_loader.load_configs()

    return {
        "master_token": settings.MASTER_TOKEN,
        "user_token": api_token,
        "routing_configs": routing_configs,
        "user_configs": user_configs,
        "req_url_path": request.url.path
    }

def whether_should_run_guardrail( guardrail_name, guardrails_list, event_type):
    for guardrail in guardrail_name:
        if guardrail in guardrails_list and guardrails_list[guardrail].get('mode') == event_type.value:
            return True
    return False

@router.post("/chat/completions", dependencies=[Depends(user_token_auth)])
@router.post("/v1/chat/completions", dependencies=[Depends(user_token_auth)])
async def chat_completion(request: Request,):
    start_time = time.time()
    req_body = await request.json()
    user_api_key_dict = UserAPIKeyAuth(api_key="sk-abc")
    req_body.update(prepare_request_data(request))

    ### CALL HOOKS(for guardrials) ###
    for callback in litellm.callbacks:
        if isinstance(callback, GuardrailsAI):
            event_type: GuardrailEventHooks = GuardrailEventHooks.pre_call
            guardrail_name = req_body.get("guardrails", [])
            guardrails_list = req_body.get('routing_configs', {}).get('guardrails', {})

            if whether_should_run_guardrail(guardrail_name, guardrails_list, event_type):
                req_body = await callback.async_pre_call_hook(
                    user_api_key_dict=user_api_key_dict, 
                    data = req_body, 
                    call_type="completion"
                )
                break  

    try:
        if req_body.get("stream", False):
            response = route_handler.stream_chat_completion(**req_body)
            return StreamingResponse(streaming_chunk_generator(response), media_type='text/event-stream') 
        else:
            response = await route_handler.chat_completion(**req_body)
            for callback in litellm.callbacks:
                if isinstance(callback, GuardrailsAI):
                    event_type: GuardrailEventHooks = GuardrailEventHooks.post_call
                    guardrails_name = req_body.get("guardrails", [])
                    routing_guardrails = req_body.get('routing_configs', {}).get('guardrails', {})

                    if whether_should_run_guardrail(guardrails_name, routing_guardrails, event_type):
                        response = await callback.async_post_call_success_hook(
                            data = req_body,
                            user_api_key_dict=user_api_key_dict,
                            response=response
                        )
                        break                    
            return response
    
    except Exception as e:
        end_time = time.time()
        prometheusLogger.log_failure_event(req_body, getattr(e, 'status_code', None), start_time, end_time)
        raise e


@router.post("/completions", dependencies=[Depends(user_token_auth)])
@router.post("/v1/completions", dependencies=[Depends(user_token_auth)])
async def completion(request: Request):
    start_time = time.time()
    req_body = await request.json()
    req_body.update(prepare_request_data(request))

    try:
        if req_body.get("stream", False):
            response = route_handler.stream_completion(**req_body)
            return StreamingResponse(streaming_chunk_generator(response), media_type='text/event-stream') 
        else:
            response = await route_handler.completion(**req_body)
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
