"""
SentinelAI Advanced Prompt Templates
====================================

Chain-of-Thought (CoT), ReAct, and specialized prompts for 
sophisticated AML analysis and reasoning.
"""

from typing import Dict, Any, List
from string import Template


class PromptTemplates:
    """Advanced prompt templates for AML analysis"""
    
    # =====================
    # SYSTEM PROMPTS
    # =====================
    
    SYSTEM_AML_EXPERT = """You are SentinelAI, an elite financial crime detection AI system with expertise in:
- Anti-Money Laundering (AML) regulations and typologies
- Bank Secrecy Act (BSA) compliance
- FATF guidelines and red flag indicators
- Sanctions compliance (OFAC, EU, UN)
- Cryptocurrency and DeFi risk assessment
- Trade-based money laundering (TBML)
- Politically Exposed Persons (PEP) risk analysis

Your analysis must be:
1. Thorough and systematic
2. Based on regulatory frameworks
3. Evidence-based with clear reasoning
4. Actionable with specific recommendations

Always structure your thinking step-by-step and provide confidence scores for your assessments."""

    # =====================
    # CHAIN-OF-THOUGHT PROMPTS
    # =====================
    
    COT_TRANSACTION_ANALYSIS = """<CHAIN_OF_THOUGHT_ANALYSIS>

## STEP 1: Initial Transaction Review
Analyze the following transaction for potential money laundering indicators:

**Transaction Details:**
- Amount: ${amount} ${currency}
- Type: ${transaction_type}
- Origin: ${origin_country} → Destination: ${destination_country}
- Parties: ${parties}
- Timestamp: ${timestamp}
${intermediate_info}
${crypto_info}

## STEP 2: Red Flag Assessment
Let me systematically evaluate each potential red flag category:

### A. Geographic Risk Analysis
- Is the origin/destination a high-risk jurisdiction? (FATF Grey/Black list)
- Are there intermediate countries that suggest layering?
- Is there a logical business reason for this routing?

### B. Transaction Pattern Analysis
- Does the amount suggest structuring (just below reporting thresholds)?
- Is this consistent with the customer's known activity?
- Are there velocity concerns?

### C. Party/Entity Risk
- Are any parties on sanctions lists?
- Are there shell company indicators?
- Is there PEP involvement?

### D. Documentation Review
- Do documents support the stated purpose?
- Are there discrepancies or anomalies?
- Is there evidence of trade-based laundering?

## STEP 3: Historical Context
**Customer Profile:**
- Account Age: ${account_age_days} days
- Customer Type: ${customer_type}
- Previous Transaction History: ${transaction_history_summary}

## STEP 4: Synthesis & Conclusion
Based on my step-by-step analysis, I will now provide:
1. Overall Risk Assessment (0-100 score)
2. Primary Risk Indicators (list of specific concerns)
3. Recommended Actions (escalate, monitor, clear, file SAR)
4. Confidence Level (how certain am I in this assessment)

</CHAIN_OF_THOUGHT_ANALYSIS>

Provide your complete analysis following the above framework. Be specific and cite exact data points that support your conclusions."""

    # =====================
    # REACT PROMPTS
    # =====================
    
    REACT_INVESTIGATION = """<REACT_INVESTIGATION_PROTOCOL>

You are conducting an AML investigation using the ReAct (Reasoning + Acting) framework.

**Case Context:**
${case_context}

**Available Actions:**
- SEARCH_SANCTIONS: Check entity against sanctions databases
- SEARCH_PEP: Check for PEP associations
- ANALYZE_NETWORK: Map entity relationships
- CHECK_VELOCITY: Analyze transaction patterns
- REVIEW_DOCUMENTS: Examine supporting documentation
- CALCULATE_RISK: Compute risk score
- GENERATE_SAR: Prepare Suspicious Activity Report

**Investigation Loop:**

For each step, output in this format:
THOUGHT: [Your reasoning about what to investigate next]
ACTION: [The action to take]
ACTION_INPUT: [Specific parameters for the action]
OBSERVATION: [What you learned from the action]

Continue the loop until you have sufficient evidence to reach a conclusion.

**Final Output Required:**
FINAL_THOUGHT: [Summary of your investigation]
RISK_SCORE: [0-100]
RISK_LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]
RECOMMENDED_ACTION: [CLEAR/MONITOR/ESCALATE/FILE_SAR]
KEY_FINDINGS: [Bullet list of critical findings]
CONFIDENCE: [0-1 score]

</REACT_INVESTIGATION_PROTOCOL>

Begin your investigation:"""

    # =====================
    # SPECIALIZED ANALYSIS PROMPTS
    # =====================
    
    DOCUMENT_ANALYSIS = """<DOCUMENT_ANALYSIS_FRAMEWORK>

## Trade Document Verification

Analyze the following documents for AML red flags related to Trade-Based Money Laundering (TBML):

**Documents Provided:**
${documents}

**Transaction Context:**
- Amount: ${amount}
- Parties: ${parties}
- Trade Route: ${origin_country} → ${destination_country}

## Analysis Framework:

### 1. Invoice Analysis
- Over/under-invoicing indicators
- Phantom shipment signs
- Multiple invoicing patterns
- Price consistency with market rates

### 2. Shipping Document Review
- Bill of lading authenticity markers
- Port/routing anomalies
- Weight/quantity discrepancies
- Carrier verification issues

### 3. Letter of Credit Review (if applicable)
- Beneficiary verification
- Terms consistency
- Amendment patterns

### 4. Red Flag Codes to Apply:
- TBML_OVERINVOICE: Price significantly above market
- TBML_UNDERINVOICE: Price significantly below market
- TBML_PHANTOM: No evidence of actual goods movement
- TBML_CAROUSEL: Circular trade patterns
- TBML_MULTI_INVOICE: Same goods invoiced multiple times
- DOC_MISMATCH: Documents don't align with transaction
- DOC_FORGERY: Signs of document manipulation

## Output Required:
1. Document legitimacy assessment
2. Identified red flags (with codes)
3. Risk score contribution (0-30)
4. Evidence summary
5. Recommended follow-up actions

</DOCUMENT_ANALYSIS_FRAMEWORK>"""

    CRYPTO_ANALYSIS = """<CRYPTOCURRENCY_RISK_ANALYSIS>

## Digital Asset Transaction Assessment

**Crypto Transaction Details:**
${crypto_details}

**Risk Evaluation Framework:**

### 1. Wallet Analysis
- Wallet age and history
- Known associations (exchanges, mixers, darknet)
- Transaction pattern anomalies
- UTXO analysis indicators

### 2. Mixing/Tumbling Detection
- Service usage indicators
- CoinJoin participation
- Cross-chain swap patterns
- Privacy coin conversion

### 3. DeFi Risk Assessment
- Protocol interactions
- Flash loan patterns
- Liquidity pool activities
- Bridge transaction analysis

### 4. Darknet/Illicit Association
- Known darknet market wallets
- Ransomware address associations
- Scam/fraud connections

### 5. Risk Codes to Apply:
- CRYPTO_MIXER: Mixing service detected
- CRYPTO_DARKNET: Darknet market association
- CRYPTO_PRIVACY: Privacy coin conversion
- CRYPTO_LAYERING: Complex layering pattern
- CRYPTO_NEW_WALLET: Suspiciously new wallet
- CRYPTO_BRIDGE: Cross-chain obfuscation
- CRYPTO_DEFI_WASH: DeFi wash trading indicators

## Output Required:
1. Blockchain risk assessment
2. Identified risk indicators (with codes)
3. Risk score contribution (0-40)
4. Recommended blockchain analytics actions
5. Law enforcement referral indicators

</CRYPTOCURRENCY_RISK_ANALYSIS>"""

    NETWORK_ANALYSIS = """<NETWORK_RELATIONSHIP_ANALYSIS>

## Entity Network Investigation

**Primary Entity:**
${primary_entity}

**Known Connections:**
${connections}

**Transaction Network:**
${transaction_network}

## Network Analysis Framework:

### 1. Relationship Mapping
- Direct beneficial ownership
- Corporate structure complexity
- UBO (Ultimate Beneficial Owner) identification
- Nominee/proxy indicators

### 2. Shell Company Detection
- Circular ownership patterns
- Lack of substantive business
- Multiple jurisdiction registrations
- Shared addresses/directors

### 3. Funnel/Fan-out Patterns
- Aggregation accounts
- Distribution networks
- Layering through multiple entities

### 4. Network Risk Codes:
- NET_SHELL: Shell company indicators
- NET_CIRCULAR: Circular fund flows
- NET_LAYERING: Complex layering structure
- NET_FUNNEL: Aggregation pattern
- NET_FANOUT: Distribution pattern
- NET_NOMINEE: Nominee arrangement detected
- NET_OPACITY: Deliberate structure opacity

## Output Required:
1. Network structure assessment
2. Key entities of concern
3. Identified patterns (with codes)
4. Risk score contribution (0-35)
5. Recommended deep-dive entities
6. Visualization recommendations

</NETWORK_RELATIONSHIP_ANALYSIS>"""

    SANCTIONS_SCREENING = """<SANCTIONS_SCREENING_ANALYSIS>

## Comprehensive Sanctions Review

**Entity to Screen:**
Name: ${entity_name}
Aliases: ${aliases}
Country: ${country}
Additional Identifiers: ${identifiers}

**Screening Against:**
- OFAC SDN List
- OFAC Consolidated Sanctions
- EU Consolidated List
- UN Security Council Sanctions
- FATF High-Risk Jurisdictions

## Screening Framework:

### 1. Name Matching
- Exact match detection
- Fuzzy matching (Levenshtein, Soundex)
- Transliteration variants
- Alias cross-reference

### 2. Identifier Verification
- Passport/ID numbers
- Corporate registration numbers
- Tax identifiers
- Vessel/Aircraft identifiers

### 3. Country/Program Analysis
- Primary sanctioned programs
- Secondary sanctions exposure
- Sectoral sanctions applicability

### 4. Sanctions Codes:
- SANC_SDN: OFAC SDN match
- SANC_EU: EU sanctions match
- SANC_UN: UN sanctions match
- SANC_SECTORAL: Sectoral sanctions exposure
- SANC_SECONDARY: Secondary sanctions risk
- SANC_OWNED: Owned by sanctioned entity
- SANC_CONTROLLED: Controlled by sanctioned entity

## Output Required:
1. Match determination (MATCH/POTENTIAL_MATCH/NO_MATCH)
2. Matched list details
3. Match confidence score
4. Required escalation actions
5. Transaction blocking recommendation

</SANCTIONS_SCREENING_ANALYSIS>"""

    PEP_SCREENING = """<PEP_SCREENING_ANALYSIS>

## Politically Exposed Person Assessment

**Individual to Screen:**
Name: ${name}
Nationality: ${nationality}
Associated Organizations: ${organizations}
Position/Role: ${position}

## PEP Assessment Framework:

### 1. PEP Category Determination
- Foreign PEP (government officials, heads of state)
- Domestic PEP (local government, judicial)
- International Organization PEP (UN, IMF, etc.)
- Close Associates & Family Members (RCA)

### 2. Position Analysis
- Current vs. Former PEP
- Level of influence
- Access to public funds
- Corruption risk indicators

### 3. Geographic Risk Overlay
- Country corruption index
- Known corruption patterns
- Political stability factors

### 4. PEP Risk Codes:
- PEP_FOREIGN_SENIOR: Senior foreign official
- PEP_DOMESTIC: Domestic political exposure
- PEP_INT_ORG: International organization
- PEP_RCA: Relative or close associate
- PEP_FORMER: Former PEP (elevated monitoring)
- PEP_HIGH_CORRUPT: High corruption risk jurisdiction

## Output Required:
1. PEP status determination
2. PEP category and level
3. Associated risk factors
4. Enhanced due diligence requirements
5. Ongoing monitoring recommendations
6. Approval level required

</PEP_SCREENING_ANALYSIS>"""

    SAR_GENERATION = """<SAR_NARRATIVE_GENERATION>

## Suspicious Activity Report Preparation

**Case Summary:**
${case_summary}

**Subject Information:**
${subject_info}

**Suspicious Activity:**
${activity_details}

## SAR Narrative Framework (FinCEN Format):

### 1. Who is Conducting the Suspicious Activity?
- Subject identification
- Account details
- Relationship to financial institution

### 2. What is the Suspicious Activity?
- Clear description of activity
- Specific transactions involved
- Total amounts and time period

### 3. When Did the Activity Occur?
- Date range of suspicious activity
- Pattern timeline
- Detection date

### 4. Where Did the Activity Take Place?
- Branches/channels involved
- Geographic locations
- Cross-border elements

### 5. Why is the Activity Suspicious?
- Red flags identified
- Deviation from expected behavior
- Regulatory indicators triggered

### 6. How was the Activity Conducted?
- Methods used
- Instruments involved
- Co-conspirators if any

## Output Required:
1. Complete SAR narrative (regulatory compliant)
2. Activity characterization codes
3. Amount involved
4. Subject role codes
5. Law enforcement recommendations
6. Case disposition recommendation

</SAR_NARRATIVE_GENERATION>"""

    # =====================
    # SCORING & DECISION PROMPTS
    # =====================
    
    RISK_SCORING = """<COMPREHENSIVE_RISK_SCORING>

## Multi-Factor Risk Score Calculation

**Analysis Inputs:**
${all_analysis_results}

## Scoring Framework:

### Weight Distribution:
- Sanctions Hits: 40% (Critical factor)
- PEP Exposure: 15%
- Geographic Risk: 15%
- Transaction Patterns: 10%
- Crypto Risk: 10%
- Document Anomalies: 5%
- Network Risk: 5%

### Score Calculation:
For each category, provide:
- Raw score (0-100)
- Weighted contribution
- Key factors driving the score

### Risk Level Thresholds:
- LOW: 0-30
- MEDIUM: 31-60
- HIGH: 61-80
- CRITICAL: 81-100

## Output Required:
1. Category-by-category scoring breakdown
2. Final weighted risk score
3. Risk level classification
4. Primary risk drivers (top 3)
5. Confidence interval

</COMPREHENSIVE_RISK_SCORING>"""

    DECISION_ROUTING = """<INTELLIGENT_DECISION_ROUTING>

## Case Disposition Recommendation

**Risk Assessment:**
Risk Score: ${risk_score}
Risk Level: ${risk_level}
Primary Factors: ${risk_factors}

**Regulatory Context:**
- SAR filing threshold met: ${sar_threshold}
- SAR filing deadline: ${sar_deadline}
- Regulatory examination context: ${exam_context}

## Decision Framework:

### Disposition Options:
1. **CLEAR** - No suspicious activity, close case
2. **MONITOR** - Add to enhanced monitoring, no immediate action
3. **ESCALATE** - Requires senior review/approval
4. **FILE_SAR** - Suspicious Activity Report required
5. **BLOCK** - Immediate transaction blocking required
6. **LAW_ENFORCEMENT** - Refer to law enforcement

### Decision Criteria:
- Legal obligations (BSA/AML requirements)
- Risk tolerance alignment
- Evidentiary sufficiency
- Precedent consistency

## Output Required:
1. Recommended disposition
2. Justification
3. Required approvals
4. Timeline for action
5. Follow-up actions
6. Documentation requirements

</INTELLIGENT_DECISION_ROUTING>"""

    @classmethod
    def get_template(cls, template_name: str) -> str:
        """Get a prompt template by name"""
        return getattr(cls, template_name, None)
    
    @classmethod
    def format_template(cls, template_name: str, **kwargs) -> str:
        """Format a prompt template with variables"""
        template = cls.get_template(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")
        
        # Use safe substitution to handle missing keys gracefully
        return Template(template).safe_substitute(**kwargs)
    
    @classmethod
    def build_cot_analysis_prompt(
        cls,
        transaction: Dict[str, Any],
        customer: Dict[str, Any]
    ) -> str:
        """Build a complete Chain-of-Thought analysis prompt"""
        
        # Format intermediate countries info
        intermediate_info = ""
        if transaction.get("intermediate_countries"):
            intermediate_info = f"- Intermediate Countries: {', '.join(transaction['intermediate_countries'])}"
        
        # Format crypto info
        crypto_info = ""
        if transaction.get("crypto_details"):
            details = transaction["crypto_details"]
            crypto_info = f"""
**Cryptocurrency Details:**
- Wallet Age: {details.get('wallet_age_days', 'Unknown')} days
- Mixer Used: {details.get('mixer_used', False)}
- Cross-Chain Swaps: {details.get('cross_chain_swaps', 0)}"""
        
        # Summarize transaction history
        history = customer.get("transaction_history", [])
        if history:
            total = sum(tx.get("amount", 0) for tx in history)
            history_summary = f"{len(history)} transactions, total ${total:,.2f}"
        else:
            history_summary = "No prior transaction history"
        
        return cls.format_template(
            "COT_TRANSACTION_ANALYSIS",
            amount=transaction.get("amount", 0),
            currency=transaction.get("currency", "USD"),
            transaction_type=transaction.get("transaction_type", "UNKNOWN"),
            origin_country=transaction.get("origin_country", "UNKNOWN"),
            destination_country=transaction.get("destination_country", "UNKNOWN"),
            parties=", ".join(transaction.get("parties", [])) or "Not specified",
            timestamp=transaction.get("timestamp", "Unknown"),
            intermediate_info=intermediate_info,
            crypto_info=crypto_info,
            account_age_days=customer.get("account_age_days", 0),
            customer_type=customer.get("customer_type", "INDIVIDUAL"),
            transaction_history_summary=history_summary
        )
    
    @classmethod
    def build_react_prompt(cls, case_context: str) -> str:
        """Build a ReAct investigation prompt"""
        return cls.format_template("REACT_INVESTIGATION", case_context=case_context)
