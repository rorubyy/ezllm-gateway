# init_guardrails.py
 
import litellm
from typing import List, Dict, Optional, TypedDict
# from litellm._logging import verbose_proxy_logger
from litellm.types.guardrails import Guardrail

class LitellmParams(TypedDict):
    guardrail: str
    mode: str
    api_key: str
    api_base: Optional[str]
    guard_name: Optional[str]

def init_guardrails(
    all_guardrails: List[Dict],
    config_file_path: Optional[str] = None,
):
    # Convert the loaded data to the TypedDict structure
    guardrail_list = []

    # Parse each guardrail and replace environment variables
    for guardrail in all_guardrails:

        # Init litellm params for guardrail
        litellm_params_data = guardrail["litellm_params"]
        # verbose_proxy_logger.debug("litellm_params= %s", litellm_params_data)

        _litellm_params_kwargs = {
            k: litellm_params_data[k] if k in litellm_params_data else None
            for k in LitellmParams.__annotations__.keys()
        }

        litellm_params = LitellmParams(**_litellm_params_kwargs)  # type: ignore

        if litellm_params["api_key"]:
            if litellm_params["api_key"].startswith("os.environ/"):
                litellm_params["api_key"] = str(get_secret(litellm_params["api_key"]))  # type: ignore

        if litellm_params["api_base"]:
            if litellm_params["api_base"].startswith("os.environ/"):
                litellm_params["api_base"] = str(get_secret(litellm_params["api_base"]))  # type: ignore

        if litellm_params["guardrail"] == "guardrails_ai":
            from my_guardrails.guardrails_ai import GuardrailsAI

            _guard_name = litellm_params.get("guard_name")
            if _guard_name is None:
                raise Exception(
                    "GuardrailsAIException - Please pass the Guardrails AI guard name via 'litellm_params::guard_name'"
                )
            _guardrails_ai_callback = GuardrailsAI(
                api_base=litellm_params.get("api_base"),
                guard_name=_guard_name,
                guardrail_name="guardrails_ai",
            )
            litellm.callbacks.append(_guardrails_ai_callback)
        else:
            raise ValueError(f"Unsupported guardrail: {litellm_params['guardrail']}")
        
        parsed_guardrail = Guardrail(
            guardrail_name=guardrail["guardrail_name"],
            litellm_params=litellm_params,
        )

        guardrail_list.append(parsed_guardrail)
        guardrail["guardrail_name"]
    