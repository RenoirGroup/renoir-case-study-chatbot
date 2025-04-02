from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, render_template, send_from_directory, session
from flask_cors import CORS
from openai import OpenAI
import os
import random
from uuid import uuid4
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", str(uuid4()))
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

supported_languages = [
    "English",
    "Spanish",
    "Portuguese",
    "Chinese (Mandarin)",
    "Indonesian Bahasa",
    "Malaysian Bahasa",
    "French"
]

base_questions = [
    "To start of can you tell me the client's name, their industry and location?",
    "What were the main challenges or problems the client was facing before the project / were identified from the analysis? Try to cover things like process issues, cultural challenges, or operational bottlenecks.",
    "Were there any measurable goals committed for this project / what did we commit to, in terms of a business case, following on from the analysis (if one was carried out)?",
    "What were the main initiatives or tools introduced during the project? Please list at least 3 key initiatives.",
    "Let’s capture the results! Please share measurable gains such as throughput improvement, overtime reduction, or other financial or operational results.",
    "Do you have any client feedback or quotes we can include? Please include the client’s name and role if possible.",
    "Finally — how will the client sustain these improvements after the project finishes? What processes, reviews, or systems are being embedded to lock in the gains?"
]

encouragements = [
    "Great, thank you!",
    "Appreciate that.",
    "Got it!",
    "Perfect, let’s keep going.",
    "Thanks for the detail.",
    "That's good info, let's keep going!",
    "Brilliant! Let's go on to the next question!"
]

humorous_prompts = [
    "Hmm... I think you might be trolling me. Shall we try that again with a serious face on? 🤨",
    "Are you *sure* that's what happened? Sounds like someone needs a coffee. ☕",
    "I’m pretty smart, but even I can't format nonsense into a case study. Want to give it another go?"
]

def translate_text(text, lang):
    if "english" in lang.lower():
        return text
    prompt = f"Translate this into {lang}: {text}"
    try:
        translated = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()
        return translated
    except:
        return text

@app.before_request
def make_session_permanent():
    session.permanent = False

@app.route("/")
def home():
    return render_template("index.html", title="Renoir Case Study Chatbot")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message").strip()

    if 'conversation_state' not in session or user_input.lower() in ["restart", "new", "start"]:
        session['conversation_state'] = {
            "question_index": 0,
            "history": [],
            "responses": {},
            "clarification_attempts": 0,
            "max_clarifications": 1,
            "language_selected": False,
            "language": "English",
            "started": False,
            "intro_sent": False,
            "awaiting_ready": False,
            "conversation_complete": False,
            "awaiting_restart_confirm": False
        }

    state = session['conversation_state']

    if state.get("awaiting_restart_confirm"):
        if user_input.lower() in ["yes", "ok", "restart", "sure"]:
            session.pop('conversation_state')
            return jsonify({"reply": "Great! Starting a new case study... 🧠\n\nPlease choose a language:\n- " + "\n- ".join(supported_languages)})
        else:
            return jsonify({"reply": "Okay, I'll stay here if you need me! Let me know if you'd like to start over."})

    if not state["started"]:
        state["started"] = True
        session.modified = True
        return jsonify({"reply": "🧠 Hi! I’m the Renoir Case Study Chatbot. Please choose a language:\n- " + "\n- ".join(supported_languages)})

    if not state["language_selected"]:
        selected = [lang for lang in supported_languages if lang.lower() in user_input.lower()]
        if selected:
            state["language"] = selected[0]
        else:
            state["language"] = "English"
        state["language_selected"] = True

        intro_message = (
            "Welcome! I’m here to guide you through a few questions so we can build a great case study around your project. "
            "If I need more detail at any point, I’ll ask – just answer as fully as you can. Ready? Let’s get started!"
        )

        translated_intro = translate_text(intro_message, state['language'])

        state["intro_sent"] = True
        state["awaiting_ready"] = True
        session.modified = True
        return jsonify({"reply": translated_intro})

    if state["awaiting_ready"]:
        if user_input.lower() in ["yes", "ok", "okay", "ready", "sure", "let's go"]:
            state["awaiting_ready"] = False
            session.modified = True
            return jsonify({"reply": translate_text(base_questions[0], state['language'])})
        else:
            return jsonify({"reply": translate_text("Just let me know when you're ready by typing 'OK' or 'Yes'! 😊", state['language'])})

    if state["conversation_complete"]:
        state["awaiting_restart_confirm"] = True
        session.modified = True
        return jsonify({"reply": translate_text("You've already completed this case study. Would you like to start a new one? (Yes/No)", state['language'])})

    question_index = state["question_index"]
    current_question = base_questions[question_index]

    if user_input.lower() in ["skip", "next"]:
        response = "(User chose to skip this question)"
    else:
        response = user_input

    if state["responses"].get(current_question) and user_input.lower() in ["asked and answered", "already answered"]:
        response = state["responses"][current_question]

    state["responses"][current_question] = response
    state["history"].append({"role": "user", "content": user_input})

    if any(keyword in user_input.lower() for keyword in ["koala", "hind wings"]):
        session.modified = True
        return jsonify({"reply": translate_text(random.choice(humorous_prompts), state['language'])})

    if user_input.lower() not in ["skip", "next", "asked and answered", "already answered"]:
        eval_prompt = f"""You are a structured and friendly chatbot conducting a case study interview.\nBelow is the current answer from the user to this question:\n\"{current_question}\"\n\nAnswer:\n\"{user_input}\"\n\nIs the answer above clear and complete? Answer ONLY with one word:\n- complete\n- incomplete"""

        eval_result = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": eval_prompt}]
        ).choices[0].message.content.strip().lower()

        if eval_result == "incomplete" and state["clarification_attempts"] < state["max_clarifications"]:
            state["clarification_attempts"] += 1
            clarification = f"Thanks! Can you tell me a bit more? {current_question}"
            session.modified = True
            return jsonify({"reply": translate_text(clarification, state['language'])})

    state["clarification_attempts"] = 0

    if question_index < len(base_questions) - 1:
        state["question_index"] += 1
        next_q = base_questions[state["question_index"]]
        reply = f"{random.choice(encouragements)}\n\n{next_q}"
        session.modified = True
        return jsonify({"reply": translate_text(reply, state['language'])})
    else:
        state["conversation_complete"] = True

        filename = f"case_study_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join("uploads", filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state["responses"], f, ensure_ascii=False, indent=2)

        summary_text = "📋 **Your Case Study Summary:**\n"
        for i, q in enumerate(base_questions):
            a = state["responses"].get(q, "(no answer)")
            summary_text += f"\n**Q{i+1}: {q}**\n➡️ {a}\n"
        summary_text += f"\nYour responses have been saved. The marketing team can find them in the file `{filename}`.\n\nIf you'd like to start a new case study, just type 'restart'."

        session.modified = True
        return jsonify({"reply": translate_text(summary_text, state['language'])})

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
    app.run(host="0.0.0.0", port=5000, debug=True)


