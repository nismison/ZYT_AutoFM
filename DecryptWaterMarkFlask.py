import base64
import json
import random
import os
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from urllib.parse import unquote
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from gevent import pywsgi

app = Flask(__name__)

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

# 图片保存配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

# 确保上传目录存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上传大小为16MB

# HTML模板
IMAGE_GALLERY_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>图片库</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #2c3e50, #34495e);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        .gallery-section {
            padding: 30px;
        }
        .gallery-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }
        .gallery-header h2 {
            color: #2c3e50;
            font-size: 1.8em;
        }
        .image-count {
            background: #667eea;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
        }
        .image-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .image-card {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .image-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }
        .image-container {
            width: 100%;
            height: 200px;
            overflow: hidden;
            background: #f8f9fa;
        }
        .image-container img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s;
        }
        .image-card:hover .image-container img {
            transform: scale(1.05);
        }
        .image-info {
            padding: 15px;
        }
        .image-name {
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 8px;
            word-break: break-all;
        }
        .image-meta {
            font-size: 0.85em;
            color: #6c757d;
            line-height: 1.4;
            margin-bottom: 10px;
        }
        .delete-btn {
            background: #e74c3c;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            width: 100%;
            transition: background 0.3s;
        }
        .delete-btn:hover {
            background: #c0392b;
        }
        .delete-btn:disabled {
            background: #95a5a6;
            cursor: not-allowed;
        }
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 15px;
            margin-top: 30px;
        }
        .pagination-btn {
            padding: 10px 20px;
            border: 2px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s;
        }
        .pagination-btn:hover:not(:disabled) {
            background: #667eea;
            color: white;
        }
        .pagination-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .page-info {
            color: #6c757d;
            font-weight: bold;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
        }
        .empty-state i {
            font-size: 3em;
            margin-bottom: 15px;
            opacity: 0.5;
        }
        .message {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }
        .success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .fade-out {
            animation: fadeOut 0.5s ease-out forwards;
        }
        @keyframes fadeOut {
            from {
                opacity: 1;
                transform: scale(1);
            }
            to {
                opacity: 0;
                transform: scale(0.8);
            }
        }
        .bulk-delete-section {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
        }
        .bulk-delete-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s;
            box-shadow: 0 4px 6px rgba(220, 53, 69, 0.2);
        }
        .bulk-delete-btn:hover:not(:disabled) {
            background: #c82333;
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(220, 53, 69, 0.3);
        }
        .bulk-delete-btn:disabled {
            background: #6c757d;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📷 图片库</h1>
            <p>查看和管理已上传的图片</p>
        </div>

        {% if message %}
        <div class="message {{ message.type }}">
            {{ message.text }}
        </div>
        {% endif %}

        <div class="gallery-section">
            <div class="gallery-header">
                <h2>图片列表</h2>
                <div class="image-count">共 <span id="totalCount">{{ total_count }}</span> 张图片</div>
            </div>

            {% if images %}
            <div class="image-grid" id="imageGrid">
                {% for image in images %}
                <div class="image-card" id="image-{{ image.filename|replace('.', '_') }}">
                    <div class="image-container">
                        <img src="/images/{{ image.filename }}" alt="{{ image.original_name }}" 
                             onclick="window.open(this.src, '_blank')" style="cursor: pointer;">
                    </div>
                    <div class="image-info">
                        <div class="image-name" title="{{ image.original_name }}">
                            {{ image.original_name[:20] }}{% if image.original_name|length > 20 %}...{% endif %}
                        </div>
                        <div class="image-meta">
                            <div>ID: {{ image.file_id }}</div>
                            <div>大小: {{ image.size_mb }} MB</div>
                            <div>上传: {{ image.upload_time }}</div>
                        </div>
                        <button class="delete-btn" onclick="deleteImage(this, '{{ image.filename }}')">
                            🗑️ 删除
                        </button>
                    </div>
                </div>
                {% endfor %}
            </div>

            {% if total_pages > 1 %}
            <div class="pagination">
                <button class="pagination-btn" onclick="changePage({{ page - 1 }})" {% if page <= 1 %}disabled{% endif %}>
                    上一页
                </button>
                <span class="page-info">第 {{ page }} 页，共 {{ total_pages }} 页</span>
                <button class="pagination-btn" onclick="changePage({{ page + 1 }})" {% if page >= total_pages %}disabled{% endif %}>
                    下一页
                </button>
            </div>
            {% endif %}

            <!-- 新增：批量删除按钮 -->
            <div class="bulk-delete-section">
                <button class="bulk-delete-btn" onclick="deleteAllImagesOnPage()">
                    🗑️ 删除本页所有照片
                </button>
            </div>

            {% else %}
            <div class="empty-state" id="emptyState">
                <div>📁</div>
                <h3>暂无图片</h3>
                <p>通过API接口上传图片后即可在此查看</p>
            </div>
            {% endif %}
        </div>
    </div>

    <script>
        function changePage(newPage) {
            const url = new URL(window.location);
            url.searchParams.set('page', newPage);
            window.location = url.toString();
        }

        function deleteImage(button, filename) {
            // 禁用按钮防止重复点击
            button.disabled = true;
            button.textContent = '删除中...';

            fetch(`/delete_image/${filename}`, {
                method: 'DELETE',
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // 找到对应的图片卡片
                    const imageCard = document.getElementById(`image-${filename.replace(/\./g, '_')}`);
                    if (imageCard) {
                        imageCard.remove();
                        
                        // 更新图片计数
                        updateImageCount(-1);
                        
                        // 检查是否还有图片，如果没有则显示空状态
                        checkEmptyState();
                    }
                } else {
                    alert('删除失败: ' + data.error);
                    // 恢复按钮状态
                    button.disabled = false;
                    button.textContent = '🗑️ 删除';
                }
            })
            .catch(error => {
                alert('删除失败: ' + error);
                // 恢复按钮状态
                button.disabled = false;
                button.textContent = '🗑️ 删除';
            });
        }

        function deleteAllImagesOnPage() {
            // 获取当前页所有图片的文件名
            const imageCards = document.querySelectorAll('.image-card');
            if (imageCards.length === 0) {
                alert('当前页面没有图片可删除');
                return;
            }

            // 确认删除
            if (!confirm(`确定要删除本页的所有 ${imageCards.length} 张照片吗？此操作不可撤销！`)) {
                return;
            }

            const deleteButton = document.querySelector('.bulk-delete-btn');
            const originalText = deleteButton.textContent;
            deleteButton.disabled = true;
            deleteButton.textContent = `删除中... (0/${imageCards.length})`;

            const filenames = [];
            imageCards.forEach(card => {
                // 从卡片ID中提取文件名（去掉"image-"前缀并将下划线恢复为点）
                const id = card.id.replace('image-', '').replace(/_/g, '.');
                filenames.push(id);
            });

            let completedCount = 0;
            const deletePromises = filenames.map(filename => {
                return fetch(`/delete_image/${filename}`, {
                    method: 'DELETE',
                })
                .then(response => response.json())
                .then(data => {
                    completedCount++;
                    deleteButton.textContent = `删除中... (${completedCount}/${filenames.length})`;
                    return data;
                });
            });

            // 等待所有删除请求完成
            Promise.all(deletePromises)
                .then(results => {
                    // 检查是否有删除失败的情况
                    const failedDeletes = results.filter(result => result.status !== 'success');
                    if (failedDeletes.length > 0) {
                        alert(`有 ${failedDeletes.length} 张图片删除失败，页面将刷新`);
                    } else {
                        // 所有删除成功
                        deleteButton.textContent = '删除完成，刷新中...';
                    }
                    
                    // 无论成功与否，都刷新页面
                    setTimeout(() => {
                        location.reload();
                    }, 1000);
                })
                .catch(error => {
                    alert('批量删除过程中发生错误: ' + error);
                    deleteButton.disabled = false;
                    deleteButton.textContent = originalText;
                });
        }

        function updateImageCount(change) {
            const countElement = document.getElementById('totalCount');
            if (countElement) {
                let currentCount = parseInt(countElement.textContent);
                currentCount += change;
                countElement.textContent = currentCount;
                
                // 如果计数为0，更新标题的计数显示
                const imageCountElements = document.querySelectorAll('.image-count');
                imageCountElements.forEach(element => {
                    element.textContent = `共 ${currentCount} 张图片`;
                });
            }
        }

        function checkEmptyState() {
            const imageGrid = document.getElementById('imageGrid');
            const emptyState = document.getElementById('emptyState');
            const pagination = document.querySelector('.pagination');
            
            if (imageGrid && imageGrid.children.length === 0) {
                // 如果没有图片了，刷新页面
                if (!emptyState) {
                    location.reload()
                }
                // 隐藏分页
                if (pagination) {
                    pagination.style.display = 'none';
                }
            }
        }

        function createEmptyState() {
            const gallerySection = document.querySelector('.gallery-section');
            const emptyStateHTML = `
                <div class="empty-state" id="emptyState">
                    <div>📁</div>
                    <h3>暂无图片</h3>
                    <p>通过API接口上传图片后即可在此查看</p>
                </div>
            `;
            
            const imageGrid = document.getElementById('imageGrid');
            if (imageGrid) {
                imageGrid.style.display = 'none';
            }
            
            // 在图片网格位置插入空状态
            if (gallerySection) {
                const pagination = document.querySelector('.pagination');
                if (pagination) {
                    gallerySection.insertBefore(createElementFromHTML(emptyStateHTML), pagination);
                } else {
                    gallerySection.insertAdjacentHTML('beforeend', emptyStateHTML);
                }
            }
        }

        function createElementFromHTML(htmlString) {
            const div = document.createElement('div');
            div.innerHTML = htmlString.trim();
            return div.firstChild;
        }

        // 显示上传消息
        {% if message %}
        setTimeout(() => {
            const messageEl = document.querySelector('.message');
            if (messageEl) {
                messageEl.style.display = 'none';
            }
        }, 5000);
        {% endif %}
    </script>
</body>
</html>"""


def allowed_file(filename):
    """
    检查文件扩展名是否允许
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_by_id(file_id):
    """
    根据文件ID查找已存在的文件
    """
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if filename.endswith(f'_{file_id}'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                return filename
    return None


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


@app.route('/')
def image_gallery():
    """
    图片库首页 - 显示图片列表
    """
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)

        # 限制每页数量
        per_page = min(per_page, 50)

        # 获取消息参数
        message_text = request.args.get('message', '')
        message_type = request.args.get('message_type', '')

        # 获取所有图片文件
        all_images = []
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(file_path) and allowed_file(filename):
                file_stat = os.stat(file_path)

                # 解析文件名获取原始名称和文件ID
                parts = filename.split('_', 2)  # 分割时间戳和文件ID
                if len(parts) >= 3:
                    original_name = parts[2]
                    file_id = parts[1] if len(parts) > 1 else 'unknown'
                else:
                    original_name = filename
                    file_id = 'unknown'

                all_images.append({
                    'filename': filename,
                    'original_name': original_name,
                    'file_id': file_id,
                    'size': file_stat.st_size,
                    'size_mb': round(file_stat.st_size / (1024 * 1024), 2),
                    'upload_time': datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                })

        # 按上传时间倒序排列
        all_images.sort(key=lambda x: x['upload_time'], reverse=True)

        # 计算分页
        total_count = len(all_images)
        total_pages = (total_count + per_page - 1) // per_page
        start_index = (page - 1) * per_page
        end_index = start_index + per_page

        # 获取当前页的数据
        current_page_images = all_images[start_index:end_index]

        # 准备消息
        message = None
        if message_text and message_type:
            message = {'text': message_text, 'type': message_type}

        return render_template_string(IMAGE_GALLERY_HTML,
                                      images=current_page_images,
                                      total_count=total_count,
                                      page=page,
                                      total_pages=total_pages,
                                      message=message
                                      )

    except Exception as e:
        print(f"图片库页面错误: {e}")
        return f"页面加载失败: {str(e)}", 500


@app.route('/upload_image', methods=['POST'])
def upload_image():
    """
    图片上传接口 - 仅支持JSON API方式
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': '请求体必须为JSON格式'}), 400

        # 验证必需参数
        required_fields = ['file_id', 'file_data', 'filename']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必需参数: {field}'}), 400

        file_id = data['file_id'].strip()
        file_data = data['file_data']  # base64编码的文件数据
        filename = data['filename']

        if not file_id:
            return jsonify({'error': '文件ID不能为空'}), 400

        # 检查文件类型
        # if not allowed_file(filename):
        #     return jsonify({
        #         'error': f'不支持的文件类型: {filename}',
        #         'allowed_extensions': list(ALLOWED_EXTENSIONS)
        #     }), 400

        # 检查是否已存在相同ID的文件
        existing_file = get_file_by_id(file_id)
        if existing_file:
            return jsonify({
                'status': 'success',
                'message': f'文件ID "{file_id}" 已存在，无需重复上传',
                'existing_file': existing_file
            })

        # 生成安全的文件名：时间戳_文件ID_原始文件名
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_filename = f"{timestamp}_{file_id}_{filename}"

        # 解码base64文件数据并保存
        try:
            # 移除base64前缀（如果有）
            if ',' in file_data:
                file_data = file_data.split(',')[1]

            file_bytes = base64.b64decode(file_data)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)

            with open(file_path, 'wb') as f:
                f.write(file_bytes)
        except Exception as e:
            return jsonify({'error': f'文件数据解码失败: {str(e)}'}), 400

        # 获取文件信息
        file_size = os.path.getsize(file_path)

        return jsonify({
            'status': 'success',
            'message': '文件上传成功',
            'file_info': {
                'original_filename': filename,
                'saved_filename': safe_filename,
                'file_id': file_id,
                'file_size': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'file_path': f'/images/{safe_filename}',
                'upload_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        })

    except Exception as e:
        print(f"文件上传错误: {e}")
        return jsonify({'error': f'文件上传失败: {str(e)}'}), 500


@app.route('/images/<filename>')
def get_image(filename):
    """
    获取图片接口 - 在浏览器中查看图片
    """
    try:
        # 安全检查：防止目录遍历攻击
        if '..' in filename or filename.startswith('/'):
            return "无效的文件名", 400

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # 检查文件是否存在
        if not os.path.isfile(file_path):
            return "文件不存在", 404

        # 返回图片文件
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    except Exception as e:
        print(f"获取图片错误: {e}")
        return f"获取图片失败: {str(e)}", 500


@app.route('/delete_image/<filename>', methods=['DELETE'])
def delete_image(filename):
    """
    删除图片接口
    """
    try:
        # 安全检查：防止目录遍历攻击
        if '..' in filename or filename.startswith('/'):
            return jsonify({'error': '无效的文件名'}), 400

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # 检查文件是否存在
        if not os.path.isfile(file_path):
            return jsonify({'error': '文件不存在'}), 404

        # 删除文件
        os.remove(file_path)

        return jsonify({
            'status': 'success',
            'message': f'文件删除成功'
        })

    except Exception as e:
        print(f"删除图片错误: {e}")
        return jsonify({'error': f'删除图片失败: {str(e)}'}), 500


@app.route('/encrypt', methods=['POST'])
def encrypt_endpoint():
    """
    加密接口 - 只需要接收n、ot、s三个参数
    """
    try:
        data = request.get_json()

        # 验证必需参数
        required_fields = ['ot', 's', 'n']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必需参数: {field}'}), 400

        # 是否使用随机坐标（默认为True）
        use_random_coords = data.get('use_random_coords', True)

        # 创建水印数据
        watermark_data = create_watermark_data(
            ot=data['ot'],
            s=data['s'],
            n=data['n'],
            use_random_coords=use_random_coords
        )

        # print(f"准备加密的数据: {watermark_data}")

        # 加密数据
        encrypted = encrypt_watermark(watermark_data)

        if encrypted:
            return jsonify({
                'status': 'success',
                'encrypted_data': encrypted,
                'original_data': watermark_data,
                'coordinates_info': {
                    'latitude': watermark_data['g']['la'],
                    'longitude': watermark_data['g']['lo'],
                    'is_random': use_random_coords
                }
            })
        else:
            return jsonify({'error': '加密失败'}), 500

    except Exception as e:
        print(f"加密接口错误: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@app.route('/encrypt_fixed', methods=['POST'])
def encrypt_fixed_endpoint():
    """
    加密接口 - 使用固定坐标
    """
    try:
        data = request.get_json()

        # 验证必需参数
        required_fields = ['ot', 's', 'n']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必需参数: {field}'}), 400

        # 创建水印数据（使用固定坐标）
        watermark_data = create_watermark_data(
            ot=data['ot'],
            s=data['s'],
            n=data['n'],
            use_random_coords=False  # 使用固定坐标
        )

        # print(f"准备加密的数据(固定坐标): {watermark_data}")

        # 加密数据
        encrypted = encrypt_watermark(watermark_data)

        if encrypted:
            return jsonify({
                'status': 'success',
                'encrypted_data': encrypted,
                'original_data': watermark_data,
                'coordinates_info': {
                    'latitude': watermark_data['g']['la'],
                    'longitude': watermark_data['g']['lo'],
                    'is_random': False
                }
            })
        else:
            return jsonify({'error': '加密失败'}), 500

    except Exception as e:
        print(f"加密接口错误: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@app.route('/decrypt', methods=['POST'])
def decrypt_endpoint():
    """
    解密接口 - 只需要接收加密数据，密钥写死
    """
    try:
        data = request.get_json()

        # 验证必需参数
        if 'encrypted_data' not in data:
            return jsonify({'error': '缺少必需参数: encrypted_data'}), 400

        # 解密数据（使用写死的密钥）
        result = decrypt_with_string_key(data['encrypted_data'], AES_KEY)

        if result:
            return jsonify({
                'status': 'success',
                'decrypted_data': result
            })
        else:
            return jsonify({'error': '解密失败'}), 400

    except Exception as e:
        print(f"解密接口错误: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@app.route('/get_coord_range', methods=['GET'])
def get_coord_range():
    """
    获取坐标范围信息
    """
    return jsonify({
        'status': 'success',
        'coordinate_range': COORD_RANGE,
        'description': '随机坐标生成范围'
    })


if __name__ == '__main__':
    server = pywsgi.WSGIServer(('127.0.0.1', 5000), app)
    server.serve_forever()
