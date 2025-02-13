# used for /metrics endpoint on EZLLM gateway
#### What this does ####
#    On success, log events to Prometheus
from typing import Optional, Union, Any

from litellm import CustomLogger
from litellm.types.utils import ModelResponse, EmbeddingResponse, ImageResponse, StandardLoggingPayload
from prometheus_client import Counter, Gauge, Histogram
from datetime import datetime, timedelta


LATENCY_BUCKETS = (
    0.005,
    0.00625,
    0.0125,
    0.025,
    0.05,
    0.1,
    0.5,
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    3.5,
    4.0,
    4.5,
    5.0,
    5.5,
    6.0,
    6.5,
    7.0,
    7.5,
    8.0,
    8.5,
    9.0,
    9.5,
    10.0,
    15.0,
    20.0,
    25.0,
    30.0,
    60.0,
    120.0,
    180.0,
    240.0,
    300.0,
    float("inf"),
)

class PrometheusLogger(CustomLogger):
    def __init__(self, routing_configs: dict, user_configs: dict):
        self.routing_configs = routing_configs
        self.user_configs = user_configs
        # 創建一個 dict 來保留 user_configs 的映射 (key: user_id --> value: user_profile)
        self.user_profiles = {}

        for user_token, user_profile in user_configs.items():
            self.user_profiles[user_profile['id']] = user_profile

        # Counter for total_output_tokens
        self.counter_tokens = Counter(
            "ezllm:tokens_total",
            "Total number of input + output tokens from LLM requests",
            labelnames=["model", "project", "org", "user"],
        )

        self.counter_input_tokens = Counter(
            "ezllm:input_tokens_total",
            "Total number of input tokens from LLM requests",
            labelnames=["model", "project", "org", "user"],
        )

        self.counter_output_tokens = Counter(
            "ezllm:output_tokens_total",
            "Total number of output tokens from LLM requests",
            labelnames=["model", "project", "org", "user"],
        ) 

        self.counter_proxy_requests_failed = Counter(
            name="ezllm:proxy_requests_failed_total",
            documentation="Total number of failed responses from proxy - the client did not get a success response from litellm proxy",
            labelnames=["model", "project", "org", "user", "status_code"],
        )

        self.counter_proxy_requests_success = Counter(
            name="ezllm:proxy_requests_success_total",
            documentation="Total number of requests made to the proxy server - track number of client side requests",
            labelnames=["model", "project", "org", "user"],
        )


        # request latency metrics
        self.histogram_total_e2e_time_request = Histogram(
            "ezllm:total_e2e_time_request_seconds",
            "Total latency (seconds) for a request to LiteLLM",
            labelnames=["model", "project", "org", "user"],
            buckets=LATENCY_BUCKETS,
        )

        self.histogram_llm_e2e_time_request = Histogram(
            "ezllm:llm_e2e_time_request_seconds",
            "Total latency (seconds) for a models LLM API call",
            labelnames=["model", "project", "org", "user"],
            buckets=LATENCY_BUCKETS,
        )

        self.histogram_time_to_first_token = Histogram(
            "ezllm:time_to_first_token_seconds",
            "Time to first token for a models LLM API call",
            labelnames=["model", "project", "org", "user"],
            buckets=LATENCY_BUCKETS,
        )
        

        self.histogram_overhead_latency = Histogram(
            "ezllm:compute_overhead_latency_secondss",
            "Latency overhead (milliseconds) added by LiteLLM processing",
            labelnames=["model", "project", "org", "user"],
            buckets=LATENCY_BUCKETS,
        )

    def _increment_token_metrics(
        self,
        standard_logging_payload: StandardLoggingPayload,
        user_id: Optional[str],
        project: Optional[str],
        org: Optional[str],
        model: Optional[str],
    ):        # token metrics
        self.counter_tokens.labels(
            model=model,
            project=project,
            org=org,
            user=user_id
        ).inc(standard_logging_payload["total_tokens"])

        self.counter_input_tokens.labels(
            model=model,
            project=project,
            org=org,
            user=user_id
        ).inc(standard_logging_payload["prompt_tokens"])

        self.counter_output_tokens.labels(
            model=model,
            project=project,
            org=org,
            user=user_id
        ).inc(standard_logging_payload["completion_tokens"])


    def _set_latency_metrics(
        self,
        kwargs: dict,
        model: Optional[str],
        user_id: Optional[str],
        project: Optional[str],
        org: Optional[str],
    ):
        # latency metrics
        end_time: datetime = kwargs.get("end_time") or datetime.now()
        start_time: Optional[datetime] = kwargs.get("start_time")
        api_call_start_time = kwargs.get("api_call_start_time", None)
        completion_start_time = kwargs.get("completion_start_time", None)

        if (
            completion_start_time is not None
            and isinstance(completion_start_time, datetime)
            and kwargs.get("stream", False) is True  # only emit for streaming requests
        ):
            time_to_first_token_seconds = (
                completion_start_time - api_call_start_time
            ).total_seconds()

            self.histogram_time_to_first_token.labels(
                model=model,
                project=project,
                org=org,
                user=user_id,
            ).observe(time_to_first_token_seconds)
        else:
            print("Time to first token metric not emitted, stream option in model_parameters is not True")

        if api_call_start_time is not None and isinstance(api_call_start_time, datetime):
            api_call_total_time: timedelta = end_time - api_call_start_time
            api_call_total_time_seconds = api_call_total_time.total_seconds()

            self.histogram_llm_e2e_time_request.labels(               
                model=model,
                project=project,
                org=org,
                user=user_id,).observe(api_call_total_time_seconds)
            
            if start_time is not None and isinstance(start_time, datetime):
                before_api_overhead: timedelta = api_call_start_time - start_time
                before_api_overhead_seconds = before_api_overhead.total_seconds()

                self.histogram_overhead_latency.labels(
                    model=model,
                    project=project,
                    org=org,
                    user=user_id,
                ).observe(before_api_overhead_seconds)
                # print(f"Overhead latency before API call: {before_api_overhead_seconds} seconds")

        # Overhead after API call (assuming end_time is request end time)
        if end_time is not None and api_call_start_time is not None:
            api_call_end_time = kwargs.get("api_call_end_time", end_time)  # Ensure we have an end time for the API call
            if isinstance(api_call_end_time, datetime):
                after_api_overhead: timedelta = end_time - api_call_end_time
                after_api_overhead_seconds = after_api_overhead.total_seconds()

                self.histogram_overhead_latency.labels(
                    model=model,
                    project=project,
                    org=org,
                    user=user_id,
                ).observe(after_api_overhead_seconds)

                # print(f"Overhead latency after API call: {after_api_overhead_seconds} seconds")

        # total request latency
        if start_time is not None and isinstance(start_time, datetime):
            total_time: timedelta = end_time - start_time
            total_time_seconds = total_time.total_seconds()

            self.histogram_total_e2e_time_request.labels(    
                model=model,
                project=project,
                org=org,
                user=user_id,           
            ).observe(total_time_seconds)


    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        print(f"Success API Call")


    def log_pre_api_call(self, model, messages, kwargs): 
        print(f"Pre-API Call")
    
    def log_post_api_call(self, kwargs, response_obj, start_time, end_time): 
        print(f"Post-API Call")


    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        print(f"Failure API Call")
        try:
            model = kwargs.get("model", "")
            user_api_key = kwargs.get("user_token","")
            user_configs = self.user_configs[user_api_key]

            self.counter_proxy_requests_failed.labels(
                model=model,
                project=user_configs.get("project", "default"),
                org=user_configs.get("org", "default"),
                user=user_configs.get("id", "default"),
                status_code=response_obj
            ).inc()

            # print(f"On Failure")
        except Exception as e:
            print(f"Error in log_failure_event: {e}")
            raise e


    #### ASYNC #### - for acompletion/aembeddings

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        print(f"On Async Success")
        try:
            # unpack kwargs
            standard_logging_payload: Optional[StandardLoggingPayload] = kwargs.get(
                "standard_logging_object"
            )

            if standard_logging_payload is None or not isinstance(
                standard_logging_payload, dict
            ):
                raise ValueError(
                    f"standard_logging_object is required, got={standard_logging_payload}"
                )

            model = kwargs.get("model", "")
            user_id = kwargs.get("user","")
            user_profile = self.user_profiles[user_id]

            # input, output, total token metrics
            self._increment_token_metrics(
                standard_logging_payload=standard_logging_payload,
                user_id=user_id,
                project=user_profile.get("project", "default"),
                org=user_profile.get("org", "default"),
                model=model,
            )

            self.counter_proxy_requests_success.labels(
                model=model,
                project=user_profile.get("project", "default"),
                org=user_profile.get("org", "default"),
                user=user_id,
            ).inc()

            # set latency metrics
            self._set_latency_metrics(
                kwargs=kwargs,
                model=model,
                user_id=user_id,
                project=user_profile.get("project", "default"),
                org=user_profile.get("org", "default"),
            )
        except Exception as e:
            print(f"Error in log_failure_event: {e}")
            raise e


    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        print(f"On Async Failure")
      