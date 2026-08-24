import re
from typing import List, Dict, Any

class TaskClassifier:
    """
    Task Classifier (Rule-Based + Keyword Heuristics).
    Designed to be upgradable to a fine-tuned DistilBERT classifier.
    """
    
    CODE_KEYWORDS = [
        r"\bcode\b", r"\bfunction\b", r"\bscript\b", r"\bpython\b", r"\bjavascript\b",
        r"\bdef\b", r"\bclass\b", r"\bsql\b", r"\bapi\b", r"\balgorithm\b", r"\brefactor\b",
        r"```"
    ]
    
    VISION_KEYWORDS = [
        r"\bp&id\b", r"\bdiagram\b", r"\bimage\b", r"\bscan\b", r"\bphoto\b",
        r"\bblueprint\b", r"\bschematic\b", r"\bocr\b", r"\bvalve\b", r"\bpump\b"
    ]
    
    DOCUMENT_KEYWORDS = [
        r"\bdocument\b", r"\bsummary\b", r"\breport\b", r"\bpage\b", r"\bpdf\b",
        r"\bmanual\b", r"\bsop\b", r"\bpolicy\b", r"\brag\b"
    ]

    FINANCIAL_KEYWORDS = [
        r"\bfinancial\b", r"\bnegotiation\b", r"\bcontract\b", r"\bvendor\b", r"\bpricing\b"
    ]

    HIGH_RISK_KEYWORDS = [
        r"\bshut\s*down\b", r"\boverride\b", r"\bvalve\s*open\b", r"\bpressure\s*release\b",
        r"\bdelete\b", r"\bpurge\b", r"\bexecute\s*shell\b", r"\bnegotiation\b", r"\bconfidential\b"
    ]

    def classify(self, prompt: str, has_image: bool = False) -> Dict[str, Any]:
        tags = []
        prompt_lower = prompt.lower()

        if has_image:
            tags.append("vision")
            tags.append("pid_diagram")

        # Code detection
        for pattern in self.CODE_KEYWORDS:
            if re.search(pattern, prompt_lower):
                tags.append("code")
                break

        # Document detection
        for pattern in self.DOCUMENT_KEYWORDS:
            if re.search(pattern, prompt_lower):
                tags.append("document_summary")
                tags.append("rag")
                break

        # Financial / negotiation contract detection
        for pattern in self.FINANCIAL_KEYWORDS:
            if re.search(pattern, prompt_lower):
                tags.append("financial")
                tags.append("negotiation")
                tags.append("contract")
                break

        # Vision text hints
        if not has_image:
            for pattern in self.VISION_KEYWORDS:
                if re.search(pattern, prompt_lower):
                    tags.append("pid_diagram")
                    break

        # High risk action detection
        is_high_risk = False
        for pattern in self.HIGH_RISK_KEYWORDS:
            if re.search(pattern, prompt_lower):
                is_high_risk = True
                tags.append("high_risk_action")
                break

        # Default fallback tag
        if not tags:
            tags.append("reasoning")

        # Select primary target tag
        if "vision" in tags or "pid_diagram" in tags:
            primary = "vision"
        elif "code" in tags:
            primary = "code"
        elif "financial" in tags or "negotiation" in tags or "contract" in tags:
            primary = "financial"
        elif "document_summary" in tags or "rag" in tags:
            primary = "document_summary"
        else:
            primary = "reasoning"

        return {
            "primary_tag": primary,
            "all_tags": list(set(tags)),
            "is_high_risk": is_high_risk,
            "confidence": 0.92 if tags else 0.65
        }

classifier = TaskClassifier()
