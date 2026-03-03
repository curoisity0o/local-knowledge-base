"""
配置管理模块
负责加载和管理应用程序配置
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._settings: Dict[str, Any] = {}
        self._models: Dict[str, Any] = {}
        
        # 确保配置目录存在
        self.config_dir.mkdir(exist_ok=True)
        
        # 加载配置
        self.load_configs()
        
        # 初始化路径
        self._init_paths()
    
    def load_configs(self) -> None:
        """加载所有配置文件"""
        try:
            # 加载 settings.yaml
            settings_path = self.config_dir / "settings.yaml"
            if settings_path.exists():
                with open(settings_path, 'r', encoding='utf-8') as f:
                    self._settings = yaml.safe_load(f)
                logger.info(f"Loaded settings from {settings_path}")
            else:
                logger.warning(f"Settings file not found: {settings_path}")
                self._settings = {}
            
            # 加载 models.yaml
            models_path = self.config_dir / "models.yaml"
            if models_path.exists():
                with open(models_path, 'r', encoding='utf-8') as f:
                    self._models = yaml.safe_load(f)
                logger.info(f"Loaded models from {models_path}")
            else:
                logger.warning(f"Models file not found: {models_path}")
                self._models = {}
                
        except Exception as e:
            logger.error(f"Error loading configs: {e}")
            raise
    
    def _init_paths(self) -> None:
        """初始化路径配置"""
        # 从环境变量或配置中获取基础路径
        base_data_dir = os.getenv("DATA_DIR", "./data")
        
        # 确保路径存在
        paths = {
            "data_dir": base_data_dir,
            "raw_docs": os.path.join(base_data_dir, "raw_docs"),
            "processed": os.path.join(base_data_dir, "processed"),
            "vector_store": os.path.join(base_data_dir, "vector_store"),
            "logs": "./logs"
        }
        
        # 创建目录
        for path in paths.values():
            Path(path).mkdir(parents=True, exist_ok=True)
        
        # 更新配置中的路径
        if "paths" not in self._settings:
            self._settings["paths"] = {}
        
        self._settings["paths"].update(paths)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点分隔的路径"""
        try:
            parts = key.split('.')
            value = self._settings
            
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            
            # 替换环境变量
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_key = value[2:-1]
                # 处理默认值语法 ${VAR:-default}
                if ":-" in env_key:
                    env_key, env_default = env_key.split(":-", 1)
                    env_value = os.getenv(env_key, env_default)
                else:
                    env_value = os.getenv(env_key)
                
                # 如果环境变量是数字，尝试转换
                if env_value and env_value.replace('.', '', 1).isdigit():
                    if '.' in env_value:
                        return float(env_value)
                    else:
                        return int(env_value)
                return env_value or default
            
            return value
        except (KeyError, AttributeError):
            return default
    
    def get_model_config(self, model_type: str, model_name: Optional[str] = None) -> Dict[str, Any]:
        """获取模型配置"""
        try:
            if model_type == "local":
                models = self._models.get("local_models", {})
                model_name = model_name or self._models.get("defaults", {}).get("local_model")
            elif model_type == "embedding":
                models = self._models.get("embedding_models", {})
                model_name = model_name or self._models.get("defaults", {}).get("embedding_model")
            elif model_type == "api":
                models = self._models.get("api_models", {})
                model_name = model_name or self._models.get("defaults", {}).get("api_model")
            else:
                models = {}
            
            if model_name and model_name in models:
                return models[model_name]
            
            # 如果没有找到具体模型，返回第一个模型
            if models:
                return next(iter(models.values()))
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting model config: {e}")
            return {}
    
    def get_recommended_combination(self, name: str) -> Dict[str, Any]:
        """获取推荐的模型组合"""
        combinations = self._models.get("recommended_combinations", [])
        for combo in combinations:
            if combo.get("name") == name:
                return combo
        return {}
    
    def get_hardware_aware_defaults(self, vram_gb: float) -> Dict[str, Any]:
        """根据显存大小获取硬件感知的默认配置"""
        defaults = self._models.get("hardware_aware_defaults", {})
        
        if vram_gb < 8:
            return defaults.get("low_vram", {})
        elif vram_gb <= 12:
            return defaults.get("medium_vram", {})
        else:
            return defaults.get("high_vram", {})
    
    @property
    def settings(self) -> Dict[str, Any]:
        """获取完整的 settings 配置"""
        return self._settings
    
    @property
    def models(self) -> Dict[str, Any]:
        """获取完整的 models 配置"""
        return self._models
    
    def update(self, key: str, value: Any) -> None:
        """更新配置值"""
        parts = key.split('.')
        config = self._settings
        
        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]
        
        config[parts[-1]] = value
        logger.info(f"Updated config: {key} = {value}")
    
    def save_settings(self) -> None:
        """保存 settings 到文件"""
        try:
            settings_path = self.config_dir / "settings.yaml"
            with open(settings_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._settings, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"Saved settings to {settings_path}")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

# 全局配置实例
config = ConfigManager()

# 便捷访问函数
def get_config(key: str, default: Any = None) -> Any:
    """便捷函数：获取配置值"""
    return config.get(key, default)

def get_model_config(model_type: str, model_name: Optional[str] = None) -> Dict[str, Any]:
    """便捷函数：获取模型配置"""
    return config.get_model_config(model_type, model_name)