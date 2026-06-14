from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file
import replicate
import time
import os
import bcrypt
import requests
import tempfile
from dotenv import load_dotenv
from moviepy.editor import VideoFileClip, concatenate_videoclips

load_dotenv()

app = Flask(__name__)
app.secret_key = "changethislater123"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET")

def supa(table):
    return f"{SUPABASE_URL}/rest/v1/{table}"

def headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def db_get(table, filters=""):
    r = requests.get(f"{supa(table)}?{filters}", headers=headers())
    return r.json()

def db_post(table, data):
    r = requests.post(supa(table), json=data, headers=headers())
    return r.json()

def db_patch(table, filters, data):
    r = requests.patch(f"{supa(table)}?{filters}", json=data, headers=headers())
    return r.json()

# ─── Pages ───────────────────────────────────────────

@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    try:
        email = session["user"]
        user = db_get("users", f"email=eq.{email}&select=credits")
        credits = user[0]["credits"] if user else 0
        videos = db_get("videos", f"user_email=eq.{email}&order=created_at.desc")
        return render_template("index.html", email=email, credits=credits, videos=videos)
    except Exception as e:
        print("Home error:", e)
        return render_template("index.html", email=session["user"], credits=0, videos=[])

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/signup")
def signup():
    return render_template("signup.html")

# ─── Auth ────────────────────────────────────────────

@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    existing = db_get("users", f"email=eq.{email}")
    if existing:
        return jsonify({"error": "Email already registered"}), 400
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db_post("users", {"email": email, "password": hashed, "credits": 3})
    session["user"] = email
    return jsonify({"success": True})

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    user = db_get("users", f"email=eq.{email}")
    if not user:
        return jsonify({"error": "User not found"}), 404
    if not bcrypt.checkpw(password.encode(), user[0]["password"].encode()):
        return jsonify({"error": "Wrong password"}), 401
    session["user"] = email
    return jsonify({"success": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── Generate ─────────────────────────────────────────

@app.route("/generate", methods=["POST"])
def generate():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401

    email = session["user"]
    user = db_get("users", f"email=eq.{email}&select=credits")
    credits = user[0]["credits"] if user else 0

    if credits <= 0:
        return jsonify({"error": "No credits left. Please upgrade your plan."}), 403

    prompt = request.json.get("prompt")

    prediction = replicate.predictions.create(
        model="minimax/video-01",
        input={"prompt": prompt, "prompt_optimizer": True}
    )

    while prediction.status not in ["succeeded", "failed", "canceled"]:
        time.sleep(5)
        prediction.reload()

    if prediction.status == "succeeded":
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET")
        )

        # Upload to Cloudinary for permanent storage
        upload = cloudinary.uploader.upload(
            prediction.output,
            resource_type="video",
            folder="ai-video-app"
        )
        permanent_url = upload["secure_url"]

        db_patch("users", f"email=eq.{email}", {"credits": credits - 1})
        db_post("videos", {"user_email": email, "url": permanent_url, "prompt": prompt})
        return jsonify({"url": permanent_url})
    else:
        return jsonify({"error": prediction.error}), 500

# ─── Merge ────────────────────────────────────────────

@app.route("/merge", methods=["POST"])
def merge():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401

    urls = request.json.get("urls", [])
    if len(urls) < 2:
        return jsonify({"error": "Select at least 2 videos to merge"}), 400

    tmp_files = []
    clips = []

    try:
        for url in urls:
            r = requests.get(url, timeout=30)
            tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            tmp.write(r.content)
            tmp.close()
            tmp_files.append(tmp.name)
            clips.append(VideoFileClip(tmp.name))

        merged = concatenate_videoclips(clips, method="compose")
        output_path = tempfile.mktemp(suffix=".mp4")
        merged.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)

        for clip in clips:
            clip.close()
        for f in tmp_files:
            os.unlink(f)

        return send_file(output_path, mimetype="video/mp4", as_attachment=True, download_name="merged-video.mp4")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)