from fastapi.responses import Response, JSONResponse
from voice_engine import speak
from dotenv import load_dotenv
load_dotenv()
import time
import uuid
import random  # Added for random greeting selection
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel

from interview_engine import (
    get_or_create_session,
    delete_session,
    generate_question,
    store_answer,
    get_full_conversation,
    start_closing,
    detect_abuse,
    generate_abuse_termination_message,
    check_question_relevance,
    generate_time_warning,
    generate_closing,
    generate_goodbye,
    answer_candidate_question,
)

from analysis_engine import analyze_interview

app = FastAPI(title="Syera AI Interview Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------- MODELS --------
class StartInterview(BaseModel):
    name: str
    domain: str
    duration: str


class Answer(BaseModel):
    session_id: str
    text: str


class EndInterview(BaseModel):
    session_id: str


# -------- START INTERVIEW --------
@app.post("/start")
def start_interview(data: StartInterview):

    # Generate unique session ID
    session_id = f"session_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    # Create session
    session = get_or_create_session(session_id)
    session["name"] = data.name
    session["domain"] = data.domain
    session["start_time"] = time.time()

    # Parse duration
    if data.duration == "3":
        session["duration_seconds"] = 3 * 60
    elif data.duration == "10":
        session["duration_seconds"] = 10 * 60
    else:
        session["duration_seconds"] = 5 * 60

    # List of greeting variations
    greetings = [
        f"Hey Mr. {data.name.split()[0]}, welcome to your {data.domain} interview. Thanks for joining me today, I'll be conducting your interview. I am excited to get started! Can you tell me a little bit about yourself?",
        f"Hello {data.name.split()[0]}, it's great to have you here for your {data.domain} interview. I'm thrilled to be your interviewer today. Let's dive right in—could you share a bit about your background?",
        f"Hi {data.name.split()[0]}, welcome to the {data.domain} interview session. Thanks for participating; I'm looking forward to this. Shall we begin? Tell me a little about yourself.",
        f"Greetings {data.name.split()[0]}, nice to meet you virtually for your {data.domain} interview. I'll be guiding you through this. Excited to learn more! Can you introduce yourself briefly?"
    ]
    
    # Randomly select one
    greeting_full = random.choice(greetings)
    greeting_repeat = "Can you tell me a little bit about yourself?"

    # Store first message in conversation
    session["conversation"].append({
        "role": "assistant",
        "content": greeting_full
    })

    session["question_count"] = 1

    return {
        "session_id": session_id,
        "question": greeting_full,
        "repeat_question": greeting_repeat,
        "duration": session["duration_seconds"],
    }


# -------- NEXT QUESTION (answer + get next) --------
@app.post("/answer")
def answer_question(data: Answer):

    session = get_or_create_session(data.session_id)
    name = session.get("name", "Candidate")
    stage = session.get("interview_stage", "technical")

    # ======== STEP 1: ABUSE DETECTION ========
    if detect_abuse(data.text):
        session["abuse_terminated"] = True
        store_answer(data.text, data.session_id)

        termination_msg = generate_abuse_termination_message(name)
        session["conversation"].append({
            "role": "assistant",
            "content": termination_msg
        })

        return {
            "question": termination_msg,
            "repeat_question": termination_msg,  # Same for termination
            "question_count": session["question_count"],
            "stage": "abuse_terminated",
            "elapsed": int(time.time() - session.get("start_time", time.time())),
            "action": "end_interview",
        }

    # Store candidate answer
    store_answer(data.text, data.session_id)

    elapsed = time.time() - session.get("start_time", time.time())
    duration = session.get("duration_seconds", 300)
    remaining = duration - elapsed
    max_questions = max(5, int(duration / 60) * 2)

    # ======== STEP 2: CANDIDATE QUESTION PHASE ========
    # If we're in "candidate_questions" stage, the candidate is asking us questions
    if stage == "candidate_questions":
        candidate_text = data.text.strip().lower()

        # Check if candidate has no questions
        no_question_phrases = [
            "no", "nope", "nothing", "no questions", "i don't have",
            "i do not have", "that's all", "that is all", "i'm good",
            "no thank you", "no thanks", "all good", "i am good",
            "skip", "none",
        ]

        has_no_questions = any(phrase in candidate_text for phrase in no_question_phrases)

        if has_no_questions:
            # No questions - generate goodbye
            goodbye_msg = generate_goodbye(name, data.session_id)
            return {
                "question": goodbye_msg,
                "repeat_question": goodbye_msg,
                "question_count": session["question_count"],
                "stage": "final",
                "elapsed": int(elapsed),
                "action": "end_interview",
            }
        else:
            # Candidate asked a question - check relevance
            is_relevant, answer = check_question_relevance(
                data.text, session.get("domain", ""), data.session_id
            )

            if not is_relevant:
                # Irrelevant question - note it, answer politely, then goodbye
                full_reply = (
                    f"{answer} "
                    f"Alright {name}, thank you for your time today. "
                    f"Best of luck with everything, {name}! Have a great day. Goodbye."
                )
                session["conversation"].append({
                    "role": "assistant",
                    "content": full_reply
                })
                return {
                    "question": full_reply,
                    "repeat_question": full_reply,
                    "question_count": session["question_count"],
                    "stage": "final",
                    "elapsed": int(elapsed),
                    "action": "end_interview",
                    "irrelevant_question": True,
                }
            else:
                # Relevant question - answer it, then say goodbye
                full_reply = (
                    f"{answer} "
                    f"Thank you for that great question, {name}. "
                    f"It was a pleasure speaking with you today. "
                    f"We will review your interview and get back to you soon. "
                    f"Best of luck, {name}! Have a wonderful day. Goodbye."
                )
                session["conversation"].append({
                    "role": "assistant",
                    "content": full_reply
                })
                return {
                    "question": full_reply,
                    "repeat_question": full_reply,
                    "question_count": session["question_count"],
                    "stage": "final",
                    "elapsed": int(elapsed),
                    "action": "end_interview",
                }

    # ======== STEP 3: TIME-AWARE QUESTION FLOW ========
    # "time_warning_given" tracks if we already warned the candidate
    time_warning_given = session.get("time_warning_given", False)

    # If very little time left (under 15s) and not yet closing, transition gracefully
    # But do NOT cut off mid-answer - we already accepted their answer above
    if remaining <= 15 and not time_warning_given and stage == "technical":
        session["time_warning_given"] = True
        # Instead of hard-stopping, move to closing which asks for candidate questions
        start_closing(data.session_id)

        # Generate the closing message (asks if candidate has questions)
        closing_msg = generate_closing(name, data.session_id)

        return {
            "question": closing_msg,
            "repeat_question": closing_msg,
            "question_count": session["question_count"],
            "stage": "candidate_questions",
            "elapsed": int(elapsed),
        }

    # Normal flow: check if we should start closing
    if (remaining <= 30 and stage == "technical") or session["question_count"] >= max_questions:
        start_closing(data.session_id)

    # Generate next question (interview_engine handles closing stage internally)
    next_question = generate_question(
        session["domain"],
        name,
        data.session_id
    )

    return {
        "question": next_question['full'],
        "repeat_question": next_question['repeat'],
        "question_count": session["question_count"],
        "stage": session["interview_stage"],
        "elapsed": int(elapsed),
    }


# -------- END INTERVIEW --------
@app.post("/end")
def end_interview(data: EndInterview):

    try:
        session = get_or_create_session(data.session_id)
        conv = get_full_conversation(data.session_id)

        elapsed = time.time() - session.get("start_time", time.time())

        # Pass metadata to the analysis engine so it can properly evaluate
        # incomplete/short interviews
        analysis_metadata = {
            "name": session.get("name", "Candidate"),
            "total_questions": session.get("question_count", 0),
            "configured_duration": session.get("duration_seconds", 300),
            "actual_duration": int(elapsed),
            "early_exit": elapsed < (session.get("duration_seconds", 300) * 0.5),
        }

        analysis = analyze_interview(conv, metadata=analysis_metadata)

        # If terminated due to abuse, reduce all scores significantly
        if session.get("abuse_terminated", False):
            analysis["technical_score"] = min(analysis.get("technical_score", 0), 20)
            analysis["communication_score"] = min(analysis.get("communication_score", 0), 10)
            analysis["confidence_score"] = min(analysis.get("confidence_score", 0), 15)
            analysis["overall_score"] = min(analysis.get("overall_score", 0), 15)
            analysis.setdefault("weaknesses", []).insert(0, "Interview terminated due to use of inappropriate language")
            analysis.setdefault("suggestions", []).insert(0, "Maintain professional language and conduct during interviews")

        result = {
            "analysis": analysis,
            "metadata": {
                "candidateName": session.get("name", ""),
                "domain": session.get("domain", ""),
                "totalQuestions": session.get("question_count", 0),
                "duration": int(elapsed),
                "configuredDuration": session.get("duration_seconds", 300),
                "abuseTerminated": session.get("abuse_terminated", False),
            },
            "conversation": conv,
        }

        # Clean up session
        delete_session(data.session_id)

        return result

    except Exception as e:
        print("END INTERVIEW ERROR:", e)

        return {
            "analysis": {
                "technical_score": 70,
                "communication_score": 70,
                "confidence_score": 70,
                "overall_score": 70,
                "strengths": ["Interview completed"],
                "weaknesses": ["Analysis failed"],
                "suggestions": ["Please try again"]
            },
            "metadata": {
                "candidateName": "",
                "domain": "",
                "totalQuestions": 0,
                "duration": 0,
                "configuredDuration": 0,
            },
            "conversation": [],
        }


@app.post("/voice")
def voice_api(data: dict):
    text = data.get("text", "")
    if not text:
        return JSONResponse(
            status_code=400,
            content={"error": "No text provided"}
        )

    try:
        audio = speak(text)

        if audio is None:
            print("VOICE ERROR: speak() returned None for text:", text[:50])
            return JSONResponse(
                status_code=500,
                content={"error": "TTS failed to generate audio"}
            )

        return Response(
            content=audio,
            media_type="audio/mpeg"
        )
    except Exception as e:
        print("VOICE ENDPOINT ERROR:", e)
        return JSONResponse(
            status_code=500,
            content={"error": f"TTS error: {str(e)}"}
        )


# -------- HEALTH CHECK --------
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Syera AI Interview Backend"}


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(app, host="0.0.0.0", port=port)
