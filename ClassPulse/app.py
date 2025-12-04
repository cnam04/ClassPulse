from flask import Flask
import os
from .routes import blueprints

app = Flask(__name__)

# Register all blueprints 
for bp in blueprints:
    app.register_blueprint(bp)


if __name__ == "__main__":
    port = int(os.getenv("PORT",5051))
    app.run(host="0.0.0.0", port=port)
