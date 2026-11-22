"""Minimal Flask app used to test Flask itself and the Cloudflare quick tunnel.

Run:  python tools_tests/flask_min_app.py  (listens on 127.0.0.1:5055)
"""
from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/ping")
def ping():
    return jsonify(status="ok", app="tools-test")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055)
