from typing import (Optional, Any, Dict)
import yaml
import os

class UserConfig:
    def __init__(self) -> None:
        self.config: Dict[str, Any] = {}

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
                "user_list": [],
            }

        return config

    
    def get_config(self, config_file_path: Optional[str] = None) -> dict:
        config = self._get_config_from_file(config_file_path=config_file_path)
        self.config = config
        return config


    def load_config(self, config_file_path: str) -> dict:
        config: dict = self.get_config(config_file_path=config_file_path)

        user_configs = {}
        user_list = config.get("user_list", None)
        if user_list:
            for user in user_list:
                user_configs[user['user_token']] = user['user_profile']
        return user_configs
