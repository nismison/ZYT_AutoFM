from flask import Flask, request
from flask_cors import CORS

from config import logger
from db import init_database_connection, ensure_tables
from routes import register_blueprints


def create_app() -> Flask:
    app = Flask(__name__)

    # DB 连接
    init_database_connection()

    # 每次请求前打印 PID 与路径
    @app.before_request
    def _log_request_pid():
        logger.info(f"处理请求: {request.path}")

    # 蓝图
    register_blueprints(app)

    # CORS
    CORS(app, resources=r'/*')
    return app


if __name__ == "__main__":
    ensure_tables()
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True)
