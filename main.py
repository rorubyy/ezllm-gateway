# import json
# import os

# import litellm
# import yaml
# from fastapi import FastAPI, Depends, HTTPException, status, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.security import OAuth2PasswordBearer
# from litellm.types.utils import ModelResponseStream
# from starlette.responses import StreamingResponse
# from prometheus_client import make_asgi_app
# from core.route_handler import RouteHandler
# from integrations.prometheus import PrometheusLogger


# import requests
# import time
# from utils.model_config import ModelConfig
# from utils.user_config import UserConfig

# def load_configurations():
#     """Load all necessary configurations from files and environment."""
#     global routing_configs, user_configs, master_token, route_handler
#     # Load routing configurations
#     mc = ModelConfig()
#     routing_configs = mc.load_config("config/routing_configs.yaml")

#     # Load user configurations
#     uc = UserConfig()
#     user_configs = uc.load_config('config/user_configs.yaml')

#     # initial router handler
#     route_handler = RouteHandler()

#     # Retrieve master token from environment
#     master_token = os.getenv("EZLLM_GATEWAY_MASTER_TOKEN", "sk-ezllm-master-token")

#     # Initialize logging
#     global prometheusLogger
#     prometheusLogger = PrometheusLogger(routing_configs=routing_configs, user_configs=user_configs)
#     litellm.callbacks = [prometheusLogger]

# def setup_middleware(app: FastAPI):
#     """Configure middlewares for the FastAPI application."""
#     app.add_middleware(
#         CORSMiddleware,
#         allow_origins=["*"],
#         allow_credentials=True,
#         allow_methods=["*"],
#         allow_headers=["*"]
#     )

# def create_app() -> FastAPI:
#     """Create and configure the FastAPI application."""
#     load_configurations()
#     app = FastAPI()
#     setup_middleware(app)

#     # Add Prometheus metrics
#     metrics_app = make_asgi_app()
#     app.mount("/metrics", metrics_app)

#     return app

# app = create_app()


# # 對Gateway使用者(使用user_tokne)進行身份驗證
# def user_token_auth(api_token: str = Depends(OAuth2PasswordBearer(tokenUrl="token"))):
#     if api_token == master_token:
#         return #使用者使用了 master_token, 通常是管理者才知道 master_token

#     if api_token not in user_configs:
#         # 如果api_token不存在所設定的user_token，則觸發 HTTP 401 Unauthorized error
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="invalid user key",
#         )

# # 對Gateway管理者(使用master_token)進行身份驗證
# def master_token_auth(api_token: str = Depends(OAuth2PasswordBearer(tokenUrl="token"))):
#     if api_token != master_token:
#         # Raise an HTTP 401 Unauthorized error if the API key is invalid
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="invalid admin key",
#         )


# # for streaming
# def streaming_chunk_generator(response)->StreamingResponse:
#     # chunk的class type是ModelResponseStream
#     for chunk in response:
#         # Convert ModelResponseStream to json text and return back to client
#         yield f"data: {json.dumps(chunk.json())}\n\n"

# # 構建一個 "/chat/completions" 的 api route 來處理 chat completion 的 LLM API 呼叫
# @app.post("/chat/completions", dependencies=[Depends(user_token_auth)])
# @app.post("/v1/chat/completions", dependencies=[Depends(user_token_auth)])
# @app.post("/completions", dependencies=[Depends(user_token_auth)])
# @app.post("/v1/completions", dependencies=[Depends(user_token_auth)])

# async def chat_completion(request: Request):
#     start_time = time.time()

#     # 擷取由client端提交的api_token
#     api_token = request.headers.get("Authorization").replace("Bearer ", "").strip()
#     # 擷取由client端提交request的body
#     req_body = await request.json()
#     # 將判斷後端api所需的metadata擷取出來并組建一個用來結route_handler使用的物件
#     req_body["master_token"] = master_token
#     req_body["user_token"] = api_token
#     req_body["routing_configs"] = routing_configs
#     req_body["user_configs"] = user_configs
#     req_body["req_url_path"] = request.url.path

#     model_name = req_body.get("model")
#     model_config = routing_configs.get(model_name)

#     # 判斷使用者是否有設定"stream"的設定
#     if "stream" in req_body:
#         if type(req_body['stream']) == str:
#             if req_body['stream'].strip().lower() == "true":
#                 req_body['stream'] = True # 轉換成 boolean

#     # *** 處理LLM Api呼叫與routing
#     try:
#         response = route_handler.completion(**req_body)
#         # 判斷是否要處理streaming的response
#         if 'stream' in req_body and req_body['stream']==True:
#             return StreamingResponse(streaming_chunk_generator(response), media_type='text/event-stream')

#         # 將llm api呼叫的結果回覆給client
#         return response

#     except Exception as e:
#         end_time = time.time()
#         prometheusLogger.log_failure_event(req_body, getattr(e, 'status_code', None), start_time, end_time)
#         raise e


# # 構建一個 "/v1/models" 的 api route 來返回gateway有配置的llm模型
# @app.get("/v1/models", dependencies=[Depends(user_token_auth)])
# @app.get("/models", dependencies=[Depends(user_token_auth)])
# async def model_list():
#     global routing_configs
#     return dict(
#         data=[
#             {
#                 "id": model,
#                 "object": "model",
#                 "created": 1677610602,
#                 "owned_by": "xxxxx",
#             }
#             for model in routing_configs.keys()
#         ],
#         object="list",
#     )

# if __name__ == "__main__":
#     import uvicorn

#     uvicorn.run(app, host="0.0.0.0", port=os.getenv("PORT", 8080))


import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from routes.chat import router as chat_router
from utils.setting import settings

def setup_middleware(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

def create_app() -> FastAPI:
    app = FastAPI()
    setup_middleware(app)
    
    # Prometheus Metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # Register Routes
    app.include_router(chat_router)

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
