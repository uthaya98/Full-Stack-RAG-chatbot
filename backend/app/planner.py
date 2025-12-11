from typing import Dict, Any, Optional
import re

def detect_intent(user_text: str) -> Dict[str, Optional[str]]:

    text = user_text.strip().lower()

    if text.startswith("calculate") or text.startswith("/calc") or re.search(r"[0-9]+\s*[\+\-\*\/]", text):
        expr = text

        if text.startswith("/calc"):
            expr = text[len("/calc"):].strip()
        elif text.startswith("calculate"):
            expr = text[len("calculate"):].strip()
        return {"intent": "calc", "query": expr}
    
     # product queries
    if "product" in text or "drinkware" in text or "what is" in text and "zus" in text:
        return {"intent": "products", "query": user_text}

    # outlets queries
    if "outlet" in text or "opening" in text or "open" in text or "hours" in text:
        return {"intent": "outlets", "query": user_text}
    
    return {"intent": "chat", "query": user_text}