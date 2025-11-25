import json
import os
from qcloud_cos import CosConfig, CosS3Client

from apis.ql_api import QLApi
from config import COS_STS_ENV_KEY


def get_cos_sts() -> dict:
    """
    从 QLApi 动态获取 COS_STS 并解析为 dict.

    期望 QL 环境变量 COS_STS 的值为 JSON 字符串，形如：
    {
      "tmpSecretId": "...",
      "tmpSecretKey": "...",
      "sessionToken": "...",
      "expiredTime": "...",
      "bucketName": "chuan-ins2-cos-1258038542",
      "region": "ap-guangzhou",
      "uploadPath": "prod/chuanplus-order/h5-app/",
      "uploadUrl": "https://chuan-ins2-cos-1258038542.cos.ap-guangzhou.myqcloud.com",
      ...
    }
    """
    ql_api = QLApi()
    env = ql_api.get_env(COS_STS_ENV_KEY)

    if not isinstance(env, dict):
        raise RuntimeError(f"QLApi.get_env({COS_STS_ENV_KEY!r}) 返回格式异常: {type(env)}")

    value = env.get("value")
    if not value:
        raise RuntimeError(f"环境变量 {COS_STS_ENV_KEY} 未设置或 value 为空")

    try:
        sts = json.loads(value)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{COS_STS_ENV_KEY} JSON 解析失败: {e}")

    required_keys = [
        "tmpSecretId",
        "tmpSecretKey",
        "sessionToken",
        "bucketName",
        "region",
        "uploadPath",
        "uploadUrl",
    ]
    for k in required_keys:
        if k not in sts:
            raise RuntimeError(f"{COS_STS_ENV_KEY} 缺少必要字段: {k}")

    return sts


def get_cos_client(sts: dict = None) -> CosS3Client:
    """
    基于 STS 构造 COS 客户端。
    sts 可从外部传入以避免重复获取；不传则内部获取一次。
    """
    if sts is None:
        sts = get_cos_sts()

    config = CosConfig(
        Region=sts["region"],
        SecretId=sts["tmpSecretId"],
        SecretKey=sts["tmpSecretKey"],
        Token=sts["sessionToken"],
        Scheme="https",
    )
    client = CosS3Client(config)
    return client


def build_cos_key(fingerprint: str, file_name: str, sts: dict = None) -> str:
    """
    基于 fingerprint + 文件名生成稳定的 COS Key。
    uploadPath 从 sts["uploadPath"] 中获取。
    """
    if sts is None:
        sts = get_cos_sts()

    _, ext = os.path.splitext(file_name)
    base = fingerprint
    if ext:
        base = f"{fingerprint}{ext}"

    upload_path = sts["uploadPath"]
    if not upload_path.endswith("/"):
        upload_path += "/"

    return upload_path + base


def build_file_url(cos_key: str, sts: dict = None) -> str:
    """
    生成最终访问 URL：uploadUrl + cos_key
    """
    if sts is None:
        sts = get_cos_sts()

    upload_url = sts["uploadUrl"]
    return upload_url.rstrip("/") + "/" + cos_key.lstrip("/")
