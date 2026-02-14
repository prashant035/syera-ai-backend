class InterviewState:
    IDLE = "idle"
    SPEAKING = "speaking"
    LISTENING = "listening"
    THINKING = "thinking"


current_state = InterviewState.IDLE


def set_state(state):
    global current_state
    current_state = state
    print("\nSTATE:", state)
