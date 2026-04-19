from flask import Flask, request, jsonify
import subprocess
import json
import os

app = Flask(__name__)


def run_ytdlp(args: list) -> subprocess.CompletedProcess:
    """Запускает yt-dlp и возвращает результат."""
    return subprocess.run(
        ["yt-dlp"] + args,
        capture_output=True,
        text=True,
        timeout=60
    )


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "service": "YT Music Downloader API"})


@app.route("/info", methods=["POST"])
def get_info():
    """Возвращает метаданные трека: название, исполнитель, обложка, длительность."""
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "url is required"}), 400

    url = data["url"]

    try:
        result = run_ytdlp(["--dump-json", "--no-playlist", url])
        if result.returncode != 0:
            return jsonify({"error": "Не удалось получить данные", "details": result.stderr}), 400

        info = json.loads(result.stdout)

        # Ищем квадратную обложку
        thumb_url = info.get("thumbnail", "")
        for t in reversed(info.get("thumbnails", [])):
            if t.get("width") and t.get("height") and t["width"] == t["height"]:
                thumb_url = t["url"]
                break

        duration_sec = info.get("duration", 0)
        duration_str = f"{int(duration_sec)//60}:{int(duration_sec)%60:02d}" if duration_sec else ""

        return jsonify({
            "title":     info.get("title", "Неизвестно"),
            "artist":    info.get("artist") or info.get("uploader") or "Неизвестно",
            "duration":  duration_str,
            "thumbnail": thumb_url,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download", methods=["POST"])
def download():
    """Скачивает трек и возвращает прямую ссылку на MP3."""
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "url is required"}), 400

    url = data["url"]

    try:
        # Получаем прямую аудио-ссылку без скачивания
        result = run_ytdlp([
            "--get-url",
            "-f", "bestaudio",
            "--no-playlist",
            url
        ])

        if result.returncode != 0:
            return jsonify({"error": "Не удалось получить ссылку", "details": result.stderr}), 400

        download_url = result.stdout.strip().split("\n")[0]

        if not download_url:
            return jsonify({"error": "Пустая ссылка"}), 400

        return jsonify({"download_url": download_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
