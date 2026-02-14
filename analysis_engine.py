from groq import Groq
from config import GROQ_API_KEY
import json

client = Groq(api_key=GROQ_API_KEY)


def analyze_interview(conversation, metadata=None):

    transcript = ""
    candidate_answer_count = 0
    candidate_total_words = 0

    # -------- BUILD TRANSCRIPT --------
    for msg in conversation:
        role = "Interviewer" if msg["role"] == "assistant" else "Candidate"
        transcript += f"{role}: {msg['content']}\n"
        if msg["role"] == "user":
            candidate_answer_count += 1
            candidate_total_words += len(msg["content"].split())

    # -------- EXTRACT METADATA --------
    total_questions = metadata.get("total_questions", 0) if metadata else 0
    configured_duration = metadata.get("configured_duration", 300) if metadata else 300
    actual_duration = metadata.get("actual_duration", 0) if metadata else 0
    candidate_name = metadata.get("name", "Candidate") if metadata else "Candidate"
    was_early_exit = metadata.get("early_exit", False) if metadata else False

    # Calculate completion percentage
    duration_pct = round((actual_duration / configured_duration) * 100) if configured_duration > 0 else 0
    avg_words_per_answer = round(candidate_total_words / candidate_answer_count) if candidate_answer_count > 0 else 0

    # -------- PROMPT --------
    prompt = f"""
You are a strict senior technical interviewer analyzing an interview.

INTERVIEW METADATA:
- Candidate: {candidate_name}
- Total questions asked: {total_questions}
- Candidate answers given: {candidate_answer_count}
- Average words per answer: {avg_words_per_answer}
- Interview duration: {actual_duration} seconds out of {configured_duration} seconds ({duration_pct}% completed)
- Early exit by candidate: {was_early_exit}

Evaluate the candidate ONLY based on the actual answers present in the transcript.

CRITICAL SCORING RULES:

1. If the candidate answered fewer than 3 questions, ALL scores MUST be below 30.
2. If the candidate gave only 1-word or very short answers (under 10 words average), communication score MUST be below 25.
3. If the interview was ended early by the candidate (before 50% of time), reduce ALL scores by at least 30 points from what they would otherwise be.
4. If the candidate could not even introduce themselves properly, ALL scores MUST be below 15.
5. DO NOT give generous scores. Be strict and realistic.
6. A score of 0-10 is acceptable for a candidate who barely participated.
7. Empty or near-empty answers mean near-zero scores.

SCORING METHOD:

Technical Score (0-100):
- 0-20: No technical content, refused to answer, or completely wrong
- 20-40: Minimal attempt, mostly wrong or very vague  
- 40-60: Some correct points but lacking depth
- 60-80: Good understanding with reasonable explanations
- 80-100: Excellent depth with concrete examples

Communication Score (0-100):
- 0-20: Did not communicate, single words, or incoherent
- 20-40: Very poor sentence structure, unclear
- 40-60: Basic communication, understandable but not clear
- 60-80: Good clarity and structured responses
- 80-100: Exceptional articulation with well-organized thoughts

Confidence Score (0-100):
- 0-20: Did not participate or gave up immediately
- 20-40: Very hesitant, incomplete responses
- 40-60: Some confidence but inconsistent
- 60-80: Generally confident with complete answers
- 80-100: Highly confident and thorough

Overall Score:
- Weighted average: (Technical * 0.4) + (Communication * 0.3) + (Confidence * 0.3)
- Round to nearest integer

Return ONLY valid JSON, no extra text:

{{
    "technical_score": number,
    "communication_score": number,
    "confidence_score": number,
    "overall_score": number,
    "strengths": ["point1", "point2"],
    "weaknesses": ["point1", "point2"],
    "suggestions": ["point1", "point2"]
}}

Interview Transcript:
{transcript}
"""

    # -------- GROQ CALL --------
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=400
    )

    result_text = response.choices[0].message.content

    # -------- SAFE JSON PARSING (IMPORTANT FIX) --------
    try:
        # Extract JSON part even if AI adds extra text
        start = result_text.find("{")
        end = result_text.rfind("}") + 1

        json_text = result_text[start:end]

        return json.loads(json_text)

    except Exception as e:
        print("ANALYSIS PARSE ERROR:", e)
        print("RAW AI RESPONSE:", result_text)

        # fallback result (only if AI fails) - use low scores, not generous ones
        fallback_score = min(20, candidate_answer_count * 5)  # Scale with answers given
        return {
            "technical_score": fallback_score,
            "communication_score": fallback_score,
            "confidence_score": fallback_score,
            "overall_score": fallback_score,
            "strengths": ["Attempted the interview"] if candidate_answer_count > 0 else ["None identified"],
            "weaknesses": ["Analysis could not be completed - insufficient data"],
            "suggestions": ["Complete more of the interview for a thorough evaluation"]
        }
