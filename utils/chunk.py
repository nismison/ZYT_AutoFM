"""
分片操作工具：保存分片、合并、清理缓存
"""
import os


def save_chunk(upload_id: str, part_index: int, chunk_tmp_path: str):
    pass  # 已在路由中实现


def merge_chunks(upload_id: str, output_path: str, total_parts: int):
    """
    合并所有上传的分片

    :param upload_id: 当前上传会话ID
    :param output_path: 输出合并后的文件路径
    :param total_parts: 分片总数
    """
    part_dir = os.path.join("/tmp/uploads", upload_id)
    with open(output_path, "wb") as output:
        for i in range(1, total_parts + 1):
            chunk_path = os.path.join(part_dir, f"part_{i}")
            with open(chunk_path, "rb") as f:
                output.write(f.read())


def cleanup_chunks(upload_id: str):
    """删除指定会话ID的分片临时目录"""
    part_dir = os.path.join("/tmp/uploads", upload_id)
    if os.path.exists(part_dir):
        for name in os.listdir(part_dir):
            os.remove(os.path.join(part_dir, name))
        os.rmdir(part_dir)
