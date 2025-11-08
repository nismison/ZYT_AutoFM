import io
import json
import os
import re
import sys
import types
from email.utils import formatdate
from urllib.parse import parse_qs

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


class _Headers:
    def __init__(self, data=None):
        self._store = {}
        if data:
            for k, v in data.items():
                self._store[k] = v

    def get(self, key, default=None):
        return self._store.get(key, default)

    def __getitem__(self, key):
        return self._store[key]

    def __setitem__(self, key, value):
        self._store[key] = value

    def __contains__(self, key):
        return key in self._store

    def items(self):
        return self._store.items()

    def __iter__(self):
        return iter(self._store.items())


class _RequestObject:
    def __init__(self):
        self.reset()

    def reset(self):
        self.method = "GET"
        self.path = "/"
        self.headers = _Headers()
        self.args = {}
        self.form = {}
        self.files = _FilesDict()
        self.cookies = {}
        self.content_type = None
        self._data = b""

    def get_data(self, as_text=False):
        if as_text:
            return self._data.decode("utf-8") if isinstance(self._data, (bytes, bytearray)) else str(self._data)
        return self._data

    def get_json(self, silent=False):
        try:
            data = self.get_data(as_text=True)
            if not data:
                return None
            return json.loads(data)
        except Exception:
            if silent:
                return None
            raise


class _FilesDict(dict):
    def get(self, key, default=None):
        items = super().get(key)
        if not items:
            return default
        return items[0]

    def getlist(self, key):
        return super().get(key, [])


class _FileStorage:
    def __init__(self, stream, filename):
        self.stream = stream
        self.filename = filename

    def save(self, dst):
        self.stream.seek(0)
        with open(dst, "wb") as fh:
            fh.write(self.stream.read())
        self.stream.seek(0)


class Response:
    def __init__(self, data=b"", status=200, headers=None, mimetype=None):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._data = data or b""
        self.status_code = status
        self.headers = {}
        if headers:
            for k, v in headers.items():
                self.headers[k] = v
        self.content_type = mimetype or self.headers.get("Content-Type") or "text/html; charset=utf-8"
        self.headers.setdefault("Content-Type", self.content_type)
        self.status = f"{self.status_code} OK"
        self.direct_passthrough = False

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        self.set_data(value)

    def get_data(self, as_text=False):
        if as_text:
            return self._data.decode("utf-8")
        return self._data

    def set_data(self, value):
        if isinstance(value, str):
            value = value.encode("utf-8")
        self._data = value

    def get_json(self):
        try:
            return json.loads(self.get_data(as_text=True))
        except Exception:
            return None


def jsonify(*args, **kwargs):
    payload = args[0] if args else kwargs
    return Response(json.dumps(payload, ensure_ascii=False), status=200, headers={"Content-Type": "application/json"})


def make_response(*args):
    if not args:
        return Response()
    if len(args) == 1:
        rv = args[0]
        if isinstance(rv, Response):
            return rv
        if isinstance(rv, tuple):
            response = make_response(rv[0])
            if len(rv) > 1:
                response.status_code = rv[1]
                response.status = f"{response.status_code} OK"
            if len(rv) > 2 and rv[2]:
                response.headers.update(rv[2])
            return response
        return Response(rv)
    response = make_response(args[0])
    if len(args) >= 2:
        response.status_code = args[1]
        response.status = f"{response.status_code} OK"
    if len(args) == 3 and args[2]:
        response.headers.update(args[2])
    return response


def send_file(path, mimetype=None, as_attachment=False, download_name=None):
    with open(path, "rb") as fh:
        data = fh.read()
    headers = {}
    if download_name:
        headers["Content-Disposition"] = f"inline; filename={download_name}"
    return Response(data, headers=headers, mimetype=mimetype or "application/octet-stream")


def send_from_directory(directory, filename, as_attachment=False):
    return send_file(os.path.join(directory, filename), mimetype="application/octet-stream", download_name=filename)


def render_template(template_name, **context):
    path = os.path.join(TEMPLATES_DIR, template_name)
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _compile_rule(rule):
    pattern = "^"
    converters = []

    def repl(match):
        type_name, name = match.group(1), match.group(2)
        converters.append((name, type_name or "string"))
        if type_name == "int":
            return fr"(?P<{name}>\d+)"
        if type_name == "path":
            return fr"(?P<{name}>.*)"
        return fr"(?P<{name}>[^/]+)"

    pattern += re.sub(r"<(?:(\w+):)?(\w+)>", repl, rule)
    pattern += "$"
    return re.compile(pattern), converters


def _convert(type_name, value):
    if type_name == "int":
        return int(value)
    return value


class Blueprint:
    def __init__(self, name, import_name, url_prefix=None):
        self.name = name
        self.import_name = import_name
        self.url_prefix = url_prefix or ""
        self._routes = []

    def route(self, rule, methods=None, defaults=None):
        methods = methods or ["GET"]

        def decorator(func):
            self._routes.append((self.url_prefix + rule, methods, func, defaults or {}))
            return func

        return decorator


class Flask:
    def __init__(self, import_name):
        self.import_name = import_name
        self._routes = []
        self._before_request_funcs = []
        self._after_request_funcs = []
        self.config = {}

    def route(self, rule, methods=None, defaults=None):
        methods = methods or ["GET"]

        def decorator(func):
            self._add_route(rule, methods, func, defaults or {})
            return func

        return decorator

    def _add_route(self, rule, methods, func, defaults):
        pattern, converters = _compile_rule(rule)
        self._routes.append((pattern, converters, methods, func, defaults))

    def before_request(self, func):
        self._before_request_funcs.append(func)
        return func

    def after_request(self, func):
        self._after_request_funcs.append(func)
        return func

    def register_blueprint(self, blueprint):
        for rule, methods, func, defaults in blueprint._routes:
            self._add_route(rule, methods, func, defaults)

    def test_client(self):
        return _TestClient(self)

    def run(self, *args, **kwargs):
        raise RuntimeError("Stub Flask app cannot run server")

    def _handle_request(self, method, path, data=None, json_data=None, query=None, content_type=None, headers=None):
        query_params = {}
        if "?" in path:
            path, raw_qs = path.split("?", 1)
            query_params.update({k: v[0] for k, v in parse_qs(raw_qs, keep_blank_values=True).items()})
        if query:
            for k, v in query.items():
                query_params[k] = str(v)

        request_context.reset()
        request_context.method = method
        request_context.path = path
        request_context.headers = _Headers(headers or {})
        request_context.args = query_params
        request_context.cookies = {}
        request_context.content_type = content_type

        form = {}
        files = _FilesDict()

        body_data = b""

        if json_data is not None:
            body_data = json.dumps(json_data).encode("utf-8")
            request_context.content_type = "application/json"
        elif isinstance(data, dict) and (content_type or "") .startswith("multipart/form-data"):
            for key, value in data.items():
                if isinstance(value, tuple):
                    stream, filename = value
                    files.setdefault(key, []).append(_FileStorage(stream, filename))
                else:
                    form[key] = value
        elif isinstance(data, dict):
            form = data
        elif data is not None:
            body_data = data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")

        request_context.form = form
        request_context.files = files
        request_context._data = body_data

        response = None
        for func in self._before_request_funcs:
            rv = func()
            if rv is not None:
                response = make_response(rv)
                break

        if response is None:
            for pattern, converters, methods_allowed, func, defaults in self._routes:
                if method not in methods_allowed:
                    continue
                match = pattern.match(path)
                if not match:
                    continue
                kwargs = defaults.copy()
                for name, type_name in converters:
                    kwargs[name] = _convert(type_name, match.group(name))
                rv = func(**kwargs)
                response = make_response(rv) if not isinstance(rv, Response) else rv
                break
            else:
                response = Response("Not Found", status=404)

        for func in self._after_request_funcs:
            response = func(response)

        return response


class _TestClient:
    def __init__(self, app):
        self.app = app

    def open(self, path, method="GET", data=None, json=None, query_string=None, content_type=None, headers=None):
        response = self.app._handle_request(method, path, data=data, json_data=json, query=query_string, content_type=content_type, headers=headers)
        return response

    def get(self, path, **kwargs):
        return self.open(path, method="GET", **kwargs)

    def post(self, path, **kwargs):
        return self.open(path, method="POST", **kwargs)

    def put(self, path, **kwargs):
        return self.open(path, method="PUT", **kwargs)

    def delete(self, path, **kwargs):
        return self.open(path, method="DELETE", **kwargs)


request_context = _RequestObject()


def get_request():
    return request_context


flask_module = types.ModuleType("flask")
flask_module.Flask = Flask
flask_module.Blueprint = Blueprint
flask_module.Response = Response
flask_module.jsonify = jsonify
flask_module.make_response = make_response
flask_module.send_file = send_file
flask_module.send_from_directory = send_from_directory
flask_module.render_template = render_template
flask_module.request = request_context

sys.modules.setdefault("flask", flask_module)


flask_cors_module = types.ModuleType("flask_cors")
flask_cors_module.CORS = lambda *args, **kwargs: None
sys.modules.setdefault("flask_cors", flask_cors_module)


peewee_module = types.ModuleType("peewee")


class _DummyField:
    def __init__(self, *args, **kwargs):
        pass


class _DummyModel:
    class Meta:
        database = None


DummyDoesNotExist = type("DoesNotExist", (Exception,), {})
_DummyModel.DoesNotExist = DummyDoesNotExist


class _DummySqliteDatabase:
    def __init__(self, *args, **kwargs):
        self._closed = True

    def is_closed(self):
        return self._closed

    def connect(self, reuse_if_open=False):
        self._closed = False

    def execute_sql(self, *args, **kwargs):
        return None

    def create_tables(self, *args, **kwargs):
        return None


peewee_module.SqliteDatabase = _DummySqliteDatabase
peewee_module.Model = _DummyModel
peewee_module.CharField = _DummyField
peewee_module.IntegerField = _DummyField
peewee_module.BooleanField = _DummyField
peewee_module.DateTimeField = _DummyField
peewee_module.AutoField = _DummyField
peewee_module.DoesNotExist = DummyDoesNotExist

sys.modules.setdefault("peewee", peewee_module)


werkzeug_module = types.ModuleType("werkzeug")
http_module = types.ModuleType("werkzeug.http")


def http_date(timestamp):
    return formatdate(timestamp, usegmt=True)


http_module.http_date = http_date
werkzeug_module.http = http_module
sys.modules.setdefault("werkzeug", werkzeug_module)
sys.modules.setdefault("werkzeug.http", http_module)

dotenv_module = types.ModuleType("dotenv")
dotenv_module.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_module)

requests_module = types.ModuleType("requests")


class RequestException(Exception):
    pass


def _requests_request(*args, **kwargs):
    raise RequestException("requests stub")


requests_module.RequestException = RequestException
requests_module.request = _requests_request
sys.modules.setdefault("requests", requests_module)

wxpusher_module = types.ModuleType("wxpusher")


class _WxPusher:
    @staticmethod
    def send_message(*args, **kwargs):
        return True


wxpusher_module.WxPusher = _WxPusher
sys.modules.setdefault("wxpusher", wxpusher_module)

pil_module = types.ModuleType("PIL")
pil_image_module = types.ModuleType("PIL.Image")
pil_image_draw_module = types.ModuleType("PIL.ImageDraw")
pil_image_font_module = types.ModuleType("PIL.ImageFont")


class _DummyImage:
    def __init__(self, width=100, height=100):
        self.width = width
        self.height = height

    def resize(self, size, *args, **kwargs):
        self.width, self.height = size
        return self

    def paste(self, *args, **kwargs):
        return None

    def rotate(self, *args, **kwargs):
        return self

    def crop(self, *args, **kwargs):
        return self

    def convert(self, *args, **kwargs):
        return self

    def save(self, *args, **kwargs):
        return None

    def close(self):
        return None


class _DummyDraw:
    def __init__(self, image):
        self._image = image

    def rectangle(self, *args, **kwargs):
        return None

    def ellipse(self, *args, **kwargs):
        return None

    def text(self, *args, **kwargs):
        return None


class _DummyFont:
    def __init__(self, *args, **kwargs):
        pass


def _image_new(mode, size, color=None):
    return _DummyImage(*size)


def _image_open(path):
    return _DummyImage()


pil_image_module.new = _image_new
pil_image_module.open = _image_open
pil_image_module.LANCZOS = 1
pil_image_draw_module.Draw = lambda image: _DummyDraw(image)
pil_image_font_module.truetype = lambda *args, **kwargs: _DummyFont()
pil_image_font_module.load_default = lambda: _DummyFont()

pil_module.Image = pil_image_module
pil_module.ImageDraw = pil_image_draw_module
pil_module.ImageFont = pil_image_font_module

sys.modules.setdefault("PIL", pil_module)
sys.modules.setdefault("PIL.Image", pil_image_module)
sys.modules.setdefault("PIL.ImageDraw", pil_image_draw_module)
sys.modules.setdefault("PIL.ImageFont", pil_image_font_module)

qrcode_module = types.ModuleType("qrcode")
qrcode_constants = types.ModuleType("qrcode.constants")


class _DummyQRCode:
    def __init__(self, *args, **kwargs):
        pass

    def add_data(self, data):
        return None

    def make(self, fit=True):
        return None

    def make_image(self, *args, **kwargs):
        return _DummyImage()


qrcode_constants.ERROR_CORRECT_L = 1
qrcode_module.QRCode = _DummyQRCode
qrcode_module.constants = qrcode_constants
qrcode_module.make = lambda *args, **kwargs: _DummyImage()

sys.modules.setdefault("qrcode", qrcode_module)
sys.modules.setdefault("qrcode.constants", qrcode_constants)

crypto_module = types.ModuleType("Crypto")
crypto_cipher_module = types.ModuleType("Crypto.Cipher")
crypto_util_module = types.ModuleType("Crypto.Util")
crypto_padding_module = types.ModuleType("Crypto.Util.Padding")


class _DummyAES:
    MODE_ECB = 1

    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def new(*args, **kwargs):
        return _DummyAES()

    def encrypt(self, data):
        return data

    def decrypt(self, data):
        return data


def _pad(data, block_size):
    return data


def _unpad(data, block_size):
    return data


crypto_cipher_module.AES = _DummyAES
crypto_padding_module.pad = _pad
crypto_padding_module.unpad = _unpad
crypto_util_module.Padding = crypto_padding_module
crypto_module.Cipher = crypto_cipher_module
crypto_module.Util = crypto_util_module

sys.modules.setdefault("Crypto", crypto_module)
sys.modules.setdefault("Crypto.Cipher", crypto_cipher_module)
sys.modules.setdefault("Crypto.Util", crypto_util_module)
sys.modules.setdefault("Crypto.Util.Padding", crypto_padding_module)

import pytest

from flask_server import create_app


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr("flask_server.init_database_connection", lambda: None)
    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def upload_record_stub(monkeypatch):
    records = []
    created = []

    class Field:
        def __init__(self, name):
            self.name = name

        def __eq__(self, other):
            return ("eq", self.name, other)

        def desc(self):
            return ("order_desc", self.name)

    class DummyRecord:
        def __init__(self, **attrs):
            self.saved = False
            for key, value in attrs.items():
                setattr(self, key, value)

        def save(self):
            self.saved = True

    class DummyQuery:
        def __init__(self, data, fields=None):
            self._data = list(data)
            self._fields = fields
            self._filtered = list(data)

        def where(self, condition):
            if isinstance(condition, tuple) and condition[0] == "eq":
                field, value = condition[1], condition[2]
                self._filtered = [r for r in self._filtered if getattr(r, field) == value]
            return self

        def order_by(self, *args, **kwargs):
            return self

        def paginate(self, page, size):
            start = (page - 1) * size
            end = start + size
            return self._filtered[start:end]

        def count(self):
            return len(self._filtered)

        def first(self):
            return self._filtered[0] if self._filtered else None

        def distinct(self):
            return self

        def tuples(self):
            if not self._fields:
                return []
            rows = []
            for record in self._filtered:
                row = []
                for field in self._fields:
                    if hasattr(field, "name"):
                        row.append(getattr(record, field.name))
                rows.append(tuple(row))
            unique = []
            for row in rows:
                if row not in unique:
                    unique.append(row)
            return unique

        def __iter__(self):
            return iter(self._filtered)

    class DummyUploadRecord:
        DoesNotExist = Exception
        favorite = Field("favorite")
        device_model = Field("device_model")
        etag = Field("etag")
        upload_time = Field("upload_time")

        @classmethod
        def select(cls, *fields):
            return DummyQuery(records, fields or None)

        @classmethod
        def get_by_id(cls, record_id):
            for record in records:
                if record.id == record_id:
                    return record
            raise cls.DoesNotExist()

        @classmethod
        def create(cls, **kwargs):
            created.append(kwargs)
            return kwargs

    monkeypatch.setattr("routes.gallery.UploadRecord", DummyUploadRecord)
    monkeypatch.setattr("routes.upload.UploadRecord", DummyUploadRecord)

    return {"records": records, "created": created, "Record": DummyRecord}


def test_proxy_success(client, monkeypatch):
    class DummyResponse:
        status_code = 200
        content = b"ok"
        headers = {"Content-Type": "text/plain"}

        def json(self):
            return {}

    captured = {}

    def fake_request(**kwargs):
        captured.update(kwargs)
        return DummyResponse()

    monkeypatch.setattr("routes.proxy.requests.request", fake_request)

    resp = client.get("/redirect/test")
    assert resp.status_code == 200
    assert resp.data == b"ok"
    assert captured["url"].endswith("/test")


def test_proxy_failure(client, monkeypatch):
    class DummyException(Exception):
        pass

    def fake_request(**kwargs):
        raise DummyException("boom")

    monkeypatch.setattr("routes.proxy.requests.request", fake_request)
    monkeypatch.setattr("routes.proxy.requests.RequestException", DummyException)

    resp = client.get("/redirect/test")
    assert resp.status_code == 502
    assert b"Upstream request failed" in resp.data


def test_serve_image_success(client, monkeypatch, tmp_path):
    gallery_dir = tmp_path / "gallery"
    cache_dir = tmp_path / "gallery_cache"
    watermark_dir = tmp_path / "watermark"
    for folder in (gallery_dir, cache_dir, watermark_dir):
        folder.mkdir()
    file_path = gallery_dir / "abc123_test.jpg"
    file_path.write_bytes(b"data")

    monkeypatch.setattr("routes.image.GALLERY_STORAGE_DIR", str(gallery_dir))
    monkeypatch.setattr("routes.image.GALLERY_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr("routes.image.WATERMARK_STORAGE_DIR", str(watermark_dir))

    resp = client.get("/api/image/gallery/abc123")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "public, max-age=2592000"


def test_serve_image_invalid_type(client):
    resp = client.get("/api/image/unknown/abc")
    assert resp.status_code == 400


def test_check_uploaded_found(client, upload_record_stub):
    record_cls = upload_record_stub["Record"]
    upload_record_stub["records"].append(record_cls(id=1, etag="etag1"))

    resp = client.get("/api/check_uploaded", query_string={"etag": "etag1"})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data == {"success": True, "uploaded": True}


def test_check_uploaded_missing_etag(client):
    resp = client.get("/api/check_uploaded")
    assert resp.status_code == 400


def test_check_uploaded_not_found(client, upload_record_stub):
    resp = client.get("/api/check_uploaded", query_string={"etag": "missing"})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data == {"success": True, "uploaded": False}


def test_upload_with_watermark_success(client, monkeypatch, tmp_path):
    output_dir = tmp_path / "watermark"
    output_dir.mkdir()

    def fake_add_watermark(original_image_path, **kwargs):
        with open(kwargs["output_path"], "wb") as fh:
            fh.write(b"processed")

    monkeypatch.setattr("routes.upload.WATERMARK_STORAGE_DIR", str(output_dir))
    monkeypatch.setattr("routes.upload.add_watermark_to_image", fake_add_watermark)
    monkeypatch.setattr("routes.upload.generate_random_suffix", lambda: "suffix")
    monkeypatch.setattr("routes.upload.get_image_url", lambda image_id, image_type: f"url:{image_id}:{image_type}")
    monkeypatch.setattr("routes.upload.random.randint", lambda a, b: 1)

    data = {
        "name": "Alice",
        "user_number": "001",
        "file": (io.BytesIO(b"image-data"), "test.jpg"),
    }
    resp = client.post("/upload_with_watermark", data=data, content_type="multipart/form-data")
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["success"] is True
    assert payload["count"] == 1
    assert payload["oss_urls"][0].startswith("url:")


def test_upload_with_watermark_missing_params(client):
    resp = client.post("/upload_with_watermark", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_upload_to_gallery_success(client, monkeypatch, upload_record_stub):
    created = upload_record_stub["created"]

    class DummyImmich:
        def upload_to_immich_file(self, path):
            assert os.path.exists(path)
            return "asset-1"

    monkeypatch.setattr("routes.upload.IMMICHApi", lambda: DummyImmich())

    data = {
        "etag": "etag2",
        "file": (io.BytesIO(b"content"), "photo.jpg"),
    }
    resp = client.post("/upload_to_gallery", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert created, "UploadRecord.create should be called"
    assert resp.get_json()["success"] is True


def test_upload_to_gallery_missing_params(client):
    resp = client.post("/upload_to_gallery", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_upload_to_gallery_failure(client, monkeypatch):
    class DummyImmich:
        def upload_to_immich_file(self, path):
            return None

    monkeypatch.setattr("routes.upload.IMMICHApi", lambda: DummyImmich())

    data = {
        "etag": "etag3",
        "file": (io.BytesIO(b"content"), "photo.jpg"),
    }
    resp = client.post("/upload_to_gallery", data=data, content_type="multipart/form-data")
    assert resp.status_code == 500


def test_toggle_favorite_success(client, upload_record_stub):
    record_cls = upload_record_stub["Record"]
    upload_record_stub["records"].append(
        record_cls(
            id=1,
            favorite=False,
            oss_url="u1",
            original_filename="a.jpg",
            device_model="DeviceA",
            upload_time="2024-01-01",
            file_size=10,
            etag="e1",
            width=100,
            height=200,
            thumb="t1",
        )
    )

    resp = client.post("/api/favorite/1")
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["success"] is True
    assert payload["favorite"] is True


def test_toggle_favorite_not_found(client, upload_record_stub):
    resp = client.post("/api/favorite/999")
    assert resp.status_code == 404


def _make_record(record_cls, **overrides):
    defaults = dict(
        oss_url="url",
        original_filename="name.jpg",
        device_model="Device",
        upload_time="2024-01-01",
        file_size=10,
        favorite=False,
        etag="etag",
        width=100,
        height=200,
        thumb="thumb",
    )
    defaults.update(overrides)
    return record_cls(**defaults)


def test_get_favorites(client, upload_record_stub):
    record_cls = upload_record_stub["Record"]
    upload_record_stub["records"].extend([
        _make_record(record_cls, id=1, favorite=True, device_model="DeviceA", etag="e1"),
        _make_record(record_cls, id=2, favorite=False, device_model="DeviceB", etag="e2"),
    ])

    resp = client.get("/api/favorites", query_string={"page": 1, "size": 10})
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["total"] == 1
    assert payload["data"]["records"][0]["favorite"] is True


def test_api_gallery_with_device_filter(client, upload_record_stub):
    record_cls = upload_record_stub["Record"]
    upload_record_stub["records"].extend([
        _make_record(record_cls, id=1, device_model="DeviceA", etag="e1"),
        _make_record(record_cls, id=2, device_model="DeviceB", etag="e2"),
    ])

    resp = client.get("/api/gallery", query_string={"device": "DeviceB"})
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["total"] == 1
    assert payload["data"]["records"][0]["device_model"] == "DeviceB"


def test_send_notify(client, monkeypatch):
    sent_messages = []

    class DummyNotify:
        def send(self, content):
            sent_messages.append(content)

    monkeypatch.setattr("routes.notify.notify", DummyNotify())

    resp = client.post("/send_notify", json={"content": "hello"})
    assert resp.status_code == 200
    assert sent_messages == ["hello"]


def test_send_notify_missing_content(client):
    resp = client.post("/send_notify", json={})
    assert resp.status_code == 400


def test_check_update_returns_latest(client, monkeypatch, tmp_path):
    apk_dir = tmp_path / "apks"
    apk_dir.mkdir()
    (apk_dir / "1.0.0.apk").write_bytes(b"a")
    (apk_dir / "2.0.0.apk").write_bytes(b"b")
    (apk_dir / "1.5.0.wgt").write_bytes(b"c")

    monkeypatch.setattr("routes.update.APK_DIR", str(apk_dir))

    resp = client.get("/api/check_update")
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["version"] == "2.0.0"
    assert payload["now_url"].endswith("2.0.0.apk")


def test_check_update_no_files(client, monkeypatch, tmp_path):
    apk_dir = tmp_path / "apks"
    apk_dir.mkdir()

    monkeypatch.setattr("routes.update.APK_DIR", str(apk_dir))

    resp = client.get("/api/check_update")
    payload = resp.get_json()
    assert resp.status_code == 200
    assert payload["version"] == "0.0.0"


def test_download_file(client, monkeypatch, tmp_path):
    apk_dir = tmp_path / "apks"
    apk_dir.mkdir()
    (apk_dir / "1.0.0.apk").write_text("apk")

    monkeypatch.setattr("routes.update.APK_DIR", str(apk_dir))

    resp = client.get("/api/download/1.0.0.apk")
    assert resp.status_code == 200
    assert resp.data == b"apk"


def test_logs_page(client):
    resp = client.get("/logs")
    assert resp.status_code == 200
    assert "日志" in resp.get_data(as_text=True)


def test_stream_logs(client, monkeypatch):
    monkeypatch.setattr("routes.log_viewer.os.path.exists", lambda path: True)

    def fake_open(path, mode="r", encoding=None, errors=None):
        stream = io.StringIO("line1\nline2\n")

        class ContextWrapper:
            def __enter__(self_inner):
                return stream

            def __exit__(self_inner, exc_type, exc, tb):
                stream.close()

        return ContextWrapper()

    monkeypatch.setattr("routes.log_viewer.open", fake_open, raising=False)
    monkeypatch.setattr("routes.log_viewer.time.sleep", lambda _: (_ for _ in ()).throw(GeneratorExit))

    resp = client.get("/stream")
    assert resp.status_code == 200
    data = resp.data
    if hasattr(data, "__iter__") and not isinstance(data, (bytes, bytearray)):
        collected = []
        for chunk in data:
            collected.append(chunk)
            break
        body = "".join(collected)
    else:
        body = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else str(data)
    assert "line1" in body

