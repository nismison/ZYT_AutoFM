import json
import os
import time
import hmac
import hashlib
import uuid
import datetime
import logging
from urllib.parse import quote
from config import FM_BASE_URL, HEADERS_BASE

logger = logging.getLogger(__name__)


class OSSClient:
    def __init__(self, session, token):
        self.session = session
        self.token = token
        self.oss = {}
        self.base = FM_BASE_URL
        self.get_oss_policy()

    def get_oss_policy(self):
        logger.info("初始化 COS 仓库...")
        payload = {"directory": "h5-app", "businessType": "video", "durationSeconds": 1800}
        headers = HEADERS_BASE.copy()
        headers["Cookie"] = f"token={self.token}; x-tenant=10010"
        url = f"{self.base}/file/sts/sts-token"

        for i in range(3):
            resp = self.session.post(url, json=payload, headers=headers)
            if resp.status_code == 200 and str(resp.json().get('code')) == "200":
                data = resp.json()['data']
                self.oss = data
                print(f">>>>>>>>>>self.oss: {self.oss}<<<<<<<<<<")
                logger.info("COS 仓库初始化完成")
                return data
            time.sleep(1)
        raise RuntimeError("获取 COS 临时凭证失败")

    def upload(self, file_path):
        if not self.oss:
            self.get_oss_policy()

        file_uuid = str(uuid.uuid4())
        file_ext = file_path.split(".")[-1]
        today = datetime.datetime.today()
        upload_key = f"{self.oss['uploadPath']}{today.year}/{today.month:02d}/{today.day:02d}/{file_uuid}.{file_ext}"

        # === 构造签名 ===
        secret_id = self.oss['tmpSecretId']
        secret_key = self.oss['tmpSecretKey']
        session_token = self.oss['sessionToken']
        host = self.oss['uploadUrl'].replace("https://", "")

        # 使用当前时间和过期时间
        start_time = int(time.time())
        end_time = int(self.oss['expiredTime'])
        sign_time = f"{start_time};{end_time}"
        key_time = sign_time  # key-time 和 sign-time 相同

        # 计算 SignKey
        sign_key = hmac.new(secret_key.encode('utf-8'), sign_time.encode('utf-8'), hashlib.sha1).hexdigest()

        # 获取文件大小
        file_size = os.path.getsize(file_path)

        # 构造 HttpString (注意：方法名必须小写，header参数必须按字母序排列)
        http_method = "put"
        http_uri = f"/{upload_key}"
        http_parameters = ""  # URL 参数为空
        http_headers = f"host={host}"  # 只包含 host header
        http_string = f"{http_method}\n{http_uri}\n{http_parameters}\n{http_headers}\n"

        # 计算 HttpString 的 SHA1
        http_string_sha1 = hashlib.sha1(http_string.encode('utf-8')).hexdigest()

        # 构造 StringToSign
        string_to_sign = f"sha1\n{sign_time}\n{http_string_sha1}\n"

        # 计算 Signature
        signature = hmac.new(sign_key.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).hexdigest()

        # 构造 Authorization
        authorization = (
            f"q-sign-algorithm=sha1"
            f"&q-ak={secret_id}"
            f"&q-sign-time={sign_time}"
            f"&q-key-time={key_time}"
            f"&q-header-list=host"
            f"&q-url-param-list="
            f"&q-signature={signature}"
        )

        # 根据文件扩展名设置 Content-Type
        content_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'mp4': 'video/mp4',
            'avi': 'video/x-msvideo',
            'mov': 'video/quicktime',
        }
        content_type = content_type_map.get(file_ext.lower(), 'application/octet-stream')

        headers = {
            "Authorization": authorization,
            "x-cos-security-token": session_token,
            "Host": host,
            "Content-Type": content_type,
            "Content-Length": str(file_size)
        }

        upload_url = f"{self.oss['uploadUrl']}/{upload_key}"

        logger.info(f"开始上传文件: {file_path}")
        logger.info(f"上传URL: {upload_url}")
        logger.debug(f"Authorization: {authorization}")

        try:
            with open(file_path, "rb") as f:
                r = self.session.put(upload_url, data=f, headers=headers)

            if r.status_code in [200, 204]:
                logger.info(f"文件上传完成: {upload_url}")
                return upload_url
            else:
                logger.error(f"上传失败：{r.status_code}")
                logger.error(f"响应内容: {r.text}")
                # 如果是 403，可能是凭证过期，尝试刷新
                if r.status_code == 403:
                    logger.info("尝试刷新 COS 凭证...")
                    self.get_oss_policy()
                return self.upload(file_path)
        except Exception as e:
            logger.error(f"上传异常: {str(e)}")
            raise