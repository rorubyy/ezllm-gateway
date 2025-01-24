import httpx
from fastapi import HTTPException

import litellm

# 跳過對後端 LLM Api 的 SSL 憑證的驗證
litellm.client_session = httpx.Client(verify=False)

# 用來處理chat completion與text generation的LLM Api proxy路由
def completion(**kwargs) -> litellm.ModelResponse:
    # 取得Gateway的預設 master token
    master_token: str = kwargs.pop("master_token")
    # 取得使用者的 token
    user_token: str = kwargs.pop("user_token")
    # 取得要routing到後端不同LLM API的設定
    routing_configs: dict = kwargs.pop("routing_configs")
    # 取得user_token所對應到的user_profile
    user_configs: dict = kwargs.pop("user_configs")
    # 取得request的url路徑可用來判斷呼叫的LLM Api服務
    req_url_path:str = kwargs.pop("req_url_path")

    # 定義一個私有的function來routing llm req并把呼叫llm api的結果回傳
    def _completion()-> litellm.ModelResponse:
        try:
            # 取得llm req的model name
            model_name = kwargs["model"]
            # 取得在llm_route_config中對應到model_name的設定(litellm)
            llm_route_config: dict = routing_configs.get(model_name)
            if llm_route_config is not None:
                # 修改原本llm req中要修改的三個主要參數:api_base, api_key
                # 呼叫的參數結構可參考LiteLLM Supported Models & Providers的資訊 (https://docs.litellm.ai/docs/providers)
                kwargs["model"] = llm_route_config.get("model")
                if llm_route_config.get("api_base") is not None:
                    kwargs["api_base"] = llm_route_config.get("api_base")
                if llm_route_config.get("api_key") is not None:
                    kwargs["api_key"] = llm_route_config.get("api_key")
            else:
                # 找不到對應model的routing設定
                raise HTTPException(
                    status_code=404,
                    detail=f"could not find model:{model_name} route setting, check model mapping configuration."
                )
            # *** 透過litellm來呼叫llm的api呼叫 ***
            # 檢查本次的llm req的user_token是否與master_token相同, 如果相同就直接去呼叫後端的llm api
            if user_token == master_token:
                kwargs["user"] = "admin"
                if req_url_path in ["/completions", "/v1/completions"]:
                    response = litellm.text_completion(**kwargs)
                else: # ["/chat/completions", "/v1/chat/completions"]
                    response = litellm.completion(**kwargs)
            else:
                # 根據user_token來進行相關有關user的相關驗證或處理
                user_profile:dict = user_configs[user_token] # {id: 11309006, name: "Ruby Lo", project: test, org: mlx000}
                kwargs["user"] = user_profile.get("id")
                # To Be Developing ...
                if req_url_path in ["/completions", "/v1/completions"]:
                    response = litellm.text_completion(**kwargs)
                else:  # ["/chat/completions", "/v1/chat/completions"]
                    response = litellm.completion(**kwargs)

            # 回覆api呼叫結果
            return response
        except Exception as e:
            raise e

    # 把內部_completion呼叫的結果回傳
    return _completion()


