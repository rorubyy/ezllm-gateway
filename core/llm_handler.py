from typing import (Callable, Dict)
import time
from azure.identity import (ClientSecretCredential,
                            DefaultAzureCredential,
                            get_bearer_token_provider)

class LLMHandler:
    def __init__(self):
        self.azure_llm_handler = AzureLLMHandler()
        

    def get_llm_provider(self, model: str):
        return model.split('/')[0]


    def configure_model_routing(self, **kwargs):
        try:
            routing_configs = kwargs.pop("routing_configs")
            model_name = kwargs.get("model")
            if model_name is None:
                raise ValueError("Model must be provided in the kwargs")

            llm_route_config = routing_configs.get(model_name)
            if llm_route_config is None:
                raise KeyError(f"No route configuration found for model {model_name}")

            # Update kwargs with specific route configurations
            kwargs["model"] = llm_route_config.get("model")
            kwargs["api_base"] = llm_route_config.get("api_base")
            kwargs["api_key"] = llm_route_config.get("api_key")

            # Determine the custom provider and handle accordingly
            custom_llm_provider = self.get_llm_provider(llm_route_config.get("model"))
            if custom_llm_provider == "azure":
                kwargs = self.azure_llm_handler.configure_azure_authentication(llm_route_config, **kwargs)
            
            return kwargs
        except KeyError as e:
            print(f"Missing required key: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            


class AzureLLMHandler:
    def __init__(self):
        self.scopes = 'https://cognitiveservices.azure.com/.default'
        self.token_cache: Dict[str, Dict[str, Any]] = {}


    def configure_azure_authentication(self, llm_route_config: dict, **kwargs):
        azure_ad_token_provider = llm_route_config.get("azure_ad_token_provider")
        azure_ad_token = llm_route_config.get("azure_ad_token_provider")
        
        if not azure_ad_token and not azure_ad_token_provider:
            azure_ad_token_provider = self.get_azure_ad_token_provider(client_id = llm_route_config.get("client_id"), 
                                                                        tenant_id = llm_route_config.get("tenant_id"), 
                                                                        client_secret =  llm_route_config.get("client_secret"))
            azure_ad_token = azure_ad_token_provider()

        kwargs["azure_ad_token"] = azure_ad_token
        kwargs["extra_headers"] = llm_route_config.get("extra_headers")

        return kwargs

    def _get_cached_token_provider(self, cache_key: str) ->  Callable[[], str]:
        token_info = self.token_cache.get(cache_key)
        if token_info and not self._check_expire(token_info):
            return token_info['azure_ad_token_provider']
        return None


    def _set_cache(self, cache_key: str, azure_ad_token_provider: Callable[[], str], expires_on: int) -> None:
        self.token_cache[cache_key] = {
            'azure_ad_token_provider': azure_ad_token_provider,
            'expires_on': expires_on
        }

    def get_azure_ad_token_provider(self, client_id: str, tenant_id: str, client_secret: str) -> Callable[[], str]:
        cache_key = f"{client_id}_{tenant_id}"
        azure_ad_token_provider = self._get_cached_token_provider(cache_key)
        if azure_ad_token_provider:
            return azure_ad_token_provider
        else:
            try:
                if not client_id or not tenant_id or not client_secret:
                    raise ValueError("Client ID, Tenant ID, and Client Secret must be provided")

                credential = ClientSecretCredential(client_id=client_id, tenant_id=tenant_id, client_secret=client_secret)
                azure_ad_token_provider = get_bearer_token_provider(credential, self.scopes)

                self._set_cache(cache_key, azure_ad_token_provider, expires_on = credential.get_token(self.scopes)[1])

            except ValueError as e:
                print(f"Invalid client credentials: {e}. Using DefaultAzureCredential instead.")
            credential = DefaultAzureCredential()

            return azure_ad_token_provider
    
    def _check_expire(self, token_info):
        current_time = int(time.time())
        expires_on = token_info.get('expires_on', 0)
        return expires_on - current_time < 60

