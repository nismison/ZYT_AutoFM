import base64
import json
import random
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from urllib.parse import unquote

# 写死的密钥
AES_KEY = "e373d090928170eb"

# 固定参数
FIXED_OR = 2  # 时间可靠性

# 坐标范围
COORD_RANGE = {
    "lat_min": 22.763168,
    "lat_max": 22.764769,
    "lon_min": 108.430403,
    "lon_max": 108.431633
}


def generate_random_coordinates():
    """
    在指定范围内生成随机坐标
    """
    lat = round(random.uniform(COORD_RANGE["lat_min"], COORD_RANGE["lat_max"]), 6)
    lon = round(random.uniform(COORD_RANGE["lon_min"], COORD_RANGE["lon_max"]), 6)

    return {
        "c": "GCJ-02",
        "la": lat,
        "lo": lon,
        "n": ""
    }


def decrypt_with_string_key(encrypted_b64, key_str):
    """
    使用字符串直接作为密钥进行解密
    """
    try:
        # 密钥就是UTF-8字符串
        key_bytes = key_str.encode('utf-8')
        print(f"密钥字符串: '{key_str}'")
        print(f"密钥字节长度: {len(key_bytes)}")

        # Base64解码
        encrypted_b64 = unquote(encrypted_b64)
        encrypted_data = base64.b64decode(encrypted_b64)
        print(f"密文长度: {len(encrypted_data)} 字节")

        # AES-128-ECB解密
        cipher = AES.new(key_bytes, AES.MODE_ECB)
        decrypted_data = cipher.decrypt(encrypted_data)
        print(f"解密后数据(hex): {decrypted_data[:32].hex()}...")

        # 去除PKCS5填充
        unpadded_data = unpad(decrypted_data, AES.block_size)
        print(f"去除填充后长度: {len(unpadded_data)} 字节")

        # 转换为字符串
        json_str = unpadded_data.decode('utf-8')
        print(f"解密后的JSON: {json_str}")

        # 解析JSON
        data_dict = json.loads(json_str)
        return data_dict

    except Exception as e:
        print(f"解密失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_watermark_data(ot, s, n, use_random_coords=True):
    """
    创建水印数据
    :param use_random_coords: 是否使用随机坐标，False则使用固定坐标
    """
    if use_random_coords:
        geo_data = generate_random_coordinates()
        # print(f"生成的随机坐标 - 纬度: {geo_data['la']}, 经度: {geo_data['lo']}")
    else:
        # 使用固定坐标（可选）
        geo_data = {
            "c": "GCJ-02",
            "la": 22.764439,
            "lo": 108.432947,
            "n": ""
        }

    data = {
        "ot": int(ot),  # 确保是整数
        "or": FIXED_OR,
        "s": int(s),  # 确保是整数
        "n": str(n),  # 确保是字符串
        "g": geo_data
    }
    return data


def encrypt_watermark(data_dict):
    """
    加密水印数据 - 使用与解密时完全相同的格式
    """
    try:
        key_bytes = AES_KEY.encode('utf-8')

        # 确保数据格式与解密结果完全一致
        formatted_data = {
            "g": {
                "c": str(data_dict["g"]["c"]),
                "la": float(data_dict["g"]["la"]),  # 明确转换为浮点数
                "lo": float(data_dict["g"]["lo"]),  # 明确转换为浮点数
                "n": str(data_dict["g"]["n"])
            },
            "n": str(data_dict["n"]),
            "or": int(data_dict["or"]),
            "ot": int(data_dict["ot"]),
            "s": int(data_dict["s"])
        }

        # 使用完全相同的JSON序列化参数
        json_str = json.dumps(
            formatted_data,
            ensure_ascii=False,
            separators=(',', ':'),  # 无空格
            sort_keys=True  # 固定字段顺序
        )

        # print(f"加密使用的JSON: {json_str}")
        # print(f"JSON字节长度: {len(json_str.encode('utf-8'))}")

        # PKCS5填充
        padded_data = pad(json_str.encode('utf-8'), AES.block_size)

        # AES-128-ECB加密
        cipher = AES.new(key_bytes, AES.MODE_ECB)
        encrypted_data = cipher.encrypt(padded_data)

        # Base64编码
        encrypted_b64 = base64.b64encode(encrypted_data).decode('utf-8')
        # print(f"生成的密文: {encrypted_b64}")

        return encrypted_b64

    except Exception as e:
        print(f"加密失败: {e}")
        import traceback
        traceback.print_exc()
        return None
