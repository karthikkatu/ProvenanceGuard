from dotenv import load_dotenv

load_dotenv()

from flask import Flask

from audit.log import init_db
from routes.log import log_bp
from routes.submit import submit_bp

app = Flask(__name__)
app.register_blueprint(submit_bp)
app.register_blueprint(log_bp)
init_db()

if __name__ == "__main__":
    app.run(debug=True)
