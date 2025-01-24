import json
import os

import litellm
import yaml
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from litellm.types.utils import ModelResponseStream
from starlette.responses import StreamingResponse
from prometheus_client import make_asgi_app
import route_handler
from integrations.prometheus import PrometheusLogger

# *** 載入相關設定檔案 ***

# 路由的設定: routing_configs.yaml
with open("routing_configs.yaml", "r") as routing_configs_yaml_file:
    routing_configs_yaml = yaml.safe_load(routing_configs_yaml_file)

# 創建一個 dict 來保留 routing_configs 的映射 (key: model_name --> value: litellm_params)
routing_configs = {}

for model in routing_configs_yaml["model_list"]:
    routing_configs[model['model_name']] = model['litellm_params']

# 用戶的設定: user_configs.yaml
with open("user_configs.yaml", "r") as user_configs_yaml_file:
    user_configs_yaml = yaml.safe_load(user_configs_yaml_file)

# 創建一個 dict 來保留 user_configs 的映射 (key: user_token --> value: user_profile)
user_configs = {}

for user in user_configs_yaml["user_list"]:
    user_configs[user['user_token']] = user['user_profile']

# 取得 mater token 設定(從環境變數EZLLM_GATEWAY_MASTER_TOKEN取得, 預設"sk-ezllm-master-token"）
master_token = os.getenv("EZLLM_GATEWAY_MASTER_TOKEN", "sk-ezllm-master-token")

# *** LiteLLM 的實例設定 ***
prometheusLogger = PrometheusLogger(routing_configs=routing_configs, user_configs=user_configs)

litellm.callbacks = [prometheusLogger]

# *** 構建 fastapi 的實例并進行設定 ***
app = FastAPI()

# 新增middleware來處理跨域資源共享 (CORS)的設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 新增middleware來處理使用者送進來的token擷取
oauth2_schema = OAuth2PasswordBearer(tokenUrl="token")

# 構建兩個 function 來對送到gateway的req token來進行驗證

# 對Gateway使用者(使用user_tokne)進行身份驗證
def user_token_auth(api_token: str = Depends(oauth2_schema)):
    if api_token == master_token:
        return #使用者使用了 master_token, 通常是管理者才知道 master_token

    if api_token not in user_configs:
        # 如果api_token不存在所設定的user_token，則觸發 HTTP 401 Unauthorized error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid user key",
        )

# 對Gateway管理者(使用master_token)進行身份驗證
def master_token_auth(api_token: str = Depends(oauth2_schema)):
    if api_token != master_token:
        # Raise an HTTP 401 Unauthorized error if the API key is invalid
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid admin key",
        )


# *** 構建 Prometheus metrics 指標實例 **
# Add prometheus asgi middleware to route /metrics requests
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# *** 構建 fastapi 的REST API ***

# for streaming
def streaming_chunk_generator(response)->StreamingResponse:
    # chunk的class type是ModelResponseStream
    for chunk in response:
        # Convert ModelResponseStream to json text and return back to client
        yield f"data: {json.dumps(chunk.json())}\n\n"

# 構建一個 "/chat/completions" 的 api route 來處理 chat completion 的 LLM API 呼叫
@app.post("/chat/completions", dependencies=[Depends(user_token_auth)])
@app.post("/v1/chat/completions", dependencies=[Depends(user_token_auth)])
@app.post("/completions", dependencies=[Depends(user_token_auth)])
@app.post("/v1/completions", dependencies=[Depends(user_token_auth)])
async def chat_completion(request: Request):
    # 擷取由client端提交的api_token
    api_token = request.headers.get("Authorization").replace("Bearer ", "").strip()
    # 擷取由client端提交request的body
    req_body = await request.json()
    # 將判斷後端api所需的metadata擷取出來并組建一個用來結route_handler使用的物件
    req_body["master_token"] = master_token
    req_body["user_token"] = api_token
    req_body["routing_configs"] = routing_configs
    req_body["user_configs"] = user_configs
    req_body["req_url_path"] = request.url.path
    # 判斷使用者是否有設定"stream"的設定
    if "stream" in req_body:
        if type(req_body['stream']) == str:
            if req_body['stream'].strip().lower() == "true":
                req_body['stream'] = True # 轉換成 boolean

    # *** 處理LLM Api呼叫與routing
    try:
        response = route_handler.completion(**req_body)
        # 判斷是否要處理streaming的response
        if 'stream' in req_body and req_body['stream']==True:
            return StreamingResponse(streaming_chunk_generator(response), media_type='text/event-stream')

        # 將llm api呼叫的結果回覆給client
        return response
    except Exception as e:
        raise e

# 構建一個 "/v1/models" 的 api route 來返回gateway有配置的llm模型
@app.get("/v1/models", dependencies=[Depends(user_token_auth)])
@app.get("/models", dependencies=[Depends(user_token_auth)])
async def model_list():
    global routing_configs
    return dict(
        data=[
            {
                "id": model,
                "object": "model",
                "created": 1677610602,
                "owned_by": "xxxxx",
            }
            for model in routing_configs.keys()
        ],
        object="list",
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=os.getenv("PORT", 8080))