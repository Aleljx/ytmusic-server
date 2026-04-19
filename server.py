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


@app.route("/download", methods=["GET", "POST"])
def download():
    """Скачивает трек через yt-dlp и отдаёт MP3 напрямую."""
    if request.method == "POST":
        data = request.get_json()
        url = data.get("url", "") if data else ""
    else:
        url = request.args.get("url", "")

    if not url:
        return jsonify({"error": "url is required"}), 400

    try:
        import tempfile, glob
        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = os.path.join(tmpdir, "%(artist,uploader)s - %(title)s.%(ext)s")
            result = run_ytdlp([
                "-f", "ba", "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--no-playlist",
                "-o", output_template,
                url
            ])

            if result.returncode != 0:
                return jsonify({"error": "Ошибка скачивания", "details": result.stderr}), 400

            files = glob.glob(os.path.join(tmpdir, "*.mp3"))
            if not files:
                return jsonify({"error": "Файл не найден"}), 400

            filepath = files[0]
            filename = os.path.basename(filepath)

            from flask import send_file
            return send_file(
                filepath,
                mimetype="audio/mpeg",
                as_attachment=True,
                download_name=filename
            )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)