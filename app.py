from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import replicate
import time
import os
import bcrypt
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

app = Flask(__name__)
app.secret_key = "changethislater123"

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SECRET"))

# ─── Pages ───────────────────────────────────────────

@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    user = supabase.table("users").select("credits").eq("email", session["user"]).execute()
    credits = user.data[0]["credits"] if user.data else 0
    return render_template("index.html", email=session["user"], credits=credits)

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

    existing = supabase.table("users").select("email").eq("email", email).execute()
    if existing.data:
        return jsonify({"error": "Email already registered"}), 400

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    supabase.table("users").insert({"email": email, "password": hashed, "credits": 3}).execute()
    session["user"] = email
    return jsonify({"success": True})

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    user = supabase.table("users").select("*").eq("email", email).execute()
    if not user.data:
        return jsonify({"error": "User not found"}), 404

    if not bcrypt.checkpw(password.encode(), user.data[0]["password"].encode()):
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

    user = supabase.table("users").select("credits").eq("email", session["user"]).execute()
    credits = user.data[0]["credits"] if user.data else 0

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
        supabase.table("users").update({"credits": credits - 1}).eq("email", session["user"]).execute()
        return jsonify({"url": prediction.output})
    else:
        return jsonify({"error": prediction.error}), 500

if __name__ == "__main__":
    app.run(debug=True)