"""
配置模块测试
"""

import pytest
import os
from pathlib import Path
from src.core.config import ConfigManager, get_config


class TestConfigManager:
    """ConfigManager 测试类"""

    def test_get_simple_key(self, tmp_path):
        """测试获取简单配置键"""
        # 创建临时配置目录
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # 创建 settings.yaml
        settings_file = config_dir / "settings.yaml"
        settings_file.write_text(
            """
app:
  name: "test-app"
  version: "1.0.0"
""",
            encoding="utf-8",
        )

        # 创建 ConfigManager 实例
        manager = ConfigManager(config_dir=str(config_dir))

        assert manager.get("app.name") == "test-app"
        assert manager.get("app.version") == "1.0.0"

    def test_get_nested_key(self, tmp_path):
        """测试获取嵌套配置键"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        settings_file = config_dir / "settings.yaml"
        settings_file.write_text(
            """
rag:
  retriever:
    top_k: 4
    score_threshold: 0.7
""",
            encoding="utf-8",
        )

        manager = ConfigManager(config_dir=str(config_dir))

        assert manager.get("rag.retriever.top_k") == 4
        assert manager.get("rag.retriever.score_threshold") == 0.7

    def test_get_with_default(self, tmp_path):
        """测试获取不存在的键时返回默认值"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        settings_file = config_dir / "settings.yaml"
        settings_file.write_text("app: {}", encoding="utf-8")

        manager = ConfigManager(config_dir=str(config_dir))

        assert manager.get("nonexistent.key", "default") == "default"
        assert manager.get("app.missing", 42) == 42

    def test_update_config(self, tmp_path):
        """测试更新配置"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        settings_file = config_dir / "settings.yaml"
        settings_file.write_text("app: {}", encoding="utf-8")

        manager = ConfigManager(config_dir=str(config_dir))
        manager.update("app.name", "updated-app")

        assert manager.get("app.name") == "updated-app"

    def test_env_variable_substitution(self, tmp_path, monkeypatch):
        """测试环境变量替换"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        monkeypatch.setenv("TEST_VALUE", "from-env")

        settings_file = config_dir / "settings.yaml"
        settings_file.write_text(
            """
test:
  value: "${TEST_VALUE}"
""",
            encoding="utf-8",
        )

        manager = ConfigManager(config_dir=str(config_dir))

        assert manager.get("test.value") == "from-env"

    def test_env_variable_with_default(self, tmp_path, monkeypatch):
        """测试带默认值的环境变量替换"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # 不设置环境变量
        monkeypatch.delenv("UNSET_VAR", raising=False)

        settings_file = config_dir / "settings.yaml"
        settings_file.write_text(
            """
test:
  value: "${UNSET_VAR:-fallback-value}"
""",
            encoding="utf-8",
        )

        manager = ConfigManager(config_dir=str(config_dir))

        assert manager.get("test.value") == "fallback-value"

    def test_get_model_config(self, tmp_path):
        """测试获取模型配置"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # 创建 settings.yaml
        settings_file = config_dir / "settings.yaml"
        settings_file.write_text("{}", encoding="utf-8")

        # 创建 models.yaml
        models_file = config_dir / "models.yaml"
        models_file.write_text(
            """
local_models:
  test_model:
    name: "test-model"
    provider: "ollama"
defaults:
  local_model: "test_model"
""",
            encoding="utf-8",
        )

        manager = ConfigManager(config_dir=str(config_dir))

        config = manager.get_model_config("local")
        assert config.get("name") == "test-model"
        assert config.get("provider") == "ollama"


class TestGetConfigFunction:
    """get_config 便捷函数测试"""

    def test_get_config_returns_default_for_missing_key(self):
        """测试 get_config 对缺失键返回默认值"""
        # 使用项目的实际配置
        result = get_config("nonexistent.key.12345", "default-value")
        assert result == "default-value"

    def test_get_config_with_numeric_type(self):
        """测试 get_config 对数字的处理"""
        # rag.retriever.top_k 应该是整数
        result = get_config("rag.retriever.top_k", 10)
        assert isinstance(result, int)
