from flask import Flask

from .image import bp as image_bp
from .log_viewer import bp as log_viewer_bp
from .notify import bp as notify_bp
from .proxy import bp as proxy_bp
from .update import bp as update_bp
from .upload import bp as upload_bp
from .upload_chunk import bp as upload_chunk
from .app_config import bp as app_config


def register_blueprints(app: Flask):
    app.register_blueprint(proxy_bp)
    app.register_blueprint(image_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(upload_chunk)
    app.register_blueprint(notify_bp)
    app.register_blueprint(update_bp)
    app.register_blueprint(log_viewer_bp)
    app.register_blueprint(app_config)