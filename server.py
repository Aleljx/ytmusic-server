from flask import Flask, request, jsonify, send_file
import subprocess
import json
import os
import tempfile
import glob

app = Flask(__name__)

COOKIES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")


def run_ytdlp(args: list) -> subprocess.CompletedProcess:
    """Запускает yt-dlp с куками если они есть."""
    base_args = ["yt-dlp", "--no-warnings"]
    if os.path.exists(COOKIES_PATH):
        base_args += ["--cookies", COOKIES_PATH]
    return subprocess.run(
        base_args + args,
        capture_output=True,
        text=True,
        timeout=60
    )


@app.route("/", methods=["GET"])
def index():
    cookies_status = "✅ куки загружены" if os.path.exists(COOKIES_PATH) else "❌ куки не найдены"
    return jsonify({"status": "ok", "service": "YT Music Downloader API", "cookies": cookies_status})


# ... (начало кода без изменений)

@app.route("/info", methods=["GET", "POST"])  # Добавили GET
def get_info():
    try:
        # Пытаемся взять URL из параметров ссылки (для GET) или из JSON (для POST)
        if request.method == "POST":
            data = request.get_json(force=True, silent=True) or {}
            url = data.get("url", "").strip()
        else:
            url = request.args.get("url", "").strip()

        if not url:
            return jsonify({"error": "url is required"}), 400

        # ВАЖНО: Увеличим таймаут для Render, так как бесплатные сервера тормозят
        result = run_ytdlp(["--dump-json", "--no-playlist", url])

        if result.returncode != 0:
            # Выводим ошибку в консоль сервера, чтобы видеть её в логах Render
            print(f"YT-DLP Error: {result.stderr}")
            return jsonify({"error": "Не удалось получить данные", "details": result.stderr}), 400

        info = json.loads(result.stdout)

        # ... (остальная логика обработки thumbnail и duration остается такой же)

        thumb_url = info.get("thumbnail", "")
        for t in reversed(info.get("thumbnails", [])):
            if t.get("width") and t.get("height") and t["width"] == t["height"]:
                thumb_url = t["url"]
                break

        duration_sec = info.get("duration", 0)
        duration_str = f"{int(duration_sec) // 60}:{int(duration_sec) % 60:02d}" if duration_sec else ""

        return jsonify({
            "title": info.get("title", "Неизвестно"),
            "artist": info.get("artist") or info.get("uploader") or "Неизвестно",
            "duration": duration_str,
            "thumbnail": thumb_url,
        })

    except Exception as e:
        print(f"SERVER ERROR: {str(e)}")  # Чтобы видеть ошибку в логах Render
        return jsonify({"error": str(e)}), 500


# ... (остальной код)


@app.route("/download", methods=["GET", "POST"])
def download():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        url = data.get("url", "")
    else:
        url = request.args.get("url", "")

    if not url:
        return jsonify({"error": "url is required"}), 400

    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            output_template = os.path.join(tmpdir, "%(artist,uploader)s - %(title)s.%(ext)s")
            result = run_ytdlp([
                "-f", "ba", "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--embed-thumbnail",
                "--embed-metadata",
                "--convert-thumbnails", "jpg",
                "--ppa", "ThumbnailsConvertor:-vf crop=ih:ih",
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

            return send_file(
                filepath,
                mimetype="audio/mpeg",
                as_attachment=True,
                download_name=filename
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)