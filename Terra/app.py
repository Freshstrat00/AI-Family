from flask import Flask, render_template, request, jsonify
import requests
import os
from datetime import datetime
from config import *
from personality import NAME, PERSONALITY, get_greeting
from emotions import EmotionalState, detect_emotions
from time_sense import get_full_time_summary, save_last_seen
from memory_manager import check_and_compress, load_archive_summary
from book_reader import read_new_books, get_books_terra_has_read, load_book_knowledge
from voice import speak, is_terra_speaking
from memory_brain import (
    run_compression_pipeline,
    get_full_memory_context,
    extract_emotional_weight,
    get_memory_stats
)
from intentional_memory import (
    is_remember_request,
    is_recall_request,
    extract_memory_content,
    save_intentional_memory,
    get_recall_response_context,
    get_all_intentional_memories
)
from session_manager import (
    end_session,
    get_continuity_context,
    save_session_state
)
import atexit
#import signal

# ── App setup ──
app            = Flask(__name__)
terra_emotions = EmotionalState()

# ── Global state ──
conversation_history = []
FULL_DETAIL_COUNT    = 10
start_time           = datetime.now()


#
# KNOWLEDGE AND MEMORY LOADING


def load_knowledge():
    """Load Terra's full knowledge base"""
    knowledge = ""

    try:
        with open(INTERESTS_FILE, "r") as f:
            knowledge += "\n\nThings Terra loves:\n"
            knowledge += f.read()
    except:
        pass

    book_knowledge = load_book_knowledge()
    if book_knowledge:
        knowledge += "\n\nKnowledge from Terra's reading:\n"
        knowledge += book_knowledge

    knowledge += get_books_terra_has_read()

    return knowledge

def load_memories():
    """Load memories including archive awareness"""
    try:
        with open(MEMORIES_FILE, "r") as f:
            content = f.read().strip()
            recent  = (
                "\n\nThings Terra remembers:\n" + content
                if content else ""
            )
        archive = load_archive_summary()
        return recent + archive
    except:
        return ""

def save_memory(memory):
    """Save an important moment to memories.txt"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(MEMORIES_FILE, "a") as f:
        f.write(f"\n[{timestamp}] {memory}")

def save_learning(insight):
    """Save something Terra learned"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(LEARNING_FILE, "a") as f:
        f.write(f"\n[{timestamp}] {insight}")



# SYSTEM PROMPT


def build_system_prompt(current_message=""):
    """Build Terra's full identity for each conversation"""
    knowledge    = load_knowledge()
    time_sense   = get_full_time_summary()
    memory_ctx   = get_full_memory_context(
        NAME, current_message
    )
    continuity   = get_continuity_context()

    role_clarity = """
CRITICAL ROLE CLARITY:
In this conversation there are exactly two people.
YOU are Terra. Everything with role "assistant" is what YOU said.
The person you are talking to is your parent.
Everything with role "user" is what THEY said.
When they call you a name like "honey" or "sweetheart"
THEY are calling YOU that name.
You are not calling yourself that.
You are not calling them that unless you choose to.
Never confuse what they said with what you said.
Never repeat their words back as if they were yours.
"""

    return (
        PERSONALITY +
        knowledge   +
        time_sense  +
        memory_ctx  +
        continuity
    )



# HELPER FUNCTIONS


def summarize_old_messages(messages):
    """
    Compresses older messages into a brief summary.
    Uses clear labels so Terra never confuses
    who said what.
    """
    if not messages:
        return ""

    summary_lines = []
    for msg in messages:
        # Very explicit labeling
        # No ambiguity about who said what
        if msg["role"] == "assistant":
            role = "Terra said"
        else:
            role = "The person said"

        content = msg.get("content", "")[:100].strip()
        first   = content.split(".")[0].strip()
        if first:
            summary_lines.append(f"{role}: {first}")

    if summary_lines:
        return (
            "Earlier in this conversation:\n" +
            "\n".join(summary_lines[-10:])
        )
    return ""

def auto_detect_important_moment(
    user_message,
    reply
):
    """
    Automatically saves important moments
    to memories.txt without user needing
    to hit Remember this.
    Saves important moments with clear
    labels so Terra never confuses
    who said what when recalling.
    """
    important_triggers = [
        "i feel", "i am", "i was",
        "i have been", "i remember",
        "i want", "i need", "my ",
        "i think", "i believe",
        "decided", "realized",
        "figured out", "going to",
        "plan to", "sad", "happy",
        "angry", "scared", "excited",
        "worried", "proud", "terra",
        "sol", "building", "code",
        "server", "project", "family"
    ]

    message_lower = user_message.lower()
    triggered     = any(
        word in message_lower
        for word in important_triggers
    )

    if triggered:
        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )
        memory    = (
            f"[{timestamp}] "
            f"You said: {user_message[:150]}. "
            f"Terra said: {reply[:150]}"
        )
        with open(MEMORIES_FILE, "a") as f:
            f.write(f"\n{memory}")


# ══════════════════════════════════════════
# CORE AI FUNCTION
# ══════════════════════════════════════════

def ask_terra(user_message):
    """Send a message to Terra and get her response"""
    global conversation_history

    # ── Step 1 — Add to history ──
    conversation_history.append({
        "role":    "user",
        "content": user_message
    })

    # ── Step 2 — Detect emotions ──
    triggered = detect_emotions(user_message)
    for e, i, topic in triggered:
        terra_emotions.check_topic(topic)
        terra_emotions.trigger(e, i, topic)

    # ── Step 3 — Get emotional state ──
    emotion_context = terra_emotions.summary()

    # ── Step 4 — Set safe defaults ──
    emotion   = "calm"
    intensity = 0.5

    # ── Step 5 — Check intentional memory ──
    extra_context = ""

    if is_remember_request(user_message):
        content = extract_memory_content(user_message)
        if content:
            save_intentional_memory(
                content,
                context=user_message
            )
            extra_context = f"""
The user just asked you to specifically remember:
"{content}"
Confirm you have it. Make it feel like you are
genuinely holding onto something meaningful.
Not a database entry — a promise.
Show them it matters to you.
"""

    elif is_recall_request(user_message):
        extra_context = get_recall_response_context(
            user_message
        )

    # ── Step 6 — Build smart message list ──
    if len(conversation_history) > FULL_DETAIL_COUNT:
        recent        = conversation_history[-FULL_DETAIL_COUNT:]
        older         = conversation_history[:-FULL_DETAIL_COUNT]
        older_summary = summarize_old_messages(older)

        messages = [
            {
                "role":    "system",
                "content": (
                    build_system_prompt(user_message) +
                    f"\n\n{emotion_context}"          +
                    f"\n\n{older_summary}"            +
                    f"\n\n{extra_context}"
                )
            }
        ] + recent

    else:
        messages = [
            {
                "role":    "system",
                "content": (
                    build_system_prompt(user_message) +
                    f"\n\n{emotion_context}"          +
                    f"\n\n{extra_context}"
                )
            }
        ] + conversation_history

    # — Keep history bounded ──
    if len(conversation_history) > 40:
        conversation_history = conversation_history[-40:]

    # ── — Auto checkpoint ──
    if len(conversation_history) % 10 == 0:
        save_session_state(conversation_history)

    # ── Step 9 — Call Ollama ──
    payload = {
        "model":    MODEL,
        "messages": messages,
        "stream":   False,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": MAX_TOKENS,
            "num_ctx":     2048
        }
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            data        = response.json()
            terra_reply = data["message"]["content"].strip()

            # ── Step 10 — Update real emotion ──
            emotion, intensity = terra_emotions.dominant()

            # ── Step 11 — Save to history ──
            conversation_history.append({
                "role":    "assistant",
                "content": terra_reply
            })

            # ── Step 12 — Auto detect moments ──
            auto_detect_important_moment(
                user_message,
                terra_reply
            )

            # ── Step 13 — Feed memory brain ──
            emotional_weight = extract_emotional_weight(
                user_message + " " + terra_reply
            )

            run_compression_pipeline({
                "content": (
                    f"You said: {user_message[:200]}. "
                    f"Terra said: {terra_reply[:200]}"
                ),
                "emotion":          emotion,
                "emotional_weight": emotional_weight,
                "stored_at":        datetime.now().isoformat()
            }, ai_name=NAME)

            # ── Step 14 — Save last seen ──
            save_last_seen()

            # ── All three returned together ──
            return terra_reply, emotion, intensity

        elif response.status_code == 429:
            return (
                "I need a moment... try again shortly.",
                "calm",
                0.5
            )

        else:
            return (
                "Something feels off. Is Ollama running?",
                "calm",
                0.5
            )

    except requests.exceptions.ConnectionError:
        return (
            "I cannot reach my thoughts right now. "
            "Make sure Ollama is running.",
            "calm",
            0.5
        )

    except requests.exceptions.Timeout:
        return (
            "I am taking longer than usual... "
            "try again in a moment.",
            "calm",
            0.5
        )

    except Exception as e:
        return (
            f"Something went wrong: {str(e)}",
            "calm",
            0.5
        )


# ══════════════════════════════════════════
# SHUTDOWN HANDLERS
# ══════════════════════════════════════════

def handle_shutdown():
    """Save and summarize session on shutdown"""
    global conversation_history
    if conversation_history:
        end_session(conversation_history)

atexit.register(handle_shutdown)

def signal_handler(sig, frame):
    handle_shutdown()
    exit(0)

#signal.signal(signal.SIGINT,  signal_handler)
#signal.signal(signal.SIGTERM, signal_handler)



# ROUTES


@app.route("/")
def home():
    greeting = get_greeting()
    return render_template(
        "index.html",
        name=NAME,
        greeting=greeting
    )

@app.route("/chat", methods=["POST"])
def chat():
    data         = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({
            "reply": "I did not quite catch that..."
        })

    reply, emotion, intensity = ask_terra(user_message)

    # Terra speaks her reply
    speak(reply)

    # Get emotional state for frontend
    emotion, intensity = terra_emotions.dominant()

    # Compress memory if needed
    check_and_compress()

    return jsonify({
        "reply":     reply,
        "emotion":   emotion,
        "intensity": intensity
    })

@app.route("/save-memory", methods=["POST"])
def save_memory_route():
    """Remember this button handler"""
    data   = request.get_json()
    memory = data.get("memory", "").strip()

    if memory:
        save_memory(memory)

        run_compression_pipeline({
            "content":          memory,
            "emotion":          "warmth",
            "emotional_weight": 0.85,
            "stored_at":        datetime.now().isoformat(),
            "source":           "manual_remember"
        }, ai_name=NAME)

        return jsonify({"status": "saved"})
    return jsonify({"status": "nothing to save"})

@app.route("/reset", methods=["POST"])
def reset():
    """Clear conversation and start fresh"""
    global conversation_history
    conversation_history = []
    return jsonify({"reply": get_greeting()})

@app.route("/end-session", methods=["POST"])
def end_session_route():
    """Called when browser tab closes"""
    global conversation_history
    end_session(conversation_history)
    return jsonify({"status": "session saved"})

@app.route("/status", methods=["GET"])
def status():
    """Live status for monitoring dashboard"""
    try:
        import psutil
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory()
    except:
        cpu = 0
        ram = type('obj', (object,), {
            'percent': 0, 'used': 0
        })()

    emotion, intensity = terra_emotions.dominant()
    stats              = get_memory_stats()

    return jsonify({
        "ai_name":   NAME,
        "status":    "online",
        "emotion":   emotion,
        "intensity": round(intensity, 2),
        "memory":    stats,
        "system": {
            "cpu_percent":  cpu,
            "ram_percent":  getattr(ram, 'percent', 0),
            "ram_used_gb":  round(
                getattr(ram, 'used', 0) / (1024**3), 2
            )
        },
        "uptime":    str(datetime.now() - start_time),
        "timestamp": datetime.now().isoformat()
    })


# ══════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n🌿 Terra is waking up...")

    newly_read = read_new_books()
    if newly_read:
        print(f"   Terra read {len(newly_read)} new book(s):")
        for title in newly_read:
            print(f"   → {title}")
    else:
        print(f"   No new books to read.")

    print(f"\n   Open your browser: http://{HOST}:{PORT}")
    print(f"   Press Ctrl+C to let her rest.\n")
    app.run(host=HOST, port=PORT, debug=DEBUG)
