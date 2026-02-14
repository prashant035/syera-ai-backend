import time

from interview_engine import (
    generate_question,
    store_answer,
    get_full_conversation,
    generate_closing,
    answer_candidate_question
)

from analysis_engine import analyze_interview
from voice import speak, listen
from state_manager import set_state, InterviewState


print("\n====== AI MOCK INTERVIEW SYSTEM ======\n")

# ---------- USER INPUT ----------
name = input("Enter your name: ")
topic = input("Enter interview role/topic: ")

print("\nSelect Interview Duration:")
print("1. 3 Minutes")
print("2. 5 Minutes")
print("3. 10 Minutes")

choice = input("Enter choice (1/2/3): ")

if choice == "1":
    INTERVIEW_TIME = 3 * 60
elif choice == "2":
    INTERVIEW_TIME = 5 * 60
else:
    INTERVIEW_TIME = 10 * 60


print("\nInterview Started...\n")

start_time = time.time()
question_count = 0
MAX_QUESTIONS = 5


# ---------- INTERVIEW LOOP ----------
while (time.time() - start_time < INTERVIEW_TIME) and (question_count < MAX_QUESTIONS):

    # AI thinking
    set_state(InterviewState.THINKING)
    time.sleep(1)

    # Generate question
    question = generate_question(topic, name)

    # AI speaking
    set_state(InterviewState.SPEAKING)
    print("\nAI:", question)
    speak(question)

    # Candidate answering
    set_state(InterviewState.LISTENING)
    answer = listen()

    print("Candidate:", answer)

    store_answer(answer)

    question_count += 1


# ---------- INTERVIEW ENDING ----------
set_state(InterviewState.IDLE)

closing_question = generate_closing(name)

print("\nAI:", closing_question)
speak(closing_question)

# Candidate asks interviewer a question
set_state(InterviewState.LISTENING)
candidate_question = listen()

print("Candidate:", candidate_question)

# AI replies professionally
set_state(InterviewState.THINKING)
ai_reply = answer_candidate_question(candidate_question)

set_state(InterviewState.SPEAKING)
print("\nAI:", ai_reply)
speak(ai_reply)


# ---------- ANALYSIS ----------
print("\nAnalyzing interview...\n")

analysis = analyze_interview(get_full_conversation())

print("\n===== INTERVIEW ANALYSIS =====\n")
print(analysis)
