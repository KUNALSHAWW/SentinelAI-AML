"""
SentinelAI RAG Service
======================

Real-time web search and Retrieval-Augmented Generation (RAG) service
for enhanced AML entity due diligence and background checks.

Supports multiple search providers:
- Tavily (AI-optimized search)
- SerpAPI (Google Search)
- DuckDuckGo (Free, no API key)
"""

import os
import re
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
import httpx

from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Individual search result"""
    title: str
    url: str
    snippet: str
    source: str
    relevance_score: float = 0.0


@dataclass
class RAGContext:
    """Aggregated RAG context for LLM"""
    entity_name: str
    entity_type: str
    search_timestamp: str
    sources_searched: int
    results_found: int
    summary: str
    raw_results: List[SearchResult]
    adverse_media_found: bool
    sanctions_indicators: List[str]
    business_info: str
    key_findings: List[str]


class RAGService:
    """
    Retrieval-Augmented Generation Service for AML Due Diligence
    
    Performs real-time web searches to gather entity information,
    adverse media, and regulatory intelligence for enhanced analysis.
    """
    
    # Corporate entity indicators
    CORPORATE_INDICATORS = [
        'ltd', 'llc', 'inc', 'corp', 'corporation', 'limited', 
        'gmbh', 'plc', 'llp', 'lp', 'sa', 'ag', 'nv', 'bv',
        'company', 'co.', 'holdings', 'group', 'international',
        'enterprises', 'partners', 'investments', 'capital',
        'bank', 'financial', 'trust', 'fund', 'asset'
    ]
    
    # Adverse media keywords
    ADVERSE_KEYWORDS = [
        'money laundering', 'fraud', 'sanctions', 'terrorist financing',
        'corruption', 'bribery', 'tax evasion', 'embezzlement',
        'criminal', 'indicted', 'charged', 'convicted', 'investigation',
        'seized', 'frozen assets', 'shell company', 'offshore',
        'pep', 'politically exposed', 'illicit', 'smuggling',
        'trafficking', 'scandal', 'violation', 'penalty', 'fine'
    ]
    
    def __init__(self):
        self.logger = get_logger("service.rag")
        
        # API keys from environment/settings
        self.tavily_api_key = os.getenv('TAVILY_API_KEY')
        self.serpapi_key = os.getenv('SERPAPI_KEY')
        
        # HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        self.logger.info("RAG Service initialized")
    
    def is_corporate_entity(self, customer_name: str, customer_type: str = None) -> bool:
        """
        Determine if the customer represents a corporate entity
        requiring enhanced due diligence.
        """
        if customer_type and customer_type.upper() in ['CORPORATE', 'FINANCIAL_INSTITUTION']:
            return True
        
        name_lower = customer_name.lower()
        for indicator in self.CORPORATE_INDICATORS:
            if indicator in name_lower:
                return True
        
        return False
    
    async def search_entity(
        self,
        entity_name: str,
        entity_type: str = "CORPORATE",
        search_depth: str = "standard"
    ) -> RAGContext:
        """
        Perform comprehensive web search for entity information.
        
        Args:
            entity_name: Name of the entity to search
            entity_type: Type of entity (CORPORATE, INDIVIDUAL, FINANCIAL_INSTITUTION)
            search_depth: 'basic', 'standard', or 'deep'
        
        Returns:
            RAGContext with aggregated search results
        """
        self.logger.info(f"Starting RAG search for: {entity_name}")
        
        all_results: List[SearchResult] = []
        
        # Build search queries
        queries = self._build_search_queries(entity_name, entity_type)
        
        # Execute searches based on available providers
        for query in queries:
            try:
                if self.tavily_api_key:
                    results = await self._search_tavily(query)
                    all_results.extend(results)
                elif self.serpapi_key:
                    results = await self._search_serpapi(query)
                    all_results.extend(results)
                else:
                    # Fall back to DuckDuckGo (no API key required)
                    results = await self._search_duckduckgo(query)
                    all_results.extend(results)
            except Exception as e:
                self.logger.error(f"Search failed for query '{query}': {str(e)}")
        
        # Deduplicate and score results
        unique_results = self._deduplicate_results(all_results)
        scored_results = self._score_results(unique_results, entity_name)
        
        # Extract key information
        adverse_media = self._detect_adverse_media(scored_results)
        sanctions_indicators = self._extract_sanctions_indicators(scored_results)
        business_info = self._extract_business_info(scored_results, entity_name)
        key_findings = self._extract_key_findings(scored_results)
        
        # Generate summary
        summary = self._generate_summary(
            entity_name, 
            scored_results, 
            adverse_media,
            sanctions_indicators
        )
        
        return RAGContext(
            entity_name=entity_name,
            entity_type=entity_type,
            search_timestamp=datetime.utcnow().isoformat(),
            sources_searched=len(queries),
            results_found=len(scored_results),
            summary=summary,
            raw_results=scored_results[:20],  # Top 20 results
            adverse_media_found=adverse_media,
            sanctions_indicators=sanctions_indicators,
            business_info=business_info,
            key_findings=key_findings
        )
    
    def _build_search_queries(self, entity_name: str, entity_type: str) -> List[str]:
        """Build targeted search queries for the entity"""
        queries = []
        
        # Basic entity search
        queries.append(f'"{entity_name}"')
        
        # Business registration/nature
        queries.append(f'"{entity_name}" company registration business')
        
        # Adverse media search
        queries.append(f'"{entity_name}" money laundering fraud sanctions news')
        
        # Regulatory/compliance search
        queries.append(f'"{entity_name}" regulatory fine penalty violation')
        
        if entity_type == "FINANCIAL_INSTITUTION":
            queries.append(f'"{entity_name}" bank license financial services')
        
        # Key personnel search
        queries.append(f'"{entity_name}" CEO director management executives')
        
        return queries
    
    async def _search_tavily(self, query: str) -> List[SearchResult]:
        """Search using Tavily API (AI-optimized search)"""
        try:
            response = await self.http_client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "include_domains": [],
                    "exclude_domains": [],
                    "max_results": 10
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get("results", []):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("content", ""),
                        source="tavily",
                        relevance_score=item.get("score", 0.5)
                    ))
                return results
        except Exception as e:
            self.logger.error(f"Tavily search error: {str(e)}")
        
        return []
    
    async def _search_serpapi(self, query: str) -> List[SearchResult]:
        """Search using SerpAPI (Google Search)"""
        try:
            response = await self.http_client.get(
                "https://serpapi.com/search",
                params={
                    "api_key": self.serpapi_key,
                    "q": query,
                    "engine": "google",
                    "num": 10
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get("organic_results", []):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        source="serpapi",
                        relevance_score=0.5
                    ))
                return results
        except Exception as e:
            self.logger.error(f"SerpAPI search error: {str(e)}")
        
        return []
    
    async def _search_duckduckgo(self, query: str) -> List[SearchResult]:
        """Search using DuckDuckGo (no API key required)"""
        try:
            # Use DuckDuckGo HTML endpoint
            response = await self.http_client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            
            if response.status_code == 200:
                # Parse HTML response (simplified)
                results = []
                text = response.text
                
                # Extract result snippets (basic parsing)
                result_pattern = r'<a class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
                snippet_pattern = r'<a class="result__snippet"[^>]*>([^<]+)</a>'
                
                urls_titles = re.findall(result_pattern, text)
                snippets = re.findall(snippet_pattern, text)
                
                for i, (url, title) in enumerate(urls_titles[:10]):
                    snippet = snippets[i] if i < len(snippets) else ""
                    results.append(SearchResult(
                        title=title.strip(),
                        url=url,
                        snippet=snippet.strip(),
                        source="duckduckgo",
                        relevance_score=0.4
                    ))
                
                return results
        except Exception as e:
            self.logger.error(f"DuckDuckGo search error: {str(e)}")
        
        return []
    
    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results based on URL"""
        seen_urls = set()
        unique = []
        
        for result in results:
            normalized_url = result.url.lower().rstrip('/')
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique.append(result)
        
        return unique
    
    def _score_results(
        self, 
        results: List[SearchResult], 
        entity_name: str
    ) -> List[SearchResult]:
        """Score and sort results by relevance"""
        entity_words = set(entity_name.lower().split())
        
        for result in results:
            score = result.relevance_score
            
            text = f"{result.title} {result.snippet}".lower()
            
            # Boost for entity name match
            for word in entity_words:
                if word in text:
                    score += 0.1
            
            # Boost for adverse keywords
            for keyword in self.ADVERSE_KEYWORDS:
                if keyword in text:
                    score += 0.15
            
            # Boost for reputable sources
            reputable_domains = [
                'reuters.com', 'bloomberg.com', 'ft.com', 'wsj.com',
                'sec.gov', 'justice.gov', 'treasury.gov', 'fincen.gov',
                'ofac', 'fatf', 'worldbank.org', 'imf.org'
            ]
            for domain in reputable_domains:
                if domain in result.url.lower():
                    score += 0.2
                    break
            
            result.relevance_score = min(1.0, score)
        
        # Sort by score descending
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results
    
    def _detect_adverse_media(self, results: List[SearchResult]) -> bool:
        """Detect presence of adverse media"""
        for result in results:
            text = f"{result.title} {result.snippet}".lower()
            for keyword in self.ADVERSE_KEYWORDS:
                if keyword in text:
                    return True
        return False
    
    def _extract_sanctions_indicators(self, results: List[SearchResult]) -> List[str]:
        """Extract sanctions-related indicators"""
        indicators = []
        
        sanctions_keywords = [
            'ofac', 'sanctions', 'sanctioned', 'designated', 'blocked',
            'sdn list', 'treasury', 'embargo', 'restricted party'
        ]
        
        for result in results:
            text = f"{result.title} {result.snippet}".lower()
            for keyword in sanctions_keywords:
                if keyword in text and keyword not in indicators:
                    indicators.append(keyword)
        
        return indicators
    
    def _extract_business_info(
        self, 
        results: List[SearchResult],
        entity_name: str
    ) -> str:
        """Extract business nature and registration info"""
        info_parts = []
        
        for result in results[:10]:
            snippet = result.snippet.lower()
            
            # Look for business descriptions
            if any(term in snippet for term in [
                'provides', 'offers', 'specializes', 'engaged in',
                'operates', 'business of', 'services include',
                'founded', 'established', 'incorporated'
            ]):
                info_parts.append(result.snippet)
        
        if info_parts:
            return " | ".join(info_parts[:3])
        
        return f"Limited public information available for {entity_name}"
    
    def _extract_key_findings(self, results: List[SearchResult]) -> List[str]:
        """Extract key findings from search results"""
        findings = []
        
        for result in results[:15]:
            text = f"{result.title} {result.snippet}".lower()
            
            # Regulatory actions
            if any(term in text for term in ['fine', 'penalty', 'settlement', 'enforcement']):
                findings.append(f"Regulatory mention: {result.title}")
            
            # Legal issues
            if any(term in text for term in ['lawsuit', 'litigation', 'charged', 'indicted']):
                findings.append(f"Legal issue: {result.title}")
            
            # Sanctions
            if any(term in text for term in ['sanctions', 'ofac', 'sdn']):
                findings.append(f"Sanctions mention: {result.title}")
            
            # Adverse news
            if any(term in text for term in ['fraud', 'money laundering', 'scandal']):
                findings.append(f"Adverse news: {result.title}")
        
        return findings[:10]
    
    def _generate_summary(
        self,
        entity_name: str,
        results: List[SearchResult],
        adverse_media: bool,
        sanctions_indicators: List[str]
    ) -> str:
        """Generate a summary of search findings"""
        summary_parts = []
        
        summary_parts.append(f"RAG Search Summary for: {entity_name}")
        summary_parts.append(f"Total results analyzed: {len(results)}")
        
        if adverse_media:
            summary_parts.append(
                "⚠️ ADVERSE MEDIA DETECTED: Potential negative news found in search results."
            )
        else:
            summary_parts.append(
                "✓ No significant adverse media detected in initial search."
            )
        
        if sanctions_indicators:
            summary_parts.append(
                f"⚠️ SANCTIONS INDICATORS: Keywords found - {', '.join(sanctions_indicators)}"
            )
        
        # Add top source domains
        domains = set()
        for r in results[:10]:
            try:
                domain = r.url.split('/')[2]
                domains.add(domain)
            except:
                pass
        
        if domains:
            summary_parts.append(f"Sources consulted: {', '.join(list(domains)[:5])}")
        
        return "\n".join(summary_parts)
    
    def format_context_for_llm(self, rag_context: RAGContext) -> str:
        """
        Format RAG context for injection into LLM prompt.
        
        Returns a clean, structured text representation of the search results.
        """
        lines = []
        
        lines.append("=" * 60)
        lines.append("ENTITY BACKGROUND RESEARCH (RAG)")
        lines.append("=" * 60)
        lines.append(f"Entity: {rag_context.entity_name}")
        lines.append(f"Type: {rag_context.entity_type}")
        lines.append(f"Search Timestamp: {rag_context.search_timestamp}")
        lines.append(f"Sources Analyzed: {rag_context.results_found}")
        lines.append("")
        
        lines.append("--- RISK INDICATORS ---")
        lines.append(f"Adverse Media Found: {'YES ⚠️' if rag_context.adverse_media_found else 'NO ✓'}")
        
        if rag_context.sanctions_indicators:
            lines.append(f"Sanctions Keywords: {', '.join(rag_context.sanctions_indicators)}")
        
        lines.append("")
        lines.append("--- BUSINESS INFORMATION ---")
        lines.append(rag_context.business_info)
        
        if rag_context.key_findings:
            lines.append("")
            lines.append("--- KEY FINDINGS ---")
            for finding in rag_context.key_findings:
                lines.append(f"• {finding}")
        
        lines.append("")
        lines.append("--- TOP SEARCH RESULTS ---")
        for i, result in enumerate(rag_context.raw_results[:5], 1):
            lines.append(f"\n[{i}] {result.title}")
            lines.append(f"    Source: {result.url}")
            lines.append(f"    {result.snippet[:200]}...")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()
