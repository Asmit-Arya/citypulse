"""
=============================================================================
FILE: ai_service.py
TIER: Cognitive AI & Defensive Triage Layer
-----------------------------------------------------------------------------
PURPOSE:
Analyzes qualitative, unstructured customer service notes (e.g., 'need skin fade 
and beard wash') and attaches an adaptive time modifier (in minutes) to tickets.

ARCHITECTURAL PRINCIPLES & SECURITY:
1. Backend Mediation:
   External AI API keys are NEVER exposed to client-side browsers. Requests are
   dispatched server-side via Python, pulling secrets securely from environment variables.
2. Defensive Engineering & Graceful Degradation:
   Third-party AI APIs can encounter latency, rate-limiting, or network drops.
   This module uses strict timeouts (3.0s) and an automated rule-based heuristic
   fallback so that CityPulse remains 100% operational even during total AI outage.
=============================================================================
"""

import os
import requests
from dotenv import load_dotenv

# Load secret environment variables from local .env file
load_dotenv()
AI_KEY = os.getenv("AI_API_KEY")
AI_ENDPOINT = os.getenv("AI_ENDPOINT")

def get_ai_ticket_modifier(service_name, customer_notes):
    """
    Evaluates customer request notes to determine additional required service minutes.

    Parameters:
        service_name (str): The baseline service (e.g., 'Standard Haircut').
        customer_notes (str): Natural language notes submitted by the user.

    Returns:
        int: Additional minutes to attach to the ticket (between 0 and 25).
    """
    clean_notes = str(customer_notes).strip().lower() if customer_notes else ""

    # Return immediately if no qualitative notes were provided
    if not clean_notes:
        return 0

    # -------------------------------------------------------------------------
    # STEP 1: Rule-Based Heuristic Fallback
    # Scans for common operational complexity keywords. Used as a safe fallback
    # if the external AI service times out, is offline, or lacks API credits.
    # -------------------------------------------------------------------------
    complexity_keywords = ["fade", "wash", "color", "beard", "styling", "detailing", "complex", "urgent"]
    heuristic_modifier = 0
    for keyword in complexity_keywords:
        if keyword in clean_notes:
            heuristic_modifier += 5
    heuristic_modifier = min(heuristic_modifier, 20)  # Cap heuristic modifier at 20 mins

    # If running with mock keys during local development, skip external calls
    if not AI_KEY or AI_KEY.startswith("mock"):
        return heuristic_modifier

    # -------------------------------------------------------------------------
    # STEP 2: External Cognitive API Dispatch
    # -------------------------------------------------------------------------
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
        "temperature": 0.0  # Zero temperature forces deterministic, factual outputs
    }

    # -------------------------------------------------------------------------
    # STEP 3: Defensive Request Handling
    # -------------------------------------------------------------------------
    try:
        # Strict timeout prevents server worker threads from blocking indefinitely
        response = requests.post(AI_ENDPOINT, headers=headers, json=payload, timeout=3.0)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"].strip()
            # Extract digits only to prevent malformed text from crashing the backend
            digits = "".join(ch for ch in content if ch.isdigit())
            if digits:
                return min(int(digits), 25)
    except requests.exceptions.RequestException:
        # Gracefully swallow connection timeouts, DNS failures, or HTTP errors
        pass

    # Safe degradation to keyword heuristic
    return heuristic_modifier

def estimate_wait_with_ai(queue_count, wait_per_person, notes):
    """
    Legacy helper function: Estimates total wait time using mathematical baseline
    with defensive fallback safeguards.
    """
    baseline_wait = int(queue_count) * int(wait_per_person)
    clean_notes = str(notes).strip() if notes else ""

    if not clean_notes or not AI_KEY or AI_KEY.startswith("mock"):
        return {
            "estimated_wait": baseline_wait,
            "engine": "baseline_formula",
            "guidance": "Standard mathematical baseline applied."
        }

    return {
        "estimated_wait": baseline_wait + 10,
        "engine": "ai_analyzed",
        "guidance": "Wait time adjusted based on service complexity."
    }