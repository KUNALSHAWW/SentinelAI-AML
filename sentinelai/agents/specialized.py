"""
SentinelAI Specialized Agents
=============================

Individual specialized agents for different aspects of AML analysis.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import statistics

from sentinelai.agents.base import BaseAgent
from sentinelai.agents.prompts import PromptTemplates
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)


class AMLState(Dict[str, Any]):
    """
    Enhanced AML State Definition
    
    This TypedDict-like class defines the complete state structure
    that flows through the LangGraph workflow.
    """
    
    @classmethod
    def create_initial(
        cls,
        transaction: Dict[str, Any],
        customer: Dict[str, Any]
    ) -> "AMLState":
        """Create initial state from transaction and customer data"""
        return cls({
            # Input Data
            "transaction": transaction,
            "customer": customer,
            
            # Risk Assessment
            "risk_score": 0,
            "risk_level": "LOW",
            "risk_factors": [],
            "alerts": [],
            
            # Analysis Results
            "llm_analysis": {},
            "investigation": {},
            
            # Screening Results
            "pep_status": None,
            "pep_details": None,
            "sanction_hits": [],
            "sanction_details": [],
            
            # Document Analysis
            "documents": transaction.get("documents", []),
            "document_analysis": {},
            
            # Network Analysis
            "network_analysis": {},
            "related_entities": [],
            
            # Decision Tracking
            "decision_path": [],
            "routing_decisions": [],
            
            # Case Management
            "case_id": None,
            "reporting_status": None,
            "sar_required": False,
            "sar_narrative": None,
            
            # Metadata
            "processing_start": datetime.utcnow().isoformat(),
            "processing_steps": [],
            "errors": [],
            
            # Transaction count for velocity
            "transaction_count": len(customer.get("transaction_history", [])),
        })


class GeographicRiskAgent(BaseAgent[AMLState]):
    """Agent for geographic/jurisdiction risk assessment"""
    
    def __init__(self):
        super().__init__(
            name="geographic_risk",
            description="Analyzes geographic risks including high-risk countries and tax havens"
        )
        
        self.high_risk_countries = set(settings.risk.high_risk_countries)
        self.tax_havens = set(settings.risk.tax_havens)
        self.grey_list_countries = set(settings.risk.grey_list_countries)
    
    async def process(self, state: AMLState) -> AMLState:
        """Analyze geographic risk factors"""
        state = self.update_decision_path(state, "start")
        
        tx = state["transaction"]
        risk_factors = []
        alerts = []
        geo_score = 0
        
        # Collect all jurisdictions
        jurisdictions = []
        
        if tx.get("origin_country"):
            jurisdictions.append(("origin", tx["origin_country"]))
        if tx.get("destination_country"):
            jurisdictions.append(("destination", tx["destination_country"]))
        for country in tx.get("intermediate_countries", []):
            jurisdictions.append(("intermediate", country))
        
        # Analyze each jurisdiction
        geo_details = []
        
        for role, country in jurisdictions:
            country = country.upper()
            
            if country in self.high_risk_countries:
                risk_factors.append(f"HIGH_RISK_JURISDICTION_{country}")
                alerts.append(f"HIGH_RISK_JURISDICTION: {country} ({role})")
                geo_score += 25
                geo_details.append({
                    "country": country,
                    "role": role,
                    "risk_type": "HIGH_RISK",
                    "score_contribution": 25
                })
            
            elif country in self.tax_havens:
                risk_factors.append(f"TAX_HAVEN_{country}")
                geo_score += 15
                geo_details.append({
                    "country": country,
                    "role": role,
                    "risk_type": "TAX_HAVEN",
                    "score_contribution": 15
                })
            
            elif country in self.grey_list_countries:
                risk_factors.append(f"GREY_LIST_{country}")
                geo_score += 10
                geo_details.append({
                    "country": country,
                    "role": role,
                    "risk_type": "GREY_LIST",
                    "score_contribution": 10
                })
        
        # Check for suspicious routing
        intermediates = tx.get("intermediate_countries", [])
        if len(intermediates) >= 2:
            risk_factors.append("COMPLEX_ROUTING")
            geo_score += 10
        
        # Check for tax haven chain
        tax_haven_count = sum(1 for _, c in jurisdictions if c in self.tax_havens)
        if tax_haven_count >= 2:
            risk_factors.append("TAX_HAVEN_CHAIN")
            alerts.append("Multiple tax havens in transaction path")
            geo_score += 20
        
        state = self.update_decision_path(state, "complete")
        
        return {
            **state,
            "risk_factors": state["risk_factors"] + risk_factors,
            "alerts": state["alerts"] + alerts,
            "llm_analysis": {
                **state.get("llm_analysis", {}),
                "geographic_risk": {
                    "score": min(50, geo_score),  # Cap geo score at 50
                    "jurisdictions_analyzed": len(jurisdictions),
                    "details": geo_details
                }
            }
        }


class BehavioralAnalysisAgent(BaseAgent[AMLState]):
    """Agent for behavioral pattern analysis"""
    
    def __init__(self):
        super().__init__(
            name="behavioral_analysis",
            description="Analyzes transaction patterns for structuring and velocity anomalies"
        )
        
        self.structuring_threshold = settings.risk.structuring_threshold
        self.max_daily_transactions = settings.risk.max_daily_transactions
        self.max_daily_amount = settings.risk.max_daily_amount
    
    async def process(self, state: AMLState) -> AMLState:
        """Analyze behavioral patterns"""
        state = self.update_decision_path(state, "start")
        
        tx = state["transaction"]
        customer = state["customer"]
        history = customer.get("transaction_history", [])
        current_amount = tx.get("amount", 0)
        
        risk_factors = []
        alerts = []
        behavioral_score = 0
        
        # Convert current timestamp
        current_ts = tx.get("timestamp")
        if isinstance(current_ts, str):
            current_ts = datetime.fromisoformat(current_ts.replace("Z", "+00:00"))
        elif not isinstance(current_ts, datetime):
            current_ts = datetime.utcnow()
        
        # Structuring Detection
        if 9000 <= current_amount < 10000:
            risk_factors.append("POTENTIAL_STRUCTURING")
            alerts.append(f"Transaction amount ${current_amount:,.2f} just below $10,000 threshold")
            behavioral_score += 20
        
        # Analyze recent transaction history
        recent_txs = []
        for htx in history:
            htx_ts = htx.get("timestamp")
            if isinstance(htx_ts, str):
                htx_ts = datetime.fromisoformat(htx_ts.replace("Z", "+00:00"))
            elif not isinstance(htx_ts, datetime):
                continue
            
            # Check if within 24 hours
            if hasattr(current_ts, 'timestamp') and hasattr(htx_ts, 'timestamp'):
                delta = abs((current_ts - htx_ts).total_seconds())
                if delta < 86400:  # 24 hours
                    recent_txs.append(htx)
        
        # Velocity analysis
        if len(recent_txs) >= self.max_daily_transactions - 1:
            risk_factors.append("HIGH_VELOCITY")
            alerts.append(f"{len(recent_txs) + 1} transactions in 24 hours")
            behavioral_score += 15
        
        # Daily amount analysis
        daily_total = sum(t.get("amount", 0) for t in recent_txs) + current_amount
        if daily_total > self.max_daily_amount:
            risk_factors.append("DAILY_LIMIT_EXCEEDED")
            alerts.append(f"Daily volume ${daily_total:,.2f} exceeds threshold")
            behavioral_score += 15
        
        # Pattern detection (uniform amounts)
        all_amounts = [t.get("amount", 0) for t in recent_txs] + [current_amount]
        if len(all_amounts) >= 3:
            try:
                std_dev = statistics.stdev(all_amounts)
                mean_amount = statistics.mean(all_amounts)
                
                # Check for uniform transactions (low variance relative to mean)
                if mean_amount > 0 and std_dev / mean_amount < 0.1:
                    risk_factors.append("UNIFORM_TRANSACTION_PATTERN")
                    behavioral_score += 15
                
                # Check for structuring pattern (all just below threshold)
                if all(9000 <= a < 10000 for a in all_amounts):
                    risk_factors.append("STRUCTURING_PATTERN")
                    alerts.append("Multiple transactions just below $10,000 threshold")
                    behavioral_score += 30
            except statistics.StatisticsError:
                pass
        
        # New account with high activity
        account_age = customer.get("account_age_days", 0)
        if account_age < settings.risk.new_account_days:
            if current_amount > settings.risk.large_transaction_threshold:
                risk_factors.append("NEW_ACCOUNT_HIGH_VALUE")
                alerts.append(f"High-value transaction on {account_age}-day-old account")
                behavioral_score += 20
            
            if len(recent_txs) >= 3:
                risk_factors.append("NEW_ACCOUNT_HIGH_VELOCITY")
                behavioral_score += 15
        
        # Round amount detection
        if current_amount >= 10000 and current_amount % 1000 == 0:
            risk_factors.append("ROUND_AMOUNT")
            behavioral_score += 5
        
        state = self.update_decision_path(state, "complete")
        
        return {
            **state,
            "risk_factors": state["risk_factors"] + risk_factors,
            "alerts": state["alerts"] + alerts,
            "llm_analysis": {
                **state.get("llm_analysis", {}),
                "behavioral_analysis": {
                    "score": min(50, behavioral_score),
                    "transactions_in_24h": len(recent_txs) + 1,
                    "daily_volume": daily_total,
                    "patterns_detected": risk_factors
                }
            }
        }


class CryptoRiskAgent(BaseAgent[AMLState]):
    """Agent for cryptocurrency-specific risk analysis"""
    
    KNOWN_MIXERS = ["tornado", "wasabi", "samourai", "chipmixer", "blender"]
    KNOWN_DARKNET = ["hydra", "alphabay", "dark0de", "versus", "world market"]
    
    def __init__(self):
        super().__init__(
            name="crypto_risk",
            description="Analyzes cryptocurrency-specific risks including mixers and darknet associations"
        )
    
    async def process(self, state: AMLState) -> AMLState:
        """Analyze cryptocurrency-specific risks"""
        tx = state["transaction"]
        
        # Skip if not a crypto transaction
        if tx.get("asset_type") != "CRYPTO" and tx.get("transaction_type") != "CRYPTO":
            return state
        
        state = self.update_decision_path(state, "start")
        
        crypto_details = tx.get("crypto_details", {})
        risk_factors = []
        alerts = []
        crypto_score = 0
        
        # Mixer detection
        if crypto_details.get("mixer_used"):
            risk_factors.append("CRYPTO_MIXER_DETECTED")
            alerts.append("Cryptocurrency mixing service detected")
            crypto_score += 35
        
        # Darknet association
        darknet = crypto_details.get("darknet_market", "")
        if darknet:
            if any(dn in darknet.lower() for dn in self.KNOWN_DARKNET):
                risk_factors.append("DARKNET_MARKET_ASSOCIATION")
                alerts.append(f"Darknet market association: {darknet}")
                crypto_score += 40
        
        # New wallet risk
        wallet_age = crypto_details.get("wallet_age_days", 365)
        if wallet_age < 7:
            risk_factors.append("NEW_CRYPTO_WALLET")
            crypto_score += 15
        elif wallet_age < 30:
            risk_factors.append("RECENT_CRYPTO_WALLET")
            crypto_score += 10
        
        # Cross-chain swaps (potential layering)
        swaps = crypto_details.get("cross_chain_swaps", 0)
        if swaps >= 3:
            risk_factors.append("CRYPTO_LAYERING_PATTERN")
            alerts.append(f"{swaps} cross-chain swaps detected")
            crypto_score += 20
        elif swaps >= 1:
            risk_factors.append("CROSS_CHAIN_ACTIVITY")
            crypto_score += 10
        
        # Privacy coin conversion
        if crypto_details.get("privacy_coin"):
            risk_factors.append("PRIVACY_COIN_USAGE")
            alerts.append("Privacy coin conversion detected")
            crypto_score += 25
        
        # High-value crypto
        amount = tx.get("amount", 0)
        if amount > 100000:
            risk_factors.append("HIGH_VALUE_CRYPTO")
            crypto_score += 10
        
        # Use LLM for deeper analysis if significant crypto risks
        llm_crypto_analysis = None
        if crypto_score >= 25:
            try:
                prompt = PromptTemplates.format_template(
                    "CRYPTO_ANALYSIS",
                    crypto_details=str(crypto_details)
                )
                response = await self.invoke_llm(prompt)
                
                # Extract additional codes from LLM
                llm_codes = self.extract_risk_codes(response)
                for code in llm_codes:
                    if code.startswith("CRYPTO_") and code not in risk_factors:
                        risk_factors.append(code)
                
                llm_crypto_analysis = {
                    "analysis": response,
                    "additional_indicators": llm_codes,
                    "confidence": self.extract_confidence(response)
                }
            except Exception as e:
                self.logger.warning(f"LLM crypto analysis failed: {e}")
        
        state = self.update_decision_path(state, "complete")
        
        return {
            **state,
            "risk_factors": state["risk_factors"] + risk_factors,
            "alerts": state["alerts"] + alerts,
            "llm_analysis": {
                **state.get("llm_analysis", {}),
                "crypto_risk": {
                    "score": min(50, crypto_score),
                    "details": crypto_details,
                    "llm_analysis": llm_crypto_analysis
                }
            }
        }


class SanctionsScreeningAgent(BaseAgent[AMLState]):
    """Agent for sanctions list screening"""
    
    # Sample sanctioned entities (in production, this would be a database)
    SAMPLE_SANCTIONS = [
        "sanctioned_russian_bank",
        "terror_group_abc",
        "narcotics_cartel_xyz",
        "north_korea_trading",
        "iran_shipping_co",
    ]
    
    def __init__(self):
        super().__init__(
            name="sanctions_screening",
            description="Screens transactions against sanctions lists (OFAC, EU, UN)"
        )
    
    async def process(self, state: AMLState) -> AMLState:
        """Screen parties against sanctions lists"""
        state = self.update_decision_path(state, "start")
        
        tx = state["transaction"]
        parties = tx.get("parties", [])
        
        sanction_hits = []
        sanction_details = []
        alerts = []
        
        for party in parties:
            party_lower = party.lower()
            
            # Check against known sanctions (simplified)
            for sanctioned in self.SAMPLE_SANCTIONS:
                if sanctioned in party_lower or party_lower in sanctioned:
                    sanction_hits.append(party)
                    sanction_details.append({
                        "entity": party,
                        "list": "OFAC_SDN",
                        "match_type": "EXACT" if sanctioned == party_lower else "PARTIAL",
                        "confidence": 0.95 if sanctioned == party_lower else 0.75
                    })
                    alerts.append(f"SANCTIONS HIT: {party} matched against OFAC SDN list")
                    break
            
            # Check for country-based sanctions
            origin = tx.get("origin_country", "")
            if origin in ["IR", "KP", "SY", "CU"]:
                if any(kw in party_lower for kw in ["iran", "korea", "syria", "cuba"]):
                    sanction_hits.append(party)
                    sanction_details.append({
                        "entity": party,
                        "list": "COUNTRY_SANCTIONS",
                        "match_type": "JURISDICTION",
                        "confidence": 0.8
                    })
        
        # Use LLM for sophisticated screening if parties exist
        llm_screening = None
        if parties and len(parties) > 0:
            try:
                prompt = PromptTemplates.format_template(
                    "SANCTIONS_SCREENING",
                    entity_name=", ".join(parties),
                    aliases="N/A",
                    country=tx.get("origin_country", "Unknown"),
                    identifiers="N/A"
                )
                response = await self.invoke_llm(prompt)
                
                # Parse LLM response for additional indicators
                if "MATCH" in response.upper() and "NO_MATCH" not in response.upper():
                    sanc_codes = self.extract_risk_codes(response)
                    llm_screening = {
                        "analysis": response,
                        "risk_codes": sanc_codes,
                        "confidence": self.extract_confidence(response)
                    }
            except Exception as e:
                self.logger.warning(f"LLM sanctions screening failed: {e}")
        
        state = self.update_decision_path(state, "complete")
        
        return {
            **state,
            "sanction_hits": state.get("sanction_hits", []) + sanction_hits,
            "sanction_details": sanction_details,
            "alerts": state["alerts"] + alerts,
            "risk_factors": state["risk_factors"] + (
                ["SANCTIONS_HIT"] if sanction_hits else []
            ),
            "llm_analysis": {
                **state.get("llm_analysis", {}),
                "sanctions_screening": {
                    "parties_screened": len(parties),
                    "hits": len(sanction_hits),
                    "details": sanction_details,
                    "llm_analysis": llm_screening
                }
            }
        }


class PEPScreeningAgent(BaseAgent[AMLState]):
    """Agent for Politically Exposed Person screening"""
    
    PEP_KEYWORDS = [
        "minister", "gov", "official", "president", "senator",
        "ambassador", "military", "general", "director", "secretary",
        "parliament", "congress", "royal", "prince", "king", "queen"
    ]
    
    def __init__(self):
        super().__init__(
            name="pep_screening",
            description="Screens customers for Politically Exposed Person status"
        )
    
    async def process(self, state: AMLState) -> AMLState:
        """Screen customer for PEP status"""
        state = self.update_decision_path(state, "start")
        
        customer = state["customer"]
        name = customer.get("name", "").lower()
        
        pep_status = False
        pep_details = None
        risk_factors = []
        alerts = []
        
        # Simple keyword-based PEP detection
        matched_keywords = [kw for kw in self.PEP_KEYWORDS if kw in name]
        
        if matched_keywords:
            pep_status = True
            pep_details = {
                "match_type": "KEYWORD",
                "matched_terms": matched_keywords,
                "customer_name": customer.get("name"),
                "confidence": 0.7
            }
            risk_factors.append("PEP_MATCH")
            alerts.append(f"PEP indicator: Customer name contains '{', '.join(matched_keywords)}'")
        
        # Use LLM for sophisticated PEP analysis
        try:
            prompt = PromptTemplates.format_template(
                "PEP_SCREENING",
                name=customer.get("name", "Unknown"),
                nationality=customer.get("nationality", "Unknown"),
                organizations=customer.get("occupation", "Unknown"),
                position="Unknown"
            )
            response = await self.invoke_llm(prompt)
            
            # Check LLM response for PEP indicators
            response_upper = response.upper()
            if "PEP" in response_upper and "NOT" not in response_upper.split("PEP")[0][-10:]:
                if not pep_status:
                    pep_status = True
                    pep_details = {
                        "match_type": "LLM_ANALYSIS",
                        "analysis": response,
                        "confidence": self.extract_confidence(response, 0.6)
                    }
                    risk_factors.append("PEP_MATCH")
                else:
                    pep_details["llm_analysis"] = response
                    pep_details["confidence"] = max(
                        pep_details.get("confidence", 0.7),
                        self.extract_confidence(response, 0.6)
                    )
            
            # Extract additional risk codes
            pep_codes = [c for c in self.extract_risk_codes(response) if "PEP" in c]
            risk_factors.extend([c for c in pep_codes if c not in risk_factors])
            
        except Exception as e:
            self.logger.warning(f"LLM PEP screening failed: {e}")
        
        state = self.update_decision_path(state, "complete")
        
        return {
            **state,
            "pep_status": pep_status,
            "pep_details": pep_details,
            "risk_factors": state["risk_factors"] + risk_factors,
            "alerts": state["alerts"] + alerts,
            "llm_analysis": {
                **state.get("llm_analysis", {}),
                "pep_screening": {
                    "pep_status": pep_status,
                    "details": pep_details
                }
            }
        }


class DocumentAnalysisAgent(BaseAgent[AMLState]):
    """Agent for document analysis and verification"""
    
    def __init__(self):
        super().__init__(
            name="document_analysis",
            description="Analyzes documents for trade-based laundering and anomalies"
        )
    
    async def process(self, state: AMLState) -> AMLState:
        """Analyze transaction documents"""
        documents = state.get("documents", [])
        
        if not documents:
            state = self.update_decision_path(state, "skipped_no_docs")
            return {
                **state,
                "alerts": state["alerts"] + ["MISSING_DOCUMENTATION"],
                "risk_factors": state["risk_factors"] + ["NO_SUPPORTING_DOCS"]
            }
        
        state = self.update_decision_path(state, "start")
        
        tx = state["transaction"]
        risk_factors = []
        alerts = []
        
        # Use LLM for document analysis
        try:
            prompt = PromptTemplates.format_template(
                "DOCUMENT_ANALYSIS",
                documents="\n".join(f"- {doc}" for doc in documents),
                amount=tx.get("amount", 0),
                parties=", ".join(tx.get("parties", [])),
                origin_country=tx.get("origin_country", "Unknown"),
                destination_country=tx.get("destination_country", "Unknown")
            )
            
            response = await self.invoke_llm(prompt)
            
            # Extract risk codes from response
            doc_codes = self.extract_risk_codes(response)
            tbml_codes = [c for c in doc_codes if c.startswith(("TBML_", "DOC_", "INVOICE"))]
            
            risk_factors.extend(tbml_codes)
            
            if tbml_codes:
                alerts.append(f"Document analysis flags: {', '.join(tbml_codes)}")
            
            doc_analysis = {
                "documents_reviewed": len(documents),
                "llm_analysis": response,
                "risk_codes": tbml_codes,
                "confidence": self.extract_confidence(response),
                "score": self.extract_score(response, 0)
            }
            
        except Exception as e:
            self.logger.warning(f"LLM document analysis failed: {e}")
            doc_analysis = {
                "documents_reviewed": len(documents),
                "error": str(e)
            }
        
        state = self.update_decision_path(state, "complete")
        
        return {
            **state,
            "risk_factors": state["risk_factors"] + risk_factors,
            "alerts": state["alerts"] + alerts,
            "document_analysis": doc_analysis,
            "llm_analysis": {
                **state.get("llm_analysis", {}),
                "document_analysis": doc_analysis
            }
        }


class EnhancedDueDiligenceAgent(BaseAgent[AMLState]):
    """Agent for enhanced due diligence using CoT reasoning"""
    
    def __init__(self):
        super().__init__(
            name="enhanced_due_diligence",
            description="Performs comprehensive due diligence using Chain-of-Thought reasoning"
        )
    
    async def process(self, state: AMLState) -> AMLState:
        """Perform enhanced due diligence"""
        state = self.update_decision_path(state, "start")
        
        # Build comprehensive context
        context = {
            "transaction": state["transaction"],
            "customer": state["customer"],
            "risk_factors": state["risk_factors"],
            "alerts": state["alerts"],
            "pep_status": state.get("pep_status"),
            "sanction_hits": state.get("sanction_hits", []),
            "previous_analysis": state.get("llm_analysis", {})
        }
        
        try:
            # Use Chain-of-Thought prompt
            prompt = PromptTemplates.build_cot_analysis_prompt(
                state["transaction"],
                state["customer"]
            )
            
            # Add context from previous analysis
            prompt += f"\n\n**Previous Analysis Results:**\n{str(context['previous_analysis'])}"
            prompt += f"\n\n**Current Risk Factors:** {', '.join(state['risk_factors'])}"
            prompt += f"\n\n**Current Alerts:** {', '.join(state['alerts'])}"
            
            response = await self.invoke_llm(prompt)
            
            # Extract comprehensive results
            edd_codes = self.extract_risk_codes(response)
            edd_score = self.extract_score(response, 50)
            edd_confidence = self.extract_confidence(response)
            edd_level = self.extract_risk_level(response)
            
            edd_analysis = {
                "full_analysis": response,
                "risk_codes": edd_codes,
                "score": edd_score,
                "confidence": edd_confidence,
                "recommended_level": edd_level
            }
            
            # Add new risk factors
            new_factors = [c for c in edd_codes if c not in state["risk_factors"]]
            
        except Exception as e:
            self.logger.error(f"EDD analysis failed: {e}")
            edd_analysis = {"error": str(e)}
            new_factors = []
        
        state = self.update_decision_path(state, "complete")
        
        return {
            **state,
            "risk_factors": state["risk_factors"] + new_factors,
            "llm_analysis": {
                **state.get("llm_analysis", {}),
                "enhanced_due_diligence": edd_analysis
            }
        }


class RiskScoringAgent(BaseAgent[AMLState]):
    """Agent for comprehensive risk scoring"""
    
    # Risk factor weights
    WEIGHTS = {
        "SANCTIONS": 40,
        "PEP": 25,
        "CRYPTO_MIXER": 30,
        "DARKNET": 35,
        "HIGH_RISK": 20,
        "TAX_HAVEN": 15,
        "STRUCTURING": 25,
        "VELOCITY": 15,
        "TBML": 20,
        "DOC": 15,
        "NEW_ACCOUNT": 10,
    }
    
    def __init__(self):
        super().__init__(
            name="risk_scoring",
            description="Calculates comprehensive risk score from all factors"
        )
    
    async def process(self, state: AMLState) -> AMLState:
        """Calculate final risk score"""
        state = self.update_decision_path(state, "start")
        
        score = 0
        score_breakdown = {}
        
        # Score from sanctions
        if state.get("sanction_hits"):
            sanction_score = len(state["sanction_hits"]) * self.WEIGHTS["SANCTIONS"]
            score += sanction_score
            score_breakdown["sanctions"] = sanction_score
        
        # Score from PEP
        if state.get("pep_status"):
            score += self.WEIGHTS["PEP"]
            score_breakdown["pep"] = self.WEIGHTS["PEP"]
        
        # Score from risk factors
        for factor in state.get("risk_factors", []):
            factor_upper = factor.upper()
            
            for key, weight in self.WEIGHTS.items():
                if key in factor_upper:
                    score += weight
                    score_breakdown[factor] = score_breakdown.get(factor, 0) + weight
                    break
        
        # Get scores from previous analysis
        llm_analysis = state.get("llm_analysis", {})
        
        for analysis_key, analysis in llm_analysis.items():
            if isinstance(analysis, dict) and "score" in analysis:
                component_score = min(30, analysis["score"])  # Cap component scores
                score += component_score
                score_breakdown[analysis_key] = component_score
        
        # Normalize to 0-100
        final_score = min(100, score)
        
        # Determine risk level
        if final_score >= settings.risk.critical_risk_threshold:
            risk_level = "CRITICAL"
        elif final_score >= settings.risk.high_risk_threshold:
            risk_level = "HIGH"
        elif final_score >= settings.risk.medium_risk_threshold:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Determine SAR requirement
        sar_required = (
            final_score >= settings.risk.high_risk_threshold or
            bool(state.get("sanction_hits")) or
            (state.get("pep_status") and final_score >= settings.risk.medium_risk_threshold)
        )
        
        state = self.update_decision_path(state, "complete")
        
        return {
            **state,
            "risk_score": final_score,
            "risk_level": risk_level,
            "sar_required": sar_required,
            "llm_analysis": {
                **state.get("llm_analysis", {}),
                "risk_scoring": {
                    "final_score": final_score,
                    "risk_level": risk_level,
                    "sar_required": sar_required,
                    "breakdown": score_breakdown
                }
            }
        }


class SARGenerationAgent(BaseAgent[AMLState]):
    """Agent for SAR narrative generation"""
    
    def __init__(self):
        super().__init__(
            name="sar_generation",
            description="Generates Suspicious Activity Report narratives"
        )
    
    async def process(self, state: AMLState) -> AMLState:
        """Generate SAR narrative"""
        state = self.update_decision_path(state, "start")
        
        # Build case summary
        case_summary = f"""
Transaction Amount: ${state['transaction'].get('amount', 0):,.2f}
Origin: {state['transaction'].get('origin_country', 'Unknown')}
Destination: {state['transaction'].get('destination_country', 'Unknown')}
Risk Score: {state.get('risk_score', 0)}/100
Risk Level: {state.get('risk_level', 'Unknown')}
"""
        
        # Subject info
        subject_info = f"""
Customer Name: {state['customer'].get('name', 'Unknown')}
Account Age: {state['customer'].get('account_age_days', 0)} days
"""
        
        # Activity details
        activity_details = f"""
Risk Factors: {', '.join(state.get('risk_factors', []))}
Alerts: {', '.join(state.get('alerts', []))}
PEP Status: {state.get('pep_status', False)}
Sanctions Hits: {', '.join(state.get('sanction_hits', []))}
"""
        
        try:
            prompt = PromptTemplates.format_template(
                "SAR_GENERATION",
                case_summary=case_summary,
                subject_info=subject_info,
                activity_details=activity_details
            )
            
            response = await self.invoke_llm(prompt)
            
            sar_narrative = {
                "narrative": response,
                "generated_at": datetime.utcnow().isoformat(),
                "risk_score": state.get("risk_score"),
                "risk_level": state.get("risk_level")
            }
            
        except Exception as e:
            self.logger.error(f"SAR generation failed: {e}")
            sar_narrative = {"error": str(e)}
        
        # Generate case ID
        import hashlib
        case_id = hashlib.sha256(
            f"{state['transaction']}{datetime.utcnow()}".encode()
        ).hexdigest()[:12].upper()
        
        state = self.update_decision_path(state, "complete")
        
        return {
            **state,
            "case_id": f"SAR-{case_id}",
            "sar_narrative": sar_narrative,
            "reporting_status": "SAR_GENERATED",
            "llm_analysis": {
                **state.get("llm_analysis", {}),
                "sar_generation": sar_narrative
            }
        }
