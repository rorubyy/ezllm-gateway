import httpx
import litellm
from core.llm_handler import LLMHandler
from fastapi import HTTPException


# Skip SSL verification for the backend LLM API
litellm.client_session = httpx.Client(verify=False)

class RouteHandler:
    def __init__(self):
        self.llm_handler = LLMHandler()

    def _extract_request_data(self, kwargs: dict) -> tuple:
        master_token = kwargs.pop("master_token")
        user_token = kwargs.pop("user_token")
        user_configs = kwargs.pop("user_configs")
        req_url_path = kwargs.pop("req_url_path")
        
        return master_token, user_token, user_configs, req_url_path, kwargs


    def _process_user(self, user_token: str, master_token: str, user_configs: dict) -> dict:
        user_info = {}

        if user_token == master_token:
            user_info["user"] = "admin"
        else:
            user_profile: dict = user_configs.get(user_token, {})
            user_info["user"] = str(user_profile.get("id", ""))

        return user_info


    async def chat_completion(self, **kwargs) -> litellm.ModelResponse:
        try: 
            master_token, user_token, user_configs, req_url_path, remaining_kwargs = self._extract_request_data(kwargs)

            updated_kwargs = self.llm_handler.configure_model_routing(**remaining_kwargs)
            user_info = self._process_user(user_token, master_token, user_configs)
            updated_kwargs.update(user_info)


            response = await litellm.acompletion(**updated_kwargs)
            return response  
        
        except AttributeError as e:
            # Specifically handle cases where an attribute error occurs
            detail_msg = f"Attribute error occurred: {str(e)}"
            raise HTTPException(status_code=400, detail=detail_msg)
        
        except Exception as e:
            # General exception catch to prevent leaking of server errors
            raise HTTPException(status_code=500, detail=e)


    async def completion(self, **kwargs) -> litellm.ModelResponse:
        try: 
            master_token, user_token, user_configs, req_url_path, remaining_kwargs = self._extract_request_data(kwargs)

            updated_kwargs = self.llm_handler.configure_model_routing(**remaining_kwargs)
            user_info = self._process_user(user_token, master_token, user_configs)
            updated_kwargs.update(user_info)

            response = await litellm.atext_completion(**updated_kwargs)
            return response  
        
        except AttributeError as e:
            # Specifically handle cases where an attribute error occurs
            detail_msg = f"Attribute error occurred: {str(e)}"
            raise HTTPException(status_code=400, detail=detail_msg)
        
        except Exception as e:
            # General exception catch to prevent leaking of server errors
            raise HTTPException(status_code=500, detail=e)


