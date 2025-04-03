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

def translate_message(message, language):
    if language.lower() == "english":
        return message
    prompt = f"Translate the following message into {language}:
{message}"
    return client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    ).choices[0].message.content.strip()

def translate_user_response(response, target_language):
    if target_language.lower() == "english":
        return response
    prompt = f"Translate this user's answer into English:
{response}"
    return client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    ).choices[0].message.content.strip()

base_questions = [
    "Can I ask for your name and email before we get started?",
    "Could you tell me the client's name, their industry and location?",
    "What were the main challenges or problems the client was facing before the project / were identified from the analysis? Try to cover things like process issues, cultural challenges, or operational bottlenecks.",
    "What were the measurable goals for this project / what did we commit to following on from the analysis (if one was carried out)?. Eg: increase throughput by 15%, improve sales conversions by 25%",
    "What were the main initiatives or tools introduced during the project? Please list at least 3 key initiatives. Eg: introduced short interval control; improved root cause analysis, introduced a CRM system",
    "Let’s capture the results! Please share measurable gains such as throughput improvement, overtime reduction, or other financial or operational results.",
    "Do you have any client feedback or quotes we can include? Please include the client’s name and their role if possible.",
    "Finally — how will the client sustain these improvements after the project finishes? What processes, reviews, or systems are being embedded to lock in the gains?"
]

language_options = [
    "English",
    "Spanish",
    "Portuguese",
    "Chinese (Mandarin)",
    "Bahasa Indonesia",
    "Bahasa Malaysia",
    "French"
]

readiness_keywords = {
    "English": ["yes", "ok", "okay", "ready", "sure", "let's go"],
    "French": ["oui", "ok", "d'accord", "prêt", "allons-y"],
    "Spanish": ["sí", "si", "ok", "claro", "listo", "vamos"],
    "Portuguese": ["sim", "ok", "claro", "pronto", "vamos"],
    "Chinese (Mandarin)": ["好的", "是", "可以", "开始"],
    "Bahasa Indonesia": ["ya", "ok", "siap", "ayo"],
    "Bahasa Malaysia": ["ya", "ok", "sedia", "mula"]
}

encouragements = [
    "Great, thank you!",
    "Appreciate that.",
    "Got it!",
    "Perfect, let’s keep going.",
    "Thanks for the detail.",
    "Alrighty, moving on!",
    "Right, let's take it to the next one."
]

humorous_prompts = [
    "Hmm... I think you might be trolling me. Shall we try that again with a serious face on? 🤨",
    "Unless your client *really* has talking koalas, let’s be a bit more realistic. 😄",
    "Are you *sure* that's what happened? Sounds like someone needs a coffee. ☕",
    "I’m pretty smart, but even I can't format nonsense into a case study. Want to give it another go?"
]

@app.route("/")
def home():
    session.clear()
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "").strip()

    if 'conversation_state' not in session or user_input.lower() == 'restart':
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
            "conversation_complete": False
        }

    state = session['conversation_state']

    if not state["started"]:
        state["started"] = True
        session.modified = True
        return jsonify({
            "reply": "🧠 Hi! I’m the Renoir Case Study Chatbot. What language would you like to use?",
            "language_options": language_options
        })

    if not state["language_selected"]:
        matched = [lang for lang in language_options if lang.lower() == user_input.lower()]
        if matched:
            state["language"] = matched[0]
            state["language_selected"] = True
            session.modified = True
        else:
            return jsonify({
                "reply": "Please choose a valid language from the options below:",
                "language_options": language_options
            })

    if not state["intro_sent"]:
        intro_message = (
            "Welcome! I’m here to guide you through a few questions so we can build a great case study around your project. "
            "If I need more detail at any point, I’ll ask – just answer as fully as you can. Ready? Let’s get started!"
        )
        translated_intro = translate_message(intro_message, state["language"])
        state["intro_sent"] = True
        state["awaiting_ready"] = True
        session.modified = True
        return jsonify({"reply": translated_intro})

    if state["awaiting_ready"]:
        allowed_words = readiness_keywords.get(state["language"], readiness_keywords["English"])
        if user_input.lower() in [word.lower() for word in allowed_words]:
            state["awaiting_ready"] = False
            session.modified = True
            return jsonify({"reply": translate_message(base_questions[0], state["language"])})
        else:
            prompt = "Just let me know when you're ready by typing 'OK' or 'Yes'! 😊"
            translated_prompt = translate_message(prompt, state["language"])
            return jsonify({"reply": translated_prompt})

    if state["conversation_complete"]:
        return jsonify({"reply": translate_message("Thanks again — you're all done! If you'd like to upload client images now, you can do so below. 📷", state["language"])})

    question_index = state["question_index"]
    current_question = base_questions[question_index]
    state["responses"][current_question] = user_input
    state["history"].append({"role": "user", "content": user_input})

    if "koala" in user_input.lower() or "hind wings" in user_input.lower():
        session.modified = True
        return jsonify({"reply": random.choice(humorous_prompts)})

    summary = "Here’s what the user has already shared:\n"
    for i in range(question_index + 1):
        q = base_questions[i]
        a = state["responses"].get(q, "(no answer)")
        summary += f"- {q}\n  Answer: {a}\n"

    eval_prompt = f"""You are a structured and friendly chatbot conducting a case study interview.\nBelow is the current answer from the user to this question:\n\"{current_question}\"\n\nAnswer:\n\"{user_input}\"\n\nAlso, here is what has already been shared so far:\n{summary}\n\nIs the answer above clear and complete? Answer ONLY with one word:\n- complete\n- incomplete"""

    eval_result = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": eval_prompt}]
    ).choices[0].message.content.strip().lower()

    if eval_result == "incomplete" and state["clarification_attempts"] < state["max_clarifications"]:
        state["clarification_attempts"] += 1
        clarify_prompt = f"""You are a friendly and structured interviewer collecting information for a case study.\nYou just asked this question:\n\"{current_question}\"\nThe user responded with:\n\"{user_input}\"\nPlease re-ask the same question in a friendly way using the exact wording of the original question:\n\"{current_question}\""""
        clarification = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": clarify_prompt}]
        ).choices[0].message.content.strip()
        session.modified = True
        return jsonify({"reply": clarification})

    state["clarification_attempts"] = 0

    if question_index < len(base_questions) - 1:
        state["question_index"] += 1
        next_question = base_questions[state["question_index"]]
        session.modified = True
        return jsonify({"reply": translate_message(f"{random.choice(encouragements)}\n\n{next_question}", state["language"])})
    else:
        state["conversation_complete"] = True
        summary_text = "📋 **Your Case Study Summary:**\n"
        translated_text = "📋 **Résumé de votre Étude de Cas :**\n"
        for i, q in enumerate(base_questions):
            a = state["responses"].get(q, "(no answer)")
            translated_a = translate_user_response(a, "English")
            summary_text += f"\n**Q{i+1}: {q}**\n➡️ {a}\n"
            translated_q = translate_message(q, state["language"])
            translated_text += f"\n**Q{i+1} : {translated_q}**\n➡️ {a}\n"

        summary_text += "\n\n🌐 **Translated Summary:**\n" + translated_text
        summary_text += "\nYou're all set! If you'd like to upload images, you can do that now — logo, site photos, or system screenshots."
        session.modified = True
        return jsonify({"reply": summary_text})

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






