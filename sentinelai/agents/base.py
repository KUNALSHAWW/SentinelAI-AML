"""
SentinelAI Base Agent
=====================

Base class for all LangGraph agents with common functionality.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, TypeVar, Generic
from datetime import datetime
import asyncio
import re

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models import BaseChatModel

from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger
from sentinelai.agents.prompts import PromptTemplates

logger = get_logger(__name__)

# Type variable for state
StateT = TypeVar("StateT", bound=Dict[str, Any])


class LLMFactory:
    """Factory for creating LLM instances based on configuration"""
    
    _instance: Optional[BaseChatModel] = None
    
    @classmethod
    def get_llm(cls, force_new: bool = False) -> BaseChatModel:
        """Get or create LLM instance"""
        
        if cls._instance is not None and not force_new:
            return cls._instance
        
        provider = settings.llm.provider
        
        if provider == "groq":
            from langchain_groq import ChatGroq
            
            cls._instance = ChatGroq(
                model=settings.llm.groq_model,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
                timeout=settings.llm.timeout,
                max_retries=settings.llm.max_retries,
                api_key=settings.llm.groq_api_key.get_secret_value() if settings.llm.groq_api_key else None,
            )
            logger.info(f"Initialized Groq LLM with model: {settings.llm.groq_model}")
            
        elif provider == "huggingface":
            from langchain_huggingface import HuggingFaceEndpoint
            
            cls._instance = HuggingFaceEndpoint(
                repo_id=settings.llm.huggingface_model,
                temperature=settings.llm.temperature,
                max_new_tokens=settings.llm.max_tokens,
                huggingfacehub_api_token=settings.llm.huggingface_api_key.get_secret_value() if settings.llm.huggingface_api_key else None,
            )
            logger.info(f"Initialized HuggingFace LLM with model: {settings.llm.huggingface_model}")
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        
        return cls._instance


class BaseAgent(ABC, Generic[StateT]):
    """
    Base agent class for all SentinelAI agents.
    
    Provides common functionality for:
    - LLM interaction
    - State management
    - Logging and metrics
    - Error handling
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        llm: Optional[BaseChatModel] = None
    ):
        self.name = name
        self.description = description
        self.llm = llm or LLMFactory.get_llm()
        self.logger = get_logger(f"agent.{name}")
        
        # Metrics
        self._invocation_count = 0
        self._total_latency_ms = 0
        self._error_count = 0
    
    @abstractmethod
    async def process(self, state: StateT) -> StateT:
        """
        Process the state and return updated state.
        Must be implemented by subclasses.
        """
        pass
    
    async def invoke_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        parse_structured: bool = False
    ) -> str:
        """
        Invoke the LLM with the given prompt.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            parse_structured: Whether to parse structured output
            
        Returns:
            The LLM response content
        """
        start_time = datetime.utcnow()
        
        try:
            messages = []
            
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            else:
                messages.append(SystemMessage(content=PromptTemplates.SYSTEM_AML_EXPERT))
            
            messages.append(HumanMessage(content=prompt))
            
            response = await self.llm.ainvoke(messages)
            
            # Update metrics
            self._invocation_count += 1
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._total_latency_ms += latency
            
            self.logger.debug(
                f"LLM invocation completed",
                extra={
                    "latency_ms": latency,
                    "prompt_length": len(prompt),
                    "response_length": len(response.content)
                }
            )
            
            return response.content
            
        except Exception as e:
            self._error_count += 1
            self.logger.error(f"LLM invocation failed: {str(e)}")
            raise
    
    def extract_risk_codes(self, text: str) -> List[str]:
        """Extract risk codes from LLM response (UPPER_CASE_CODES)"""
        pattern = r"\b[A-Z][A-Z_]{3,}[A-Z]\b"
        codes = re.findall(pattern, text)
        # Filter out common words that might match
        excluded = {"THE", "AND", "FOR", "NOT", "BUT", "FROM", "WITH", "THIS", "THAT", "WHEN", "WHERE"}
        return [code for code in codes if code not in excluded]
    
    def extract_score(self, text: str, default: int = 0) -> int:
        """Extract risk score from LLM response"""
        patterns = [
            r"(?:risk\s*score|score)[:\s]*(\d{1,3})",
            r"(\d{1,3})\s*/\s*100",
            r"RISK_SCORE[:\s]*(\d{1,3})",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                score = int(match.group(1))
                return min(100, max(0, score))  # Clamp to 0-100
        
        return default
    
    def extract_risk_level(self, text: str) -> str:
        """Extract risk level from LLM response"""
        text_upper = text.upper()
        
        if "CRITICAL" in text_upper:
            return "CRITICAL"
        elif "HIGH" in text_upper and "RISK" in text_upper:
            return "HIGH"
        elif "MEDIUM" in text_upper:
            return "MEDIUM"
        elif "LOW" in text_upper and "RISK" in text_upper:
            return "LOW"
        
        return "MEDIUM"  # Default
    
    def extract_confidence(self, text: str, default: float = 0.5) -> float:
        """Extract confidence score from LLM response"""
        patterns = [
            r"confidence[:\s]*([\d.]+)",
            r"([\d.]+)\s*confidence",
            r"CONFIDENCE[:\s]*([\d.]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    score = float(match.group(1))
                    # Handle percentage vs decimal
                    if score > 1:
                        score = score / 100
                    return min(1.0, max(0.0, score))
                except ValueError:
                    continue
        
        return default
    
    def update_decision_path(self, state: StateT, step: str) -> StateT:
        """Add a step to the decision path"""
        path = state.get("decision_path", [])
        if not isinstance(path, list):
            path = []
        return {**state, "decision_path": path + [f"{self.name}:{step}"]}
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics"""
        avg_latency = (
            self._total_latency_ms / self._invocation_count 
            if self._invocation_count > 0 else 0
        )
        
        return {
            "agent_name": self.name,
            "invocation_count": self._invocation_count,
            "average_latency_ms": avg_latency,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(1, self._invocation_count)
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
