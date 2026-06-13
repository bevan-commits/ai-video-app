from flask import Flask, request, jsonify, render_template
import replicate
import time
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    prompt = data.get("prompt")
    
    prediction = replicate.predictions.create(
        model="minimax/video-01",
        input={"prompt": prompt, "prompt_optimizer": True}
    )
    
    while prediction.status not in ["succeeded", "failed", "canceled"]:
        time.sleep(5)
        prediction.reload()
    
    if prediction.status == "succeeded":
        return jsonify({"url": prediction.output})
    else:
        return jsonify({"error": prediction.error}), 500

if __name__ == "__main__":
    app.run(debug=True)