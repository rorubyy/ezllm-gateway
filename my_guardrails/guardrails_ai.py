import json
from typing import Any, Dict, List, Literal, Optional, Union, TypedDict

import litellm
from litellm.caching.caching import DualCache
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy.guardrails.guardrail_helpers import should_proceed_based_on_metadata
from litellm.types.guardrails import GuardrailEventHooks
from litellm.litellm_core_utils.prompt_templates.common_utils import (
    get_content_from_model_response,
)
from litellm.proxy.common_utils.callback_utils import (
    add_guardrail_to_applied_guardrails_header,
)
from fastapi import HTTPException


class GuardrailsAIResponse(TypedDict):
    callId: str
    rawLlmOutput: str
    validatedOutput: str
    validationPassed: bool

class GuardrailsAI(CustomGuardrail):
    def __init__(
        self,
        guard_name: str,
        api_base: Optional[str] = None,
        **kwargs,
    ):

        self.guardrails_ai_api_base = api_base 
        self.guardrails_ai_guard_name = guard_name
        self.optional_params = kwargs
        supported_event_hooks = [GuardrailEventHooks.post_call, GuardrailEventHooks.pre_call]
        super().__init__(supported_event_hooks=supported_event_hooks, **kwargs)

    def whether_should_run_guardrail(self, guardrails_name, routing_guardrails, event_type):
        for guardrail in guardrails_name:
            if guardrail in routing_guardrails:
                guardrail_config = routing_guardrails[guardrail]
                if guardrail_config.get('mode') == event_type.value:
                    return True
        return False

    async def make_guardrails_ai_api_request(self, llm_output: str, request_data: dict):
        from httpx import URL

        data = {
            "llmOutput": llm_output,
            **self.get_guardrail_dynamic_request_body_params(request_data=request_data),
        }
        _json_data = json.dumps(data)
        response = await litellm.module_level_aclient.post(
            url=str(
                URL(self.guardrails_ai_api_base).join(
                    f"guards/{self.guardrails_ai_guard_name}/validate"
                )
            ),
            data=_json_data,
            headers={
                "Content-Type": "application/json",
            },
        )
        _json_response = GuardrailsAIResponse(**response.json())  # type: ignore
        if _json_response.get("validationPassed") is False:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Violated guardrail policy",
                    "guardrails_ai_response": _json_response,
                },
            )
        return _json_response

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        # cache: DualCache,
        data: dict,
        call_type: Literal[
            "completion",
            "text_completion",
            "embeddings",
            "image_generation",
            "moderation",
            "audio_transcription",
            "pass_through_endpoint",
            "rerank"
        ],
    ) -> Optional[Union[Exception, str, dict]]:
        """
        Runs before the LLM API call
        Runs on only Input
        Use this if you want to MODIFY the input
        """
        print("async_pre_call_hook")
        # In this guardrail, if a user inputs `litellm` we will mask it and then send it to the LLM
        _messages = data.get("messages")
        if _messages:
            for message in _messages:
                _content = message.get("content")
                if isinstance(_content, str):
                    # 呼叫 guardrails_ai 進行檢測
                    guardrails_response = await self.make_guardrails_ai_api_request(_content, data)
                    validated_output = guardrails_response.get("validatedOutput")
                    if validated_output:
                        message["content"] = validated_output

        return data

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: UserAPIKeyAuth,
        response,
    ):
        """
        Runs on response from LLM API call

        It can be used to reject a response
        """
        print("async_post_call_success_hook")
        print("response: ", response)
        if not isinstance(response, litellm.ModelResponse):
            return

        response_str: str = get_content_from_model_response(response)
        if response_str is not None and len(response_str) > 0:
            await self.make_guardrails_ai_api_request(
                llm_output=response_str, request_data=data
            )

            add_guardrail_to_applied_guardrails_header(
                request_data=data, guardrail_name=self.guardrail_name
            )


        return response