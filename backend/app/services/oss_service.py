from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import oss2

from app.core.config import Settings


class OssService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        """
        功能:
            判断 OSS 所需配置是否完整，避免运行时才暴露缺失配置。
        参数:
            无。
        返回:
            bool: 配置完整返回 True，否则返回 False。
        关键流程:
            1) 检查 AccessKey、Bucket、Endpoint、Bucket 域名是否为空。
            2) 全部有值时返回 True。
        异常处理:
            无显式异常，统一通过布尔值表达状态。
        """
        return all(
            [
                self.settings.oss_access_key_id,
                self.settings.oss_access_key_secret,
                self.settings.oss_bucket_name,
                self.settings.oss_endpoint,
                self.settings.oss_bucket_domain,
            ]
        )

    def upload_image(self, image_bytes: bytes, filename: str) -> tuple[str, str]:
        """
        功能:
            将图片二进制上传到阿里云 OSS，并返回对象 key 与可访问 URL。
        参数:
            image_bytes: 图片二进制内容，必填。
            filename: 原始文件名，用于推断扩展名，必填。
        返回:
            tuple[str, str]: (object_key, object_url)。
        关键流程:
            1) 校验 OSS 配置是否完整；
            2) 生成按日期分层的对象路径与唯一文件名；
            3) 调用 OSS SDK 上传二进制；
            4) 拼接公开访问 URL 返回。
        异常处理:
            当配置不完整或上传失败时抛出 ValueError/RuntimeError。
        """
        if not self.is_configured():
            raise ValueError("OSS 配置不完整，请先检查 .env 中 OSS_* 变量。")

        ext = Path(filename).suffix.lower() or ".jpg"
        now = datetime.now(timezone.utc)
        date_path = now.strftime("%Y/%m/%d")
        object_key = (
            f"{self.settings.oss_object_prefix.strip('/')}/{date_path}/"
            f"{uuid4().hex}{ext}"
        )

        auth = oss2.Auth(
            self.settings.oss_access_key_id,
            self.settings.oss_access_key_secret,
        )
        bucket = oss2.Bucket(
            auth=auth,
            endpoint=self.settings.oss_endpoint,
            bucket_name=self.settings.oss_bucket_name,
        )

        result = bucket.put_object(object_key, image_bytes)
        if result.status not in (200, 201):
            raise RuntimeError(f"OSS 上传失败，状态码: {result.status}")

        object_url = (
            f"{self.settings.oss_bucket_domain.rstrip('/')}/{object_key.lstrip('/')}"
        )
        return object_key, object_url
