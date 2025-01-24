# used for /metrics endpoint on EZLLM gateway
#### What this does ####
#    On success, log events to Prometheus
from typing import Optional, Union, Any

from litellm import CustomLogger
from litellm.types.utils import ModelResponse, EmbeddingResponse, ImageResponse, StandardLoggingPayload
from prometheus_client import Counter, Gauge, Histogram

class PrometheusLogger(CustomLogger):
    def __init__(self, routing_configs: dict, user_configs: dict):
        self.routing_configs = routing_configs
        self.user_configs = user_configs
        # 創建一個 dict 來保留 user_configs 的映射 (key: user_id --> value: user_profile)
        self.user_profiles = {}

        for user_token, user_profile in user_configs.items():
            self.user_profiles[user_profile['id']] = user_profile

        self.ezllm_gateway_failed_requests = Counter(
            name="ezllm_gateway_failed_requests",
            documentation="Total number of failed responses from gateway - the client did not get a success response from ezllm gateway",
            labelnames=["model", "project", "org", "user"],
        )

        self.ezllm_gateway_success_responses = Counter(
            name="ezllm_gateway_success_responses",
            documentation="Total number of successful LLM API calls via ezllm gateway",
            labelnames=["model", "project", "org", "user"],
        )


    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        # unpack kwargs
        standard_logging_payload: Optional[StandardLoggingPayload] = kwargs.get("standard_logging_object")
        if standard_logging_payload is None or not isinstance(
            standard_logging_payload, dict
        ):
            raise ValueError(
                f"standard_logging_object is required, got={standard_logging_payload}"
            )

        output_tokens = standard_logging_payload["completion_tokens"]
        tokens_used = standard_logging_payload["total_tokens"]

        user_id = kwargs.get("user","")
        user_profile = self.user_profiles[user_id]

        model = kwargs.get("model", "")

        self.ezllm_gateway_success_responses.labels(
            model=model,
            project=user_profile.get("project", "default"),
            org=user_profile.get("org", "default"),
            user=user_id,
        ).inc()

        print(f"On Success")

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        print(f"On Failure")
