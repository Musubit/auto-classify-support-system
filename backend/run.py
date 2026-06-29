"""Flask 应用启动入口。"""

import logging

from app import create_app

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
