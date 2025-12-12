"""
SentinelAI LLM Service - HuggingFace Integration
================================================

Advanced LLM service with support for:
- HuggingFace Inference API
- Specialized fraud detection models
- Fallback to general-purpose models
- Structured JSON output parsing
"""

import os
import json
import re
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass
import asyncio
import httpx

from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger
from sentinelai.services.rag_service import RAGContext

logger = get_logger(__name__)


@dataclass
class LLMAnalysisResult:
    """Structured result from LLM analysis"""
    risk_score: int
    risk_level: str
    flagged_issues: List[str]
    reasoning: str
    confidence_score: float
    recommendation: str
    sar_required: bool
    raw_response: str = ""


class HuggingFaceLLMService:
    """
    HuggingFace-powered LLM Service for AML Analysis
    
    Supports multiple models with automatic fallback:
    1. Primary: Bilic/Mistral-7B-LLM-Fraud-Detection (specialized)
    2. Secondary: ProsusAI/finbert (financial sentiment) + reasoning
    3. Fallback: Meta-Llama/Llama-3.1-8B-Instruct (general purpose)
    """
    
    # Model configurations
    MODELS = {
        "fraud_detection": {
            "repo_id": "Bilic/Mistral-7B-LLM-Fraud-Detection",
            "type": "specialized",
            "max_tokens": 2048
        },
        "finbert": {
            "repo_id": "ProsusAI/finbert",
            "type": "sentiment",
            "max_tokens": 512
        },
        "llama3_8b": {
            "repo_id": "meta-llama/Meta-Llama-3-8B-Instruct",
            "type": "general",
            "max_tokens": 4096
        },
        "llama3_70b": {
            "repo_id": "meta-llama/Meta-Llama-3.1-70B-Instruct", 
            "type": "general",
            "max_tokens": 4096
        },
        "mistral_7b": {
            "repo_id": "mistralai/Mistral-7B-Instruct-v0.2",
            "type": "general",
            "max_tokens": 4096
        }
    }
    
    # AML System Prompt
    AML_SYSTEM_PROMPT = """You are an expert AI Financial Crime Compliance Officer with extensive experience in Anti-Money Laundering (AML) analysis. You are analyzing a transaction for potential money laundering risks.

Your expertise includes:
- FATF recommendations and guidelines
- Bank Secrecy Act (BSA) compliance
- Suspicious Activity Report (SAR) filing requirements
- Know Your Customer (KYC) procedures
- Enhanced Due Diligence (EDD) protocols
- Geographic risk assessment
- Structuring/smurfing detection
- PEP and sanctions screening

ANALYSIS FRAMEWORK:
1. Transaction Pattern Analysis - Evaluate the transaction characteristics
2. Geographic Risk Assessment - Assess jurisdictional risks
3. Customer Profile Analysis - Review customer type, account age, behavior
4. Adverse Media Correlation - Cross-reference with search results
5. Red Flag Identification - Identify specific AML red flags
6. Risk Scoring - Assign quantitative risk score
7. Recommendation - Provide actionable compliance guidance

OUTPUT REQUIREMENTS:
You MUST respond with ONLY valid JSON in the following exact format:
{
    "riskScore": <integer 0-100>,
    "riskLevel": "<LOW|MEDIUM|HIGH|CRITICAL>",
    "flaggedIssues": [
        "<specific issue 1>",
        "<specific issue 2>"
    ],
    "reasoning": "<detailed multi-paragraph analysis>",
    "confidenceScore": <float 0.0-1.0>,
    "recommendation": "<APPROVE|REVIEW|ESCALATE|BLOCK>",
    "sarRequired": <boolean>,
    "redFlags": [
        "<red flag code 1>",
        "<red flag code 2>"
    ]
}

Do NOT include any text before or after the JSON. Do NOT use markdown code blocks."""

    def __init__(self):
        self.logger = get_logger("service.llm")
        
        # Get API key from environment
        self.api_key = os.getenv('HUGGINGFACE_API_KEY') or (
            settings.llm.huggingface_api_key.get_secret_value() 
            if settings.llm.huggingface_api_key else None
        )
        
        # Groq as backup
        self.groq_api_key = os.getenv('GROQ_API_KEY') or (
            settings.llm.groq_api_key.get_secret_value()
            if settings.llm.groq_api_key else None
        )
        
        # HTTP client
        self.http_client = httpx.AsyncClient(timeout=120.0)
        
        # Track available models
        self.available_models: List[str] = []
        
        self.logger.info("HuggingFace LLM Service initialized")
    
    async def analyze_transaction(
        self,
        transaction: Dict[str, Any],
        customer: Dict[str, Any],
        rag_context: Optional[RAGContext] = None
    ) -> LLMAnalysisResult:
        """
        Perform LLM-powered transaction analysis.
        
        Args:
            transaction: Transaction details
            customer: Customer information
            rag_context: Optional RAG search context
        
        Returns:
            Structured LLMAnalysisResult
        """
        self.logger.info(f"Starting LLM analysis for transaction")
        
        # Build the analysis prompt
        prompt = self._build_analysis_prompt(transaction, customer, rag_context)
        
        # Try models in order of preference
        models_to_try = ["llama3_8b", "mistral_7b", "llama3_70b"]
        
        for model_key in models_to_try:
            try:
                # First try HuggingFace
                if self.api_key:
                    response = await self._call_huggingface(
                        model_key, 
                        prompt
                    )
                    if response:
                        return self._parse_llm_response(response)
                
                # Fallback to Groq
                if self.groq_api_key:
                    response = await self._call_groq(prompt)
                    if response:
                        return self._parse_llm_response(response)
                        
            except Exception as e:
                self.logger.warning(f"Model {model_key} failed: {str(e)}")
                continue
        
        # If all LLM calls fail, use rule-based fallback
        self.logger.warning("All LLM models failed, using rule-based fallback")
        return self._rule_based_fallback(transaction, customer, rag_context)
    
    def _build_analysis_prompt(
        self,
        transaction: Dict[str, Any],
        customer: Dict[str, Any],
        rag_context: Optional[RAGContext] = None
    ) -> str:
        """Build the complete analysis prompt with all context"""
        
        prompt_parts = []
        
        # System instruction
        prompt_parts.append(self.AML_SYSTEM_PROMPT)
        prompt_parts.append("\n" + "=" * 60 + "\n")
        
        # RAG Context (if available)
        if rag_context:
            prompt_parts.append("**EXTERNAL INTELLIGENCE (RAG Search Results):**")
            prompt_parts.append(f"Entity Searched: {rag_context.entity_name}")
            prompt_parts.append(f"Adverse Media Found: {'YES - ELEVATED RISK' if rag_context.adverse_media_found else 'No significant adverse media'}")
            
            if rag_context.sanctions_indicators:
                prompt_parts.append(f"Sanctions Keywords Detected: {', '.join(rag_context.sanctions_indicators)}")
            
            prompt_parts.append(f"\nBusiness Information: {rag_context.business_info}")
            
            if rag_context.key_findings:
                prompt_parts.append("\nKey Findings from Web Search:")
                for finding in rag_context.key_findings[:5]:
                    prompt_parts.append(f"  • {finding}")
            
            prompt_parts.append("\n" + "-" * 40 + "\n")
        
        # Transaction details
        prompt_parts.append("**TRANSACTION DETAILS:**")
        prompt_parts.append(json.dumps({
            "amount": transaction.get("amount"),
            "currency": transaction.get("currency", "USD"),
            "transaction_type": transaction.get("transaction_type"),
            "origin_country": transaction.get("origin_country"),
            "destination_country": transaction.get("destination_country"),
            "timestamp": str(transaction.get("timestamp", datetime.utcnow()))
        }, indent=2))
        
        prompt_parts.append("\n" + "-" * 40 + "\n")
        
        # Customer details
        prompt_parts.append("**CUSTOMER PROFILE:**")
        prompt_parts.append(json.dumps({
            "name": customer.get("name"),
            "customer_type": customer.get("customer_type"),
            "account_age_days": customer.get("account_age_days"),
            "country": customer.get("country", customer.get("origin_country"))
        }, indent=2))
        
        # Analysis instructions
        prompt_parts.append("\n" + "=" * 60)
        prompt_parts.append("""
**YOUR TASK:**
Analyze this transaction considering ALL provided context. Pay special attention to:
1. Does the transaction amount match the expected profile for this customer type?
2. Are the jurisdictions involved associated with elevated AML risk?
3. Do the RAG search results reveal any concerning information?
4. Is there evidence of structuring, layering, or other ML typologies?

Provide your analysis as valid JSON only.""")
        
        return "\n".join(prompt_parts)
    
    async def _call_huggingface(
        self,
        model_key: str,
        prompt: str
    ) -> Optional[str]:
        """Call HuggingFace Inference API"""
        
        model_config = self.MODELS.get(model_key)
        if not model_config:
            return None
        
        url = f"https://api-inference.huggingface.co/models/{model_config['repo_id']}"
        
        try:
            response = await self.http_client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": model_config["max_tokens"],
                        "temperature": 0.1,
                        "return_full_text": False,
                        "do_sample": True
                    }
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get("generated_text", "")
                elif isinstance(result, dict):
                    return result.get("generated_text", "")
            
            self.logger.warning(
                f"HuggingFace API returned {response.status_code}: {response.text}"
            )
            
        except Exception as e:
            self.logger.error(f"HuggingFace API error: {str(e)}")
        
        return None
    
    async def _call_groq(self, prompt: str) -> Optional[str]:
        """Call Groq API as fallback"""
        
        try:
            response = await self.http_client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": settings.llm.groq_model or "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": self.AML_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 4096
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            
            self.logger.warning(
                f"Groq API returned {response.status_code}: {response.text}"
            )
            
        except Exception as e:
            self.logger.error(f"Groq API error: {str(e)}")
        
        return None
    
    def _parse_llm_response(self, response: str) -> LLMAnalysisResult:
        """Parse LLM response into structured result"""
        
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                
                return LLMAnalysisResult(
                    risk_score=int(data.get("riskScore", 50)),
                    risk_level=data.get("riskLevel", "MEDIUM"),
                    flagged_issues=data.get("flaggedIssues", []) + data.get("redFlags", []),
                    reasoning=data.get("reasoning", "Analysis completed"),
                    confidence_score=float(data.get("confidenceScore", 0.7)),
                    recommendation=data.get("recommendation", "REVIEW"),
                    sar_required=bool(data.get("sarRequired", False)),
                    raw_response=response
                )
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse JSON response: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {str(e)}")
        
        # Fallback parsing for non-JSON responses
        return self._extract_from_text(response)
    
    def _extract_from_text(self, response: str) -> LLMAnalysisResult:
        """Extract analysis from unstructured text response"""
        
        text_lower = response.lower()
        
        # Estimate risk score from keywords
        risk_score = 30
        risk_keywords = {
            'critical': 30, 'severe': 25, 'high risk': 20, 'suspicious': 15,
            'concern': 10, 'elevated': 10, 'medium': 5, 'low risk': -10
        }
        
        for keyword, adjustment in risk_keywords.items():
            if keyword in text_lower:
                risk_score += adjustment
        
        risk_score = max(0, min(100, risk_score))
        
        # Determine risk level
        if risk_score >= 80:
            risk_level = "CRITICAL"
        elif risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Extract flagged issues
        issues = []
        issue_patterns = [
            r'red flag[s]?:?\s*([^\n]+)',
            r'concern[s]?:?\s*([^\n]+)',
            r'issue[s]?:?\s*([^\n]+)',
            r'risk[s]?:?\s*([^\n]+)'
        ]
        
        for pattern in issue_patterns:
            matches = re.findall(pattern, text_lower)
            issues.extend(matches)
        
        return LLMAnalysisResult(
            risk_score=risk_score,
            risk_level=risk_level,
            flagged_issues=issues[:5] if issues else ["Analysis completed - review response"],
            reasoning=response[:1000],
            confidence_score=0.5,
            recommendation="REVIEW",
            sar_required=risk_score >= 75,
            raw_response=response
        )
    
    def _rule_based_fallback(
        self,
        transaction: Dict[str, Any],
        customer: Dict[str, Any],
        rag_context: Optional[RAGContext] = None
    ) -> LLMAnalysisResult:
        """Rule-based fallback when LLM is unavailable"""
        
        risk_score = 0
        flagged_issues = []
        reasoning_parts = []
        
        # High-risk jurisdictions
        high_risk_countries = ['RU', 'IR', 'KP', 'SY', 'CU', 'VE', 'MM', 'BY']
        tax_havens = ['KY', 'VG', 'PA', 'CH', 'LI', 'MC', 'AD', 'BM', 'BS']
        
        origin = transaction.get("origin_country", "").upper()
        dest = transaction.get("destination_country", "").upper()
        amount = transaction.get("amount", 0)
        
        # Geographic risk
        if origin in high_risk_countries or dest in high_risk_countries:
            risk_score += 25
            flagged_issues.append("HIGH_RISK_JURISDICTION")
            reasoning_parts.append(f"Transaction involves high-risk jurisdiction")
        
        if dest in tax_havens:
            risk_score += 15
            flagged_issues.append("TAX_HAVEN_DESTINATION")
            reasoning_parts.append("Destination is a known tax haven")
        
        # Amount analysis
        if amount > 100000:
            risk_score += 15
            flagged_issues.append("LARGE_TRANSACTION")
            reasoning_parts.append(f"Large transaction amount: ${amount:,.2f}")
        
        if 9000 <= amount <= 10000:
            risk_score += 20
            flagged_issues.append("STRUCTURING_INDICATOR")
            reasoning_parts.append("Amount near reporting threshold - potential structuring")
        
        # Account age
        account_age = customer.get("account_age_days", 365)
        if account_age < 90:
            risk_score += 10
            flagged_issues.append("NEW_ACCOUNT")
            reasoning_parts.append(f"New account ({account_age} days old)")
        
        # RAG context
        if rag_context:
            if rag_context.adverse_media_found:
                risk_score += 25
                flagged_issues.append("ADVERSE_MEDIA_DETECTED")
                reasoning_parts.append("Adverse media found in background search")
            
            if rag_context.sanctions_indicators:
                risk_score += 30
                flagged_issues.append("SANCTIONS_INDICATOR")
                reasoning_parts.append(f"Sanctions keywords: {', '.join(rag_context.sanctions_indicators)}")
        
        risk_score = min(100, risk_score)
        
        # Determine risk level and recommendation
        if risk_score >= 80:
            risk_level = "CRITICAL"
            recommendation = "BLOCK"
        elif risk_score >= 60:
            risk_level = "HIGH"
            recommendation = "ESCALATE"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
            recommendation = "REVIEW"
        else:
            risk_level = "LOW"
            recommendation = "APPROVE"
        
        return LLMAnalysisResult(
            risk_score=risk_score,
            risk_level=risk_level,
            flagged_issues=flagged_issues,
            reasoning="\n".join(reasoning_parts) if reasoning_parts else "Standard transaction - no significant risks identified",
            confidence_score=0.85,
            recommendation=recommendation,
            sar_required=risk_score >= 75,
            raw_response="[Rule-based analysis - LLM unavailable]"
        )
    
    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()
