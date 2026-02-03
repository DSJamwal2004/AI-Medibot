import re

def generate_conversation_title(message: str) -> str:
    """
    Generate a short, safe title from the first user message.
    """
    if not message:
        return "Medical conversation"

    # Remove punctuation and extra spaces
    cleaned = re.sub(r"[^\w\s]", "", message).strip()

    # Capitalize nicely
    words = cleaned.split()
    title_words = words[:6]  # limit length

    title = " ".join(title_words).capitalize()

    return title if title else "Medical conversation"
