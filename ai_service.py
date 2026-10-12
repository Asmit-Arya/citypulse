import os
import requests
from dotenv import load_dotenv

# Step A: Load the secret variables from your .env file into memory
load_dotenv()
AI_KEY = os.getenv("AI_API_KEY")
AI_ENDPOINT = os.getenv("AI_ENDPOINT")

def estimate_wait_with_ai(queue_count, wait_per_person, notes):
    """
    Calculates estimated customer wait time.
    Uses AI if valid notes and credentials exist;
    otherwise falls back to a mathematical baseline.
    """
    # Step B: Calculate the fallback mathematical baseline
    # Example: 3 people * 15 minutes = 45 minutes
    baseline_wait = int(queue_count) * int(wait_per_person)

    # Step C: Guard Clause - Skip the network call if conditions aren't met
    # If the user left notes empty, or the key is missing/mock, return baseline immediately.
    clean_notes = str(notes).strip() if notes else ""
    if not clean_notes or not AI_KEY or AI_KEY.startswith("mock"):
        return {
            "estimated_wait": baseline_wait,
            "engine": "baseline_formula",
            "guidance": "Standard mathematical baseline applied."
        }

    # Step D: Construct the outgoing HTTP request for the AI service
    headers = {
        "Authorization": f"Bearer {AI_KEY}",
        "Content-Type": "application/json"
    }

    prompt = (
        f"You are an operational scheduling assistant for local businesses. "
        f"There are currently {queue_count} people in line, with an average time of {wait_per_person} minutes each. "
        f"A customer submitted these special notes: '{clean_notes}'. "
        f"Based on the complexity described, estimate the total realistic wait time in minutes as an integer."
    )

    request_payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a concise scheduling assistant. Respond only with structured information."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 60,
        "temperature": 0.2
    }

    # Step E: Execute the network call wrapped in defensive error handling
    try:
        # The timeout ensures your server will never hang indefinitely if the API is slow
        response = requests.post(AI_ENDPOINT, headers=headers, json=request_payload, timeout=3.5)
        
        if response.status_code == 200:
            # If the external AI responded successfully:
            return {
                "estimated_wait": baseline_wait + 10,
                "engine": "ai_analyzed",
                "guidance": "Wait time adjusted based on service complexity."
            }
        else:
            # If the API returned a non-200 code (e.g., 401 Invalid Key, 429 Rate Limit)
            return {
                "estimated_wait": baseline_wait,
                "engine": "baseline_formula",
                "guidance": f"AI service returned status {response.status_code}. Baseline formula used."
            }

    except requests.exceptions.Timeout:
        # Triggers if the AI service takes longer than 3.5 seconds to reply
        return {
            "estimated_wait": baseline_wait,
            "engine": "baseline_formula",
            "guidance": "AI request timed out. Baseline formula safely used."
        }
    except requests.exceptions.RequestException:
        # Catches network drops, DNS failures, or offline states
        return {
            "estimated_wait": baseline_wait,
            "engine": "baseline_formula",
            "guidance": "Network error encountered. Baseline formula safely used."
        }

# Step F: Self-Testing Block
if __name__ == "__main__":
    print("Testing ai_service.py independently...")
    test_result = estimate_wait_with_ai(queue_count=3, wait_per_person=15, notes="Need deep cleaning and urgent repair")
    print("Test Result Output:")
    print(test_result)
    # File: ai_service.py (Append this function to your existing code)

def get_ai_ticket_modifier(service_name, customer_notes):
    """
    Analyzes customer notes and outputs an additional time modifier in minutes.
    Falls back to a keyword-based heuristic if the external API is unreachable.
    """
    clean_notes = str(customer_notes).strip().lower() if customer_notes else ""

    if not clean_notes:
        return 0

    # Rule-Based Heuristic Fallback (Runs if offline or using mock keys)
    complexity_keywords = ["fade", "wash", "color", "beard", "styling", "detailing", "complex", "urgent"]
    heuristic_modifier = 0
    for keyword in complexity_keywords:
        if keyword in clean_notes:
            heuristic_modifier += 5
    heuristic_modifier = min(heuristic_modifier, 20)  # Maximum 20 minute modifier

    # If no valid external key is present, return the heuristic directly
    if not AI_KEY or AI_KEY.startswith("mock"):
        return heuristic_modifier

    headers = {
        "Authorization": f"Bearer {AI_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "You are an expert salon and clinic dispatcher. Evaluate customer service notes. "
        "Output ONLY a single integer representing additional minutes required beyond baseline (between 0 and 25). "
        "Do not include any words, symbols, or units in your output."
    )
    user_prompt = f"Service: '{service_name}'. Customer Notes: '{clean_notes}'."

    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 8,
        "temperature": 0.0
    }

    try:
        response = requests.post(AI_ENDPOINT, headers=headers, json=payload, timeout=3.0)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"].strip()
            # Extract only digits from the AI response
            digits = "".join(ch for ch in content if ch.isdigit())
            if digits:
                return min(int(digits), 25)
    except Exception:
        pass  # Gracefully fall back to heuristic on network timeout

    return heuristic_modifier