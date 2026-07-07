import os
import time


import pymysql
import redis
from flask import Flask, jsonify, request

app = Flask(__name__)

MYSQL_HOST = os.environ["MYSQL_HOST"]
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_USER = os.environ["MYSQL_USER"]
MYSQL_PASSWORD = os.environ["MYSQL_PASSWORD"]
MYSQL_DATABASE = os.environ["MYSQL_DATABASE"]
REDIS_HOST = os.environ["REDIS_HOST"]

r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)


def get_db():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
    )


def init_db():
    # db container may still be booting when we start, so retry instead of crashing
    for attempt in range(15):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    done BOOLEAN DEFAULT FALSE
                )
                """
            )
            conn.commit()
            cur.close()
            conn.close()
            return
        except pymysql.err.OperationalError:
            time.sleep(2)
    raise RuntimeError("Could not connect to database after retries")


@app.route("/api/health")
def health():
    hits = r.incr("health_hits")
    return jsonify(status="ok", hits=hits)


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, title, done FROM tasks ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"id": row[0], "title": row[1], "done": bool(row[2])} for row in rows])


@app.route("/api/tasks", methods=["POST"])
def add_task():
    data = request.get_json(force=True)
    title = (data or {}).get("title", "").strip()
    if not title:
        return jsonify(error="title is required"), 400
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO tasks (title) VALUES (%s)", (title,))
    conn.commit()
    task_id = cur.lastrowid
    cur.close()
    conn.close()
    return jsonify(id=task_id, title=title, done=False), 201


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
