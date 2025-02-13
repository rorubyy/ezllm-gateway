import yaml
from functools import lru_cache
from utils.model_config import ModelConfig
from utils.user_config import UserConfig

class ConfigLoader:
    @lru_cache()
    def load_configs(self):
        """Load all necessary configurations from files."""
        mc = ModelConfig()
        routing_configs = mc.load_config("config/routing_configs.yaml")

        uc = UserConfig()
        user_configs = uc.load_config("config/user_configs.yaml")

        return routing_configs, user_configs

config_loader = ConfigLoader()
