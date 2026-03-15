import os
from typing import List, Tuple

from openai import OpenAI

from utils.database import get_chat_history, save_chat_message

def run_agent_with_history(user_message: str, api_key: str) -> str:
    """
    Run chat agent with conversation history using OpenAI.
    """
    client = OpenAI(api_key=api_key)
    
    # Get conversation history from database
    history = get_chat_history(limit=10)
    
    # Build messages for OpenAI
    messages = [
        {
            "role": "system",
            "content": """You are HealthGuard AI, a helpful healthcare assistant.
            
            Your capabilities:
            - Answer general health questions
            - Provide medication information
            - Give wellness advice
            - Explain symptoms (but never diagnose)
            
            IMPORTANT:
            - Always include disclaimer that you're not a doctor
            - Recommend consulting healthcare professionals for serious issues
            - Be empathetic and supportive
            - Focus on Indian healthcare context when relevant
            - Keep responses concise (2-3 paragraphs)
            """
        }
    ]
    
    # Add conversation history
    for role, content, timestamp in history:
        messages.append({"role": role, "content": content})
    
    # Add current user message
    messages.append({"role": "user", "content": user_message})
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content
        
        # Save to database
        save_chat_message("user", user_message)
        save_chat_message("assistant", ai_response)
        
        return ai_response
        
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"


def run_simple_chat(user_message: str) -> str:
    """
    Simple rule-based chat without OpenAI (fallback).
    """
    message_lower = user_message.lower()
    
    # Simple keyword responses
    if any(word in message_lower for word in ['hello', 'hi', 'hey']):
        return "Hello! I'm HealthGuard AI. How can I help you with your health today?"
    
    elif 'medication' in message_lower or 'medicine' in message_lower:
        return "I can help you with medication information. Please ask about a specific medicine or check your medication list in the app."
    
    elif 'pain' in message_lower:
        return "For pain management, common options include paracetamol or ibuprofen. However, please consult your doctor for persistent pain. What type of pain are you experiencing?"
    
    elif 'fever' in message_lower:
        return "For fever, paracetamol (like Dolo 650 or Crocin) is commonly used. Stay hydrated and rest. If fever persists beyond 3 days or is very high, please consult a doctor."
    
    else:
        return "I'm here to help with health questions. For the best responses, please enable OpenAI integration or ask about medications, symptoms, or general health advice. Remember, I'm not a substitute for professional medical advice."


def _validate_med_record(med_tuple) -> list:
    """
    Validate medication record for data inconsistencies.
    Returns list of warning messages (empty if valid).
    
    Args:
        med_tuple: (id, name, dosage, frequency, time, notes, max_dose, created)
    """
    warnings = []
    
    try:
        med_id, name, dosage, frequency, med_time, notes, max_dose, created = med_tuple
        
        # Check if name is empty
        if not name or not name.strip():
            warnings.append("Medicine name is empty")
        
        # Check if dosage contains 'mg'
        if not dosage or 'mg' not in dosage.lower():
            warnings.append("Dosage should include 'mg' (e.g., 500mg)")
        
        # Check time format
        if not med_time or ':' not in med_time:
            warnings.append("Time format invalid (should be HH:MM)")
        else:
            try:
                h, m = map(int, med_time.split(':'))
                if h < 0 or h > 23 or m < 0 or m > 59:
                    warnings.append("Time values out of range")
            except:
                warnings.append("Time format invalid")
        
        # Check frequency
        valid_frequencies = ["Once daily", "Twice daily", "Three times daily", "Four times daily", "As needed"]
        if frequency not in valid_frequencies:
            warnings.append(f"Unusual frequency: {frequency}")
        
        return warnings
        
    except Exception as e:
        return [f"Error validating record: {str(e)}"]