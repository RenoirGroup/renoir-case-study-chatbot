from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, render_template, send_from_directory, session
from flask_cors import CORS
from openai import OpenAI
import os
import random
from uuid import uuid4

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", str(uuid4()))
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

base_questions = [
    "To start off with can you tell me the client's name, their industry and location?",
    "What were the main challenges or problems the client was facing before the project / were identified from the analysis? Try to cover things like process issues, cultural challenges, or operational bottlenecks.",
    "Were there any measurable goals committed for this project / what did we commit to, in terms of a business case, following on from the analysis (if one was carried out)?",
    "What were the main initiatives or tools introduced during the project? Please list at least 3 key initiatives.",
    "Let’s capture the results! Please share measurable gains such as throughput improvement, overtime reduction, or other financial or operational results.",
    "Do you have any client feedback or quotes we can include? Please include the client’s name and role if possible.",
    "Finally — how will the client sustain these improvements after the project finishes? What processes, reviews, or systems are being embedded to lock in the gains?"
]

language_choices = [
    "English",
    "Spanish",
    "Portuguese",
    "Chinese (Mandarin)",
    "Bahasa Indonesia",
    "Bahasa Malaysia",
    "French"
]

@app.route("/")
def home():
    session.clear()  # Reset state for new visitor
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "").strip()

    if 'conversation_state' not in session or user_input.lower() == 'restart':
        session['conversation_state'] = {
            "question_index": 0,
            "responses": {},
            "language_selected": False,
            "language": "English",
            "intro_sent": False,
            "conversation_complete": False
        }
        session.modified = True

    state = session['conversation_state']

    if not state["language_selected"]:
        if user_input in language_choices:
            state["language"] = user_input
            state["language_selected"] = True
            session.modified = True
        else:
            return jsonify({
                "reply": "🧠 Hi! I’m the Renoir Case Study Chatbot. What language would you like to use?",
                "language_options": language_choices
            })

    if not state["intro_sent"]:
        intro_text = (
            "Welcome! I’m here to guide you through a few questions so we can build a great case study around your project. "
            "If I need more detail at any point, I’ll ask – just answer as fully as you can. Ready? Let’s get started!"
        )
        state["intro_sent"] = True
        session.modified = True
        return jsonify({"reply": intro_text})

    if state["conversation_complete"]:
        return jsonify({"reply": "Thanks again — you're all done! If you'd like to upload client images now, you can do so below. 📷"})

    q_index = state["question_index"]
    state["responses"][base_questions[q_index]] = user_input
    session.modified = True

    if q_index < len(base_questions) - 1:
        state["question_index"] += 1
        return jsonify({"reply": base_questions[state["question_index"]]})
    else:
        state["conversation_complete"] = True
        summary = "📋 **Your Case Study Summary:**\n"
        for i, q in enumerate(base_questions):
            a = state["responses"].get(q, "(no answer)")
            summary += f"\n**Q{i+1}: {q}**\n➡️ {a}\n"
        session.modified = True
        return jsonify({"reply": summary})

@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files['file']
    image_type = request.form.get('type', 'general')
    if file:
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], image_type)
        os.makedirs(save_path, exist_ok=True)
        file.save(os.path.join(save_path, file.filename))
        return jsonify({"message": f"{image_type.capitalize()} uploaded successfully!"})
    return jsonify({"error": "No file received."}), 400

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


