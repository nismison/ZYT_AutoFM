from flask import Flask
from .proxy import bp as proxy_bp
from .image import bp as image_bp
from .upload import bp as upload_bp
from .notify import bp as notify_bp
from .update import bp as update_bp
from .log_viewer import bp as log_viewer_bp


def register_blueprints(app: Flask):
    app.register_blueprint(proxy_bp)
    app.register_blueprint(image_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(notify_bp)
    app.register_blueprint(update_bp)
    app.register_blueprint(log_viewer_bp)