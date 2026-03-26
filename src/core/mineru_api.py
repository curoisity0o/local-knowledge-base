"""
MinerU API 客户端模块
用于调用MinerU在线API将PDF转换为Markdown
"""

import logging
import time
from typing import Any, Dict, Optional

import requests

from .config import get_config

logger = logging.getLogger(__name__)


class MinerUAPIError(Exception):
    """MinerU API错误异常"""

    pass


class MinerUAPI:
    """MinerU API客户端"""

    BASE_URL = "https://mineru.net/api/v4"

    def __init__(self, api_token: Optional[str] = None):
        """初始化API客户端

        Args:
            api_token: MinerU API token，如果为None则从配置读取
        """
        self.api_token = api_token or get_config("mineru.api_token", "")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }

    def is_configured(self) -> bool:
        """检查是否已配置API Token"""
        return bool(self.api_token)

    def validate_token(self) -> Dict[str, Any]:
        """验证Token是否有效

        通过尝试调用转换接口来验证token

        Returns:
            Dict包含验证结果
        """
        if not self.api_token:
            return {"valid": False, "message": "API Token未配置"}

        try:
            # 尝试调用转换接口（使用示例URL）
            # 通过401响应来判断token是否无效
            data = {
                "url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf",
                "model_version": "vlm",
            }

            response = requests.post(
                f"{self.BASE_URL}/extract/task",
                headers=self.headers,
                json=data,
                timeout=15,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    # 成功提交，说明token有效
                    return {"valid": True, "message": "Token有效，可以正常调用API"}
                else:
                    # 业务错误，可能是参数问题，但token有效
                    return {
                        "valid": True,
                        "message": f"Token有效，API业务响应: {result.get('msg', '未知')}",
                    }
            elif response.status_code == 401:
                return {"valid": False, "message": "Token无效或已过期 (401)"}
            else:
                return {
                    "valid": False,
                    "message": f"API返回错误: {response.status_code}",
                }

        except requests.exceptions.RequestException as e:
            return {"valid": False, "message": f"网络错误: {str(e)}"}

    def upload_file(self, file_path: str) -> Optional[str]:
        """上传文件到MinerU（通过URL方式）

        由于MinerU API需要URL，我们使用文件上传接口

        Args:
            file_path: 本地PDF文件路径

        Returns:
            文件的CDN URL或None
        """
        # 方案1: 使用临时文件托管服务
        # 这里先检查是否有本地文件服务器配置

        # 方案2: 直接返回本地文件路径（如果API支持）
        # MinerU API需要公网URL，这里我们返回None表示需要特殊处理
        return None

    def convert_pdf(
        self,
        pdf_url: str,
        is_ocr: bool = False,
        enable_formula: bool = True,
        enable_table: bool = True,
        language: str = "ch",
        model_version: str = "vlm",
    ) -> Dict[str, Any]:
        """提交PDF转换任务

        Args:
            pdf_url: PDF文件的公网URL
            is_ocr: 是否启用OCR
            enable_formula: 是否启用公式识别
            enable_table: 是否启用表格识别
            language: 文档语言
            model_version: 模型版本

        Returns:
            包含task_id的响应
        """
        if not self.api_token:
            raise MinerUAPIError("API Token未配置")

        data = {
            "url": pdf_url,
            "is_ocr": is_ocr,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "language": language,
            "model_version": model_version,
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/extract/task",
                headers=self.headers,
                json=data,
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    return {
                        "success": True,
                        "task_id": result["data"]["task_id"],
                        "message": "任务提交成功",
                    }
                else:
                    raise MinerUAPIError(
                        f"任务提交失败: {result.get('msg', '未知错误')}"
                    )
            elif response.status_code == 401:
                raise MinerUAPIError("API Token无效或已过期")
            else:
                raise MinerUAPIError(f"API返回错误: {response.status_code}")

        except requests.exceptions.RequestException as e:
            raise MinerUAPIError(f"网络请求失败: {str(e)}")

    def get_result(self, task_id: str) -> Dict[str, Any]:
        """获取转换结果

        Args:
            task_id: 任务ID

        Returns:
            转换结果
        """
        if not self.api_token:
            raise MinerUAPIError("API Token未配置")

        try:
            response = requests.get(
                f"{self.BASE_URL}/extract/result/{task_id}",
                headers=self.headers,
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    data = result["data"]
                    status = data.get("status")

                    if status == "success":
                        return {
                            "success": True,
                            "status": "success",
                            "markdown": data.get("markdown_content", ""),
                            "message": "转换成功",
                        }
                    elif status == "pending" or status == "processing":
                        return {
                            "success": False,
                            "status": status,
                            "message": "任务处理中",
                        }
                    else:
                        return {
                            "success": False,
                            "status": status,
                            "message": f"任务失败: {data.get('message', '未知错误')}",
                        }
                else:
                    raise MinerUAPIError(
                        f"获取结果失败: {result.get('msg', '未知错误')}"
                    )
            elif response.status_code == 401:
                raise MinerUAPIError("API Token无效或已过期")
            else:
                raise MinerUAPIError(f"API返回错误: {response.status_code}")

        except requests.exceptions.RequestException as e:
            raise MinerUAPIError(f"网络请求失败: {str(e)}")

    def convert_pdf_with_wait(
        self,
        pdf_url: str,
        max_wait_seconds: int = 300,
        poll_interval: int = 5,
        **kwargs,
    ) -> str:
        """提交任务并等待结果

        Args:
            pdf_url: PDF文件的公网URL
            max_wait_seconds: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）
            **kwargs: 其他参数传递给convert_pdf

        Returns:
            转换后的Markdown内容
        """
        # 提交任务
        result = self.convert_pdf(pdf_url, **kwargs)
        task_id = result["task_id"]

        # 轮询等待结果
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            result = self.get_result(task_id)

            if result["success"]:
                return result["markdown"]
            elif result["status"] == "failed":
                raise MinerUAPIError(f"转换失败: {result['message']}")

            # 等待后继续轮询
            time.sleep(poll_interval)

        raise MinerUAPIError("转换超时")


def get_mineru_client() -> MinerUAPI:
    """获取MinerU API客户端实例"""
    return MinerUAPI()


def validate_mineru_token(api_token: str) -> Dict[str, Any]:
    """验证Token有效性（便捷函数）

    Args:
        api_token: 要验证的Token

    Returns:
        验证结果Dict
    """
    client = MinerUAPI(api_token)
    return client.validate_token()
