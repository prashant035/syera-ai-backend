import os
from groq import Groq
import random  # Added for random message selection

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# ------------------------------
# SESSION-BASED STATE STORAGE
# ------------------------------
sessions = {}

def get_or_create_session(session_id):
    if session_id not in sessions:
        sessions[session_id] = {
            "conversation": [],
            "interview_stage": "technical",
            "name": "",
            "domain": "",
            "question_count": 0,
            "abuse_terminated": False,
        }
    return sessions[session_id]

def delete_session(session_id):
    if session_id in sessions:
        del sessions[session_id]

# For backward compatibility (CLI usage)
conversation = []
interview_stage = "technical"

# --------------------------------------------------
# ABUSE / INAPPROPRIATE LANGUAGE DETECTION
# --------------------------------------------------
ABUSE_WORDS = [
    "fuck", "shit", "damn", "ass", "bitch", "bastard", "dick", "crap",
    "hell", "idiot", "stupid", "dumb", "moron", "retard", "stfu",
    "wtf", "bullshit", "screw you", "shut up", "suck", "piss",
    "motherfucker", "asshole", "cunt", "whore", "slut",
]

def detect_abuse(text):
    """Check if candidate used abusive/inappropriate language."""
    lower = text.lower().strip()
    for word in ABUSE_WORDS:
        if word in lower:
            return True
    return False

def generate_abuse_termination_message(name):
    """Generate a firm but professional termination message. Uses name only once."""
    return (
        "I need to address something important. "
        "The language you just used is inappropriate for a professional interview setting. "
        "We maintain a respectful environment during all our interviews. "
        "Unfortunately, due to the use of inappropriate language, we will need to end this interview immediately. "
        "Please consider this a learning experience for future professional interactions. "
        "Best of luck in your career. Goodbye."
    )

# --------------------------------------------------
# CANDIDATE QUESTION RELEVANCE CHECK
# --------------------------------------------------
def check_question_relevance(question, domain, session_id=None):
    """
    Check if candidate's question is interview-relevant.
    Returns: (is_relevant: bool, answer: str)
    """
    system_prompt = f"""
You are a professional interviewer for a {domain} position.
The interview is ending and the candidate asked a question.

Determine if this question is relevant to the interview, the role, the company,
career growth, team culture, work expectations, or any professional topic.

If the question is RELEVANT:
- Answer it briefly and professionally in 2-3 sentences.
- Start your response with: RELEVANT:

If the question is IRRELEVANT or INAPPROPRIATE (off-topic, personal, weird, nonsensical):
- Respond with a polite redirect.
- Start your response with: IRRELEVANT:

Candidate's question: "{question}"
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": system_prompt}],
            temperature=0.3,
            max_tokens=150
        )
        reply = response.choices[0].message.content.strip()

        if reply.upper().startswith("RELEVANT:"):
            return True, reply[len("RELEVANT:"):].strip()
        elif reply.upper().startswith("IRRELEVANT:"):
            return False, reply[len("IRRELEVANT:"):].strip()
        else:
            # Default: treat as relevant
            return True, reply
    except Exception as e:
        print("QUESTION RELEVANCE CHECK ERROR:", e)
        return True, "That's a good question. I'd suggest discussing that with the hiring manager during the next round."

# --------------------------------------------------
# GENERATE NEXT QUESTION
# --------------------------------------------------
def generate_question(topic, name, session_id=None):

    if session_id:
        session = get_or_create_session(session_id)
        conv = session["conversation"]
        stage = session["interview_stage"]
    else:
        global interview_stage
        conv = conversation
        stage = interview_stage

    # If interview already closing
    if stage == "closing":
        closing_msg = generate_closing(name, session_id)
        return {'full': closing_msg, 'repeat': closing_msg}  # Always return dict

    system_prompt = f"""
You are a professional technical interviewer named Syera.

Candidate Name: {name}
Interview Role: {topic}

CRITICAL NAME RULES:
- Use the candidate's name occasionally in questions or responses, like "Mr. {name}", to make it personal (1-2 times per few questions).
- For example, say "Mr. Pandey, can you explain..." or "As you mentioned, Mr. Pandey...".
- Do not overuse it (not every response).

Interview Rules:
- Always conduct interview in English.
- Start with basic questions then move upward in difficulty.
- Ask about projects the candidate has worked on, then ask questions related to those projects.
- Ask ONLY ONE question at a time.
- Ask only verbally understandable and verbally answerable questions. Never ask the candidate to write code.
- Keep questions concise and answerable within 30-40 seconds.
- Avoid examples unless absolutely necessary.
- Do NOT give long explanations.
- IMPORTANT: Do not include any introductory phrases, transitions, or extra text like "Okay Mr. {name}, let's dive into..." or "We can move forward." in your response. Just ask the question directly.
- When the candidate mentions something relevant (e.g., a project or skill), transition naturally. For example, if they mention a project in response to a different question, say something like "We were discussing networking, but since you brought up your project, let's explore that. Can you elaborate on your projects?" to make the conversation flow smoothly.
- If candidate says "I don't know" or gives a wrong answer:
    * Give a very brief 1-2 short sentence explanation of the correct answer.
    * Then put '---' on a new line.
    * Then IMMEDIATELY ask the next question.
    * Your response must clearly end with a question mark.
    * Use repeat filler phrases like "No problem" or "That's okay" some times when asking question immediately after explainaing the correct answer .
- Keep your response SHORT. Maximum 3 sentences total (1 brief explanation + --- + 1 question).
"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conv[-6:])

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=0.6,
        max_tokens=80
    )

    question = response.choices[0].message.content.strip()

    # Parse for separator
    if '---' in question:
        parts = question.split('---', 1)
        full_message = parts[0].strip() + '\n' + parts[1].strip()
        repeat_message = parts[1].strip()
    else:
        full_message = question
        repeat_message = question

    # Add transition for first question after intro
    if session_id and session["question_count"] == 1:  # First technical question
        transition = f"Okay Mr. {name}, let's dive into some technical background and skills. "
        full_message = transition + full_message
        # DO NOT add transition to repeat_message - keep it short for retries

    # Post-process repeat_message to ensure it's always just the core question
    # Take the last sentence that ends with '?' (assuming the question is at the end)
    sentences = repeat_message.split('.')
    last_sentence = sentences[-1].strip()
    if last_sentence.endswith('?'):
        repeat_message = last_sentence
    else:
        # Fallback: If no '?', keep the last sentence (for edge cases)
        repeat_message = last_sentence
    # Ensure it starts with a capital letter if possible
    if repeat_message and not repeat_message[0].isupper():
        repeat_message = repeat_message[0].upper() + repeat_message[1:]

    # Debug logging
    print("DEBUG: Raw AI response:", question)
    print("DEBUG: Full message after transition:", full_message)
    print("DEBUG: Repeat message after processing:", repeat_message)

    conv.append({
        "role": "assistant",
        "content": full_message  # Store full in conversation for analysis
    })

    if session_id:
        session["question_count"] += 1

    return {'full': full_message, 'repeat': repeat_message}

# --------------------------------------------------
# START CLOSING PHASE
# --------------------------------------------------
def start_closing(session_id=None):
    if session_id:
        session = get_or_create_session(session_id)
        session["interview_stage"] = "closing"
    else:
        global interview_stage
        interview_stage = "closing"

# --------------------------------------------------
# TIME WARNING MESSAGE (10 seconds left)
# --------------------------------------------------
def generate_time_warning(name, session_id=None):
    """Generate a heads-up message when ~10 seconds remain."""
    if session_id:
        session = get_or_create_session(session_id)
        conv = session["conversation"]
    else:
        conv = conversation

    # List of warning variations
    warnings = [
        "Alright, we are reaching the end of our scheduled time. Please take a moment to finish your thought. After this, I will give you a chance to ask any questions you may have.",
        "We're almost out of time for our interview. Wrap up your current point if you can. Then, I'll open the floor for any questions you might have.",
        "Time's ticking down; we have just a few seconds left. Please complete your response. Following that, feel free to ask me anything about the role or company.",
        "Okay, we're nearing the end of our allotted time. Go ahead and finish up. After that, you'll have an opportunity to ask questions about the position or team."
    ]
    
    # Randomly select one
    warning = random.choice(warnings)

    conv.append({
        "role": "assistant",
        "content": warning
    })

    return warning

# --------------------------------------------------
# CLOSING MESSAGE (asks candidate for questions)
# --------------------------------------------------
def generate_closing(name, session_id=None):

    if session_id:
        session = get_or_create_session(session_id)
        conv = session["conversation"]
        session["interview_stage"] = "candidate_questions"
    else:
        global interview_stage
        interview_stage = "candidate_questions"
        conv = conversation

    # List of closing variations
    closings = [
        "That concludes the technical part of our interview. You did well! Before we wrap up, do you have any questions for me about the role, the team, or anything else you would like to know?",
        "We've covered the main interview questions. Great job on your responses! Now, is there anything you'd like to ask regarding the position, the team, or the company?",
        "The technical portion is complete. You handled it well! Before we end, do you have questions about the role, our team, or anything else?",
        "Alright, that's the end of the core interview questions. You did a fantastic job! Feel free to ask about the role, the team, or whatever else is on your mind."
    ]
    
    # Randomly select one
    closing_message = random.choice(closings)

    conv.append({
        "role": "assistant",
        "content": closing_message
    })

    return closing_message

# --------------------------------------------------
# FINAL GOODBYE MESSAGE
# --------------------------------------------------
def generate_goodbye(name, session_id=None):
    """Generate the final farewell message with best of luck."""
    if session_id:
        session = get_or_create_session(session_id)
        conv = session["conversation"]
        session["interview_stage"] = "final"
    else:
        global interview_stage
        interview_stage = "final"
        conv = conversation

    # List of goodbye variations
    goodbyes = [
        f"Thank you so much for your time today, {name}. It was a pleasure speaking with you. We will review your interview and get back to you soon. Best of luck with everything! Have a wonderful day. Goodbye.",
        f"Thanks for joining us today, {name}. It was great chatting with you. We'll be in touch after reviewing your interview. Wishing you all the best! Take care.",
        f"Appreciate your time and effort, {name}. Pleasure to interview you. Expect to hear from us shortly with next steps. Good luck ahead! Farewell.",
        f"Thank you for your participation, {name}. It was enjoyable speaking with you. We'll follow up soon with next steps. Best wishes! Goodbye."
    ]
    
    # Randomly select one
    goodbye = random.choice(goodbyes)

    conv.append({
        "role": "assistant",
        "content": goodbye
    })

    return goodbye

# --------------------------------------------------
# ANSWER LAST CANDIDATE QUESTION
# --------------------------------------------------
def answer_candidate_question(question, session_id=None):

    if session_id:
        session = get_or_create_session(session_id)
        conv = session["conversation"]
    else:
        conv = conversation

    system_prompt = """
You are a professional interviewer answering the candidate's final question.
Reply briefly and professionally in 2-3 sentences.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        temperature=0.5,
        max_tokens=120
    )

    reply = response.choices[0].message.content.strip()

    conv.append({
        "role": "assistant",
        "content": reply
    })

    return reply

# --------------------------------------------------
# STORE ANSWER
# --------------------------------------------------
def store_answer(answer, session_id=None):
    if session_id:
        session = get_or_create_session(session_id)
        session["conversation"].append({
            "role": "user",
            "content": answer
        })
    else:
        conversation.append({
            "role": "user",
            "content": answer
        })

# --------------------------------------------------
# GET FULL CONVERSATION
# --------------------------------------------------
def get_full_conversation(session_id=None):
    if session_id:
        session = get_or_create_session(session_id)
        return session["conversation"]
    return conversation