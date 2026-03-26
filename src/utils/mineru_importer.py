"""
MinerU 文档导入工具
用于从 MinerU 输出目录导入文档到知识库系统
"""

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class MinerUImporter:
    """MinerU 文档导入器"""

    def __init__(self):
        # 获取项目根目录
        self.project_root = Path(__file__).parent.parent.parent
        self.raw_docs_dir = self.project_root / "data" / "raw_docs"
        self.images_dir = self.project_root / "data" / "images"
        self.metadata_dir = self.project_root / "data" / "metadata"

        # 确保目录存在
        self.raw_docs_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def import_from_mineru(self, mineru_dir: str) -> Dict[str, Any]:
        """
        从 MinerU 输出目录导入文档

        Args:
            mineru_dir: MinerU 输出目录路径

        Returns:
            导入结果字典
        """
        mineru_path = Path(mineru_dir)

        # 验证目录存在
        if not mineru_path.exists():
            raise FileNotFoundError(f"MinerU 目录不存在: {mineru_dir}")

        # 查找 full.md
        full_md_path = mineru_path / "full.md"
        if not full_md_path.exists():
            raise FileNotFoundError(f"未找到 full.md 文件: {mineru_dir}")

        # 查找 images 目录
        images_src_dir = mineru_path / "images"
        has_images = images_src_dir.exists() and images_src_dir.is_dir()

        logger.info(f"开始导入 MinerU 文档: {mineru_dir}")

        # 1. 读取 full.md 内容
        with open(full_md_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 2. 提取元数据（标题、作者、摘要）
        metadata = self._extract_metadata(content)

        # 3. 生成友好文件名
        filename = self._generate_filename(metadata)

        # 4. 复制文档到 raw_docs
        dest_md_path = self.raw_docs_dir / f"{filename}.md"
        with open(dest_md_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"文档已复制: {dest_md_path}")

        # 5. 复制 images 目录
        images_dest_dir = None
        if has_images:
            images_dest_dir = self.images_dir / f"{filename}_images"
            if images_dest_dir.exists():
                shutil.rmtree(images_dest_dir)
            shutil.copytree(images_src_dir, images_dest_dir)
            logger.info(f"图片已复制: {images_dest_dir}")

        # 6. 保存元数据文件（过滤掉空值）
        metadata_path = self.metadata_dir / f"{filename}.meta.json"

        # 过滤掉空的元数据
        metadata = {
            k: v
            for k, v in metadata.items()
            if v not in ([], "", None, {}) and not (isinstance(v, list) and len(v) == 0)
        }

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"元数据已保存: {metadata_path}")

        return {
            "success": True,
            "filename": f"{filename}.md",
            "title": metadata.get("title", ""),
            "authors": metadata.get("authors", []),
            "has_images": has_images,
            "images_dir": str(images_dest_dir) if images_dest_dir else None,
            "metadata_path": str(metadata_path),
        }

    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """从 full.md 内容中提取元数据"""
        metadata = {
            "title": "",
            "authors": [],
            "abstract": "",
            "document_type": "paper",
            "field": "",
            "keywords": [],
        }

        lines = content.split("\n")

        # 提取标题（第一个 # 标题）
        for _i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("# ") and not line.startswith("##"):
                metadata["title"] = line[2:].strip()
                break

        # 提取作者（紧跟标题后，以名字*或名字结尾的行）
        author_lines = []
        for j in range(1, min(25, len(lines))):
            line = lines[j].strip()

            # 跳过空行
            if not line:
                continue

            # 遇到 # 开头的标题（说明进入下一部分）
            if line.startswith("#"):
                break

            # 作者行特征：
            # - 包含 * 或 † 符号（脚注标记）
            # - 或只包含名字（2-4个单词）
            if "*" in line or "†" in line:
                # 处理逗号分隔的多作者行（如 "Ling Yue1†, Nithin Somasekharan1†, ...")
                if "," in line:
                    # 按逗号分割，提取每个作者
                    for part in line.split(","):
                        # 移除脚注标记（*, †, ‡, 数字等）
                        author_name = re.sub(r"[*†‡§\d]+", "", part).strip()
                        # 清理多余的空白和符号
                        author_name = re.sub(r"\s+", " ", author_name).strip()
                        # 过滤：需要至少2个字符，且不能太长（人名通常<30字符）
                        if author_name and 2 <= len(author_name) <= 30:
                            author_lines.append(author_name)
                else:
                    # 单作者行，移除脚注标记
                    author_name = re.sub(r"[*†‡§\d]+", "", line).strip()
                    author_name = re.sub(r"\s+", " ", author_name).strip()
                    if author_name and 2 <= len(author_name) <= 30:
                        author_lines.append(author_name)
            elif re.match(r"^[A-Z][a-z]+(\s+[A-Z][a-z]+){0,3}$", line):
                # 纯名字（2-4个单词，首字母大写）
                if len(line) < 40:
                    author_lines.append(line)

        # 去重并限制数量
        metadata["authors"] = list(dict.fromkeys(author_lines))[:5]

        # 提取摘要（找 Abstract 部分）
        abstract_lines = []
        in_abstract = False
        for line in lines:
            line_stripped = line.strip()

            if line_stripped.lower().startswith("# abstract"):
                in_abstract = True
                continue

            if in_abstract:
                if line_stripped.startswith("# ") and not line_stripped.startswith(
                    "##"
                ):
                    # 遇到下一个标题，摘要结束
                    break
                if line_stripped:
                    abstract_lines.append(line_stripped)

        if abstract_lines:
            metadata["abstract"] = " ".join(abstract_lines)

        # 提取关键词（如果有）
        keywords = self._extract_keywords(content)
        if keywords:
            metadata["keywords"] = keywords

        return metadata

    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        keywords = []

        # 常见关键词模式
        patterns = [
            r"[Kk]eywords?:\s*([^\n]+)",
            r"[Tt]ags?:\s*([^\n]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # 分割逗号分隔的关键词
                kw_list = re.split(r"[,;]", match)
                for kw in kw_list:
                    kw = kw.strip()
                    if kw and len(kw) > 2:
                        keywords.append(kw)

        return keywords[:5]  # 最多5个

    def _generate_filename(self, metadata: Dict[str, Any]) -> str:
        """根据元数据生成友好文件名"""
        title = metadata.get("title", "")

        if not title:
            # 如果没有标题，使用时间戳
            from datetime import datetime

            return f"document_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 从标题提取关键词生成简短文件名
        # 移除常见前缀
        title = re.sub(r"^(The\s+|A\s+|An\s+)", "", title, flags=re.IGNORECASE)

        # 只保留前3-4个重要单词
        words = re.findall(r"[A-Za-z]+", title)
        important_words = [w for w in words if len(w) > 2][:4]

        if important_words:
            filename = "_".join(important_words)
        else:
            # 降级使用原始标题
            filename = title[:50].replace(" ", "_")

        # 清理非法文件名字符
        filename = re.sub(r'[<>:"/\\|?*]', "", filename)

        return filename


def import_mineru_document(mineru_dir: str) -> Dict[str, Any]:
    """导入 MinerU 文档的便捷函数"""
    importer = MinerUImporter()
    return importer.import_from_mineru(mineru_dir)
