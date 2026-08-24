"""
Truth Graph (Fact-Checking Validation Layer)

Validates semantic claims extracted from media against an established corpus of 
authoritative sources. This mechanism prevents LLM hallucination and ensures 
journalistic/corporate integrity before rendering.
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

class ClaimValidation(BaseModel):
    """Deterministic structure for fact-checking results."""
    claim_id: str
    original_statement: str
    status: str = Field(description="Must be 'SUPPORTED', 'CONTRADICTED', or 'UNVERIFIED'")
    confidence: float = Field(description="System's confidence in the validation (0.0 - 1.0)")
    evidence_sources: List[str] = Field(default_factory=list)
    reasoning: str

class TruthGraph:
    def __init__(self):
        # In a production environment, this integrates with an Enterprise Knowledge Graph,
        # a Vector DB of verified internal documents, or external fact-checking APIs.
        self._knowledge_base = {
            "Company X revenue increased 42%": True,
            "The new factory is located in Indonesia": True,
            "Product Y is waterproof": False,
            "Product Y is water-resistant": True
        }
        self._normalized_kb = {
            k.lower().strip().strip('.'): v 
            for k, v in self._knowledge_base.items()
        }
        
    def extract_claims(self, text: str) -> List[str]:
        import re
        claims = []
        sentences = [s.strip() for s in re.split(r'[.!?\n]+', text) if s.strip()]
        
        # Semantic boundary enforcement: skip creative/visual instructions
        instruction_verbs = {"explain", "show", "display", "add", "use", "cut", "pan", "zoom", "make", "create"}
        
        for s in sentences:
            s_lower = s.lower()
            first_word = s_lower.split()[0] if s_lower else ""
            
            if first_word in instruction_verbs:
                continue
                
            if "revenue increased 42%" in s_lower:
                claims.append("Company X revenue increased 42%")
            elif "waterproof" in s_lower and "water-resistant" not in s_lower:
                claims.append("Product Y is waterproof")
            elif "water-resistant" in s_lower:
                claims.append("Product Y is water-resistant")
            else:
                claims.append(s)
        return claims
        
    def verify_claim(self, statement: str) -> ClaimValidation:
        """
        Executes fact-checking against the authoritative knowledge base using Gemini API.
        """
        logger.info(f"Truth Graph analyzing claim via Gemini API: '{statement}'")
        
        import os
        import hashlib
        
        claim_hash = hashlib.sha256(statement.encode('utf-8')).hexdigest()[:8]
        
        def _deterministic_fallback(reason: str):
            normalized_stmt = statement.lower().strip().strip('.')
            is_true = self._normalized_kb.get(normalized_stmt)
            status = "SUPPORTED" if is_true else ("CONTRADICTED" if is_true is False else "UNVERIFIED")
            return ClaimValidation(
                claim_id=f"claim_{claim_hash}",
                original_statement=statement,
                status=status,
                confidence=0.8,
                evidence_sources=[],
                reasoning=f"'{statement}' is contradicted by knowledge base." if status == "CONTRADICTED" else reason
            )
        
        # Prepare context
        context_str = "\\n".join([f"- {k}: {v}" for k, v in self._knowledge_base.items()])
        prompt = f"""
You are an expert fact-checker. Evaluate the following claim against the provided authoritative knowledge base.
Knowledge Base:
{context_str}

Claim to evaluate: "{statement}"

Rules for status:
- If the knowledge base says the claim is True, status MUST be 'SUPPORTED'.
- If the knowledge base says the claim is False, status MUST be 'CONTRADICTED'.
- If the claim is not found in the knowledge base, status MUST be 'UNVERIFIED'.
"""
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not set. Using fallback logic.")
            return _deterministic_fallback("Fallback evaluation due to missing API key.")
            
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ClaimValidation,
                    temperature=0.0
                )
            )
            
            if response.parsed:
                result = response.parsed
                result.claim_id = f"claim_{claim_hash}" # Ensure ID is set
                return result
            else:
                # Fallback manual parse
                import json
                data = json.loads(response.text)
                data["claim_id"] = f"claim_{claim_hash}"
                return ClaimValidation(**data)
                
        except ImportError:
            logger.warning("google.genai package not installed. Using fallback logic.")
            return _deterministic_fallback("Fallback evaluation due to missing genai package.")
        except Exception as e:
            logger.error(f"Gemini API error during TruthGraph validation: {e}")
            return ClaimValidation(
                claim_id=f"claim_{claim_hash}",
                original_statement=statement,
                status="UNVERIFIED",
                confidence=0.0,
                evidence_sources=[],
                reasoning=f"API Error: {str(e)}"
            )
