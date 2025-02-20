from openai import OpenAI
import httpx
 
# 初始化 OpenAI 客戶端，使用自定義的 base_url 和虛擬 api_key
client = OpenAI(
    base_url="http://0.0.0.0:8080", 
    api_key="sk-0000", 
    http_client=httpx.Client(verify=False) 
)
 
# 定義對話內容
messages = [
    {
        "role": "user",
        "content": "hi my email is joy_AN_lin@wistron.com"
        # "content": "choose a number from 1 to 10."
    }
]

# completion = client.completions.create(
#     model="llama3.1-8b-instruct",  
#     prompt="Remenber my email: joy_AN_lin@wistron.com",
#     # stream=True,
#     extra_body={
#         "guardrails": ["guardrails_ai-post"]
#     }
# )
 
# 呼叫 Chat Completions 接口
completion = client.chat.completions.create(
    model="llama3.1-8b-instruct",  
    messages=messages,
    # stream=True,
    extra_body={
        "guardrails": ["guardrails_ai-post"]
    }
)
 
# 輸出結果
print(completion)