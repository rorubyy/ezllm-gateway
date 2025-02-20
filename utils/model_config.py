from typing import (Optional, Any, Dict, List)
import yaml
import os
from my_guardrails.init_guardrails import init_guardrails

class ModelConfig:
    def __init__(self) -> None:
        self.config: Dict[str, Any] = {}


    def _check_for_os_environ_vars(self, config: dict, depth: int = 0, max_depth: int = 10) -> dict:
        """
        Check for os.environ/ variables in the config and replace them with the actual values.
        Includes a depth limit to prevent infinite recursion.

        Args:
            config (dict): The configuration dictionary to process.
            depth (int): Current recursion depth.
            max_depth (int): Maximum allowed recursion depth.

        Returns:
            dict: Processed configuration dictionary.
        """
        for key, value in config.items():
            if isinstance(value, dict):
                config[key] = self._check_for_os_environ_vars(
                    config=value, depth=depth + 1, max_depth=max_depth
                )
            elif isinstance(value, list):
                config[key] = [
                    self._check_for_os_environ_vars(
                        config=item, depth=depth + 1, max_depth=max_depth
                    ) if isinstance(item, dict) else item for item in value
                ]
            elif isinstance(value, str) and value.startswith("os.environ/"):
                env_var_name = value[len("os.environ/"):]
                config[key] = os.environ.get(env_var_name, "")
        return config

    def _get_config_from_file(
        self, config_file_path: Optional[str] = None
    ) -> dict:
        """
        Given a config file path, load the config from the file.
        Args:
            config_file_path (str): path to the config file
        Returns:
            dict: config
        """
        # Load existing config
        ## Yaml
        if os.path.exists(f"{config_file_path}"):
            with open(f"{config_file_path}", "r") as config_file:
                config = yaml.safe_load(config_file)
        elif config_file_path is not None:
            raise Exception(f"Config file not found: {config_file_path}")
        else:
            config = {
                "model_list": [],
                "general_settings": {},
                "router_settings": {},
                "litellm_settings": {},
            }

        return config

    # TODO : Add more checks for os.environ/ variables in the config and replace them with the actual values.
    
    def get_config(self, config_file_path: Optional[str] = None) -> dict:
        config = self._get_config_from_file(config_file_path=config_file_path)
        self.config = config
        return config

    def load_config(self, config_file_path: str) -> dict:
        config: dict = self.get_config(config_file_path=config_file_path)

        model_configs = {}
        model_list = config.get("model_list", None)
        if model_list:
            for model in model_list:
                model_configs[model['model_name']] = model['litellm_params']
        model_configs = self._check_for_os_environ_vars(model_configs)

        # Guardrail settings
        guardrail_configs = {}
        guardrails: Optional[List[Dict]] = None

        if config is not None:
            guardrails = config.get("guardrails", None)
        if guardrails:
            init_guardrails(
                all_guardrails=guardrails, config_file_path=config_file_path
            )
            for guardrail in guardrails:
                guardrail_configs[guardrail['guardrail_name']] = guardrail['litellm_params']
        
        routing_configs = {
            "models": model_configs,
            "guardrails": guardrail_configs
        }
        
        return routing_configs
