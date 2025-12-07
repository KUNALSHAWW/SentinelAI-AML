/**
 * SentinelAI - Enterprise AML Detection Platform
 * Frontend Application JavaScript v2.0
 */

// ============================================
// Configuration
// ============================================
const CONFIG = {
    API_BASE_URL: 'https://sentinelai-api.onrender.com',
    ENDPOINTS: {
        health: '/health',
        analyze: '/api/v1/analyze/rules',  // Use rule-based endpoint (always available)
        analyzeLLM: '/api/v1/analyze',     // LLM-powered endpoint (may timeout)
        cases: '/api/v1/cases'
    },
    ANIMATION: {
        counterDuration: 2000,
        typingSpeed: 50
    },
    ENABLE_LOCAL_SIMULATION: true
};

// ============================================
// Risk Data for Local Simulation
// ============================================
const RISK_DATA = {
    HIGH_RISK_COUNTRIES: ['RU', 'IR', 'KP', 'SY', 'CU', 'VE', 'MM', 'BY', 'CD', 'CF', 'LY', 'SO', 'SS', 'YE', 'ZW'],
    TAX_HAVENS: ['KY', 'VG', 'PA', 'CH', 'LI', 'MC', 'AD', 'JE', 'GG', 'IM', 'BM', 'BS', 'BZ', 'LU', 'MT', 'CY', 'SG', 'HK', 'AE'],
    GREY_LIST: ['NG', 'PK', 'PH', 'TZ', 'JM', 'AL', 'BB', 'BF', 'CM', 'HR', 'GH', 'GI', 'HT', 'JO', 'ML', 'MZ', 'SN', 'UG', 'ZA'],
    PEP_INDICATORS: ['government', 'minister', 'president', 'senator', 'official', 'embassy', 'state', 'political', 'military'],
    SANCTION_KEYWORDS: ['russia', 'russian', 'moscow', 'iran', 'iranian', 'tehran', 'korea', 'pyongyang', 'syria', 'syrian']
};

// ============================================
// State Management
// ============================================
const state = {
    isLoading: false,
    apiStatus: 'checking',
    lastAnalysis: null,
    useLocalSimulation: false
};

// ============================================
// DOM Elements
// ============================================
const elements = {};

// ============================================
// Initialization
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    console.log('🛡️ SentinelAI Frontend v2.0 Initializing...');
    
    cacheElements();
    initNavigation();
    initNeuralNetwork();
    initAPIStatusCheck();
    initForm();
    initScenarioButtons();
    initAnimations();
    initCounterAnimation();
    
    console.log('✅ SentinelAI Frontend Ready');
    console.log('📡 API Endpoint:', CONFIG.API_BASE_URL);
}

function cacheElements() {
    elements.navbar = document.querySelector('.navbar');
    elements.mobileMenuBtn = document.getElementById('mobileMenuBtn');
    elements.mobileMenu = document.getElementById('mobileMenu');
    elements.statusDot = document.querySelector('.status-dot');
    elements.statusText = document.querySelector('.status-text');
    elements.analyzeBtn = document.getElementById('analyzeBtn');
    elements.btnLoader = document.getElementById('btnLoader');
    elements.resultsPanel = document.getElementById('resultsPanel');
    
    elements.amount = document.getElementById('amount');
    elements.originCountry = document.getElementById('originCountry');
    elements.destCountry = document.getElementById('destCountry');
    elements.transactionType = document.getElementById('transactionType');
    elements.customerName = document.getElementById('customerName');
    elements.customerType = document.getElementById('customerType');
    elements.accountAge = document.getElementById('accountAge');
}

// ============================================
// Navigation
// ============================================
function initNavigation() {
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            elements.navbar?.classList.add('scrolled');
        } else {
            elements.navbar?.classList.remove('scrolled');
        }
    });
    
    elements.mobileMenuBtn?.addEventListener('click', () => {
        elements.mobileMenu?.classList.toggle('active');
        elements.mobileMenuBtn.classList.toggle('active');
    });
    
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                elements.mobileMenu?.classList.remove('active');
            }
        });
    });
}

// ============================================
// Neural Network Animation
// ============================================
function initNeuralNetwork() {
    const canvas = document.getElementById('neuralCanvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    let nodes = [];
    let connections = [];
    
    function resize() {
        canvas.width = canvas.offsetWidth * 2;
        canvas.height = canvas.offsetHeight * 2;
        ctx.scale(2, 2);
        initNodes();
    }
    
    function initNodes() {
        nodes = [];
        connections = [];
        const centerX = canvas.offsetWidth / 2;
        const centerY = canvas.offsetHeight / 2;
        const radius = Math.min(centerX, centerY) * 0.8;
        
        for (let i = 0; i < 12; i++) {
            const angle = (i / 12) * Math.PI * 2;
            const r = radius * (0.5 + Math.random() * 0.5);
            nodes.push({
                x: centerX + Math.cos(angle) * r,
                y: centerY + Math.sin(angle) * r,
                radius: 4 + Math.random() * 4,
                angle: angle,
                speed: 0.001 + Math.random() * 0.002,
                orbitRadius: r
            });
        }
        
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                if (Math.random() > 0.5) {
                    connections.push({ from: i, to: j, active: false, progress: 0 });
                }
            }
        }
    }
    
    function animate() {
        ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight);
        const centerX = canvas.offsetWidth / 2;
        const centerY = canvas.offsetHeight / 2;
        
        nodes.forEach(node => {
            node.angle += node.speed;
            node.x = centerX + Math.cos(node.angle) * node.orbitRadius;
            node.y = centerY + Math.sin(node.angle) * node.orbitRadius;
        });
        
        connections.forEach(conn => {
            const from = nodes[conn.from];
            const to = nodes[conn.to];
            
            ctx.beginPath();
            ctx.moveTo(from.x, from.y);
            ctx.lineTo(to.x, to.y);
            ctx.strokeStyle = 'rgba(99, 102, 241, 0.15)';
            ctx.lineWidth = 1;
            ctx.stroke();
            
            if (Math.random() > 0.995) {
                conn.active = true;
                conn.progress = 0;
            }
            
            if (conn.active) {
                conn.progress += 0.02;
                if (conn.progress >= 1) conn.active = false;
                
                const x = from.x + (to.x - from.x) * conn.progress;
                const y = from.y + (to.y - from.y) * conn.progress;
                
                ctx.beginPath();
                ctx.arc(x, y, 3, 0, Math.PI * 2);
                ctx.fillStyle = '#6366f1';
                ctx.fill();
            }
        });
        
        nodes.forEach(node => {
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, node.radius);
            gradient.addColorStop(0, 'rgba(99, 102, 241, 0.8)');
            gradient.addColorStop(1, 'rgba(139, 92, 246, 0.4)');
            ctx.fillStyle = gradient;
            ctx.fill();
        });
        
        requestAnimationFrame(animate);
    }
    
    resize();
    animate();
    window.addEventListener('resize', resize);
}

// ============================================
// API Status Check
// ============================================
async function initAPIStatusCheck() {
    updateAPIStatus('checking', 'Checking API...');
    
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);
        
        const response = await fetch(`${CONFIG.API_BASE_URL}/health`, {
            method: 'GET',
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
            const data = await response.json();
            state.apiStatus = 'online';
            state.useLocalSimulation = false;
            updateAPIStatus('online', 'API Online');
            console.log('✅ API Status:', data);
        } else {
            throw new Error('API returned non-OK status');
        }
    } catch (error) {
        state.apiStatus = 'offline';
        state.useLocalSimulation = CONFIG.ENABLE_LOCAL_SIMULATION;
        updateAPIStatus('simulation', 'Demo Mode');
        console.warn('⚠️ API unavailable, using local simulation:', error.message);
    }
}

function updateAPIStatus(status, text) {
    if (elements.statusDot) {
        const colors = {
            'checking': '#f59e0b',
            'online': '#10b981',
            'offline': '#ef4444',
            'simulation': '#8b5cf6'
        };
        elements.statusDot.style.background = colors[status] || '#6b7280';
    }
    if (elements.statusText) {
        elements.statusText.textContent = text;
    }
}

// ============================================
// Form Handling
// ============================================
function initForm() {
    elements.analyzeBtn?.addEventListener('click', async (e) => {
        e.preventDefault();
        await analyzeTransaction();
    });
}

async function analyzeTransaction() {
    if (state.isLoading) return;
    
    const amount = parseFloat(elements.amount?.value) || 0;
    const originCountry = elements.originCountry?.value || 'US';
    const destCountry = elements.destCountry?.value || 'US';
    const transactionType = elements.transactionType?.value || 'WIRE_TRANSFER';
    const customerName = elements.customerName?.value || 'Demo Customer';
    const customerType = elements.customerType?.value || 'INDIVIDUAL';
    const accountAge = parseInt(elements.accountAge?.value) || 365;
    
    if (!amount || amount <= 0) {
        showNotification('Please enter a valid amount', 'error');
        return;
    }
    
    state.isLoading = true;
    updateLoadingState(true);
    showNotification('Analyzing transaction...', 'info');
    
    const requestData = {
        transaction: {
            amount: amount,
            currency: 'USD',
            origin_country: originCountry,
            destination_country: destCountry,
            transaction_type: transactionType,
            timestamp: new Date().toISOString()
        },
        customer: {
            name: customerName,
            customer_type: customerType.toLowerCase(),
            account_age_days: accountAge
        },
        enable_llm_analysis: true
    };
    
    console.log('📤 Analysis Request:', requestData);
    
    try {
        let result;
        
        if (state.useLocalSimulation) {
            result = await simulateAnalysis(requestData);
        } else {
            result = await callAPI(requestData);
        }
        
        console.log('📥 Analysis Result:', result);
        state.lastAnalysis = result;
        displayResults(result);
        showNotification('Analysis completed successfully!', 'success');
        
    } catch (error) {
        console.error('❌ Analysis Error:', error);
        
        if (CONFIG.ENABLE_LOCAL_SIMULATION && !state.useLocalSimulation) {
            console.log('🔄 Falling back to local simulation...');
            state.useLocalSimulation = true;
            updateAPIStatus('simulation', 'Demo Mode');
            
            try {
                const result = await simulateAnalysis(requestData);
                state.lastAnalysis = result;
                displayResults(result);
                showNotification('Analysis completed (Demo Mode)', 'success');
            } catch (simError) {
                showNotification(`Analysis failed: ${simError.message}`, 'error');
                displayErrorResult(simError.message);
            }
        } else {
            showNotification(`Analysis failed: ${error.message}`, 'error');
            displayErrorResult(error.message);
        }
    } finally {
        state.isLoading = false;
        updateLoadingState(false);
    }
}

async function callAPI(requestData) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.analyze}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(requestData),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            const errorText = await response.text();
            let errorDetail = `HTTP ${response.status}`;
            try {
                const errorJson = JSON.parse(errorText);
                errorDetail = errorJson.detail || errorDetail;
            } catch (e) {}
            throw new Error(errorDetail);
        }
        
        return await response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Request timeout - API may be starting up');
        }
        throw error;
    }
}

// ============================================
// Local Simulation (AI-like Analysis)
// ============================================
async function simulateAnalysis(requestData) {
    await new Promise(resolve => setTimeout(resolve, 1500 + Math.random() * 1000));
    
    const tx = requestData.transaction;
    const customer = requestData.customer;
    
    let riskScore = 0;
    const riskFactors = [];
    const alerts = [];
    const decisionPath = ['entry:initial_screening'];
    
    decisionPath.push('geographic_risk:analyzing');
    
    const originUpper = tx.origin_country.toUpperCase();
    const destUpper = tx.destination_country.toUpperCase();
    
    if (RISK_DATA.HIGH_RISK_COUNTRIES.includes(originUpper)) {
        riskScore += 25;
        riskFactors.push({
            code: 'HIGH_RISK_ORIGIN',
            description: `High-risk origin country: ${getCountryName(originUpper)}`,
            severity: 'HIGH',
            score: 25,
            category: 'geographic'
        });
        alerts.push({
            type: 'HIGH_RISK_JURISDICTION',
            severity: 'HIGH',
            title: 'High-Risk Origin Country',
            description: `Transaction originates from ${getCountryName(originUpper)}, which is classified as a high-risk jurisdiction for money laundering.`
        });
    }
    
    if (RISK_DATA.HIGH_RISK_COUNTRIES.includes(destUpper)) {
        riskScore += 25;
        riskFactors.push({
            code: 'HIGH_RISK_DESTINATION',
            description: `High-risk destination country: ${getCountryName(destUpper)}`,
            severity: 'HIGH',
            score: 25,
            category: 'geographic'
        });
    }
    
    if (RISK_DATA.TAX_HAVENS.includes(destUpper)) {
        riskScore += 15;
        riskFactors.push({
            code: 'TAX_HAVEN_DESTINATION',
            description: `Destination is known tax haven: ${getCountryName(destUpper)}`,
            severity: 'MEDIUM',
            score: 15,
            category: 'geographic'
        });
        alerts.push({
            type: 'TAX_HAVEN',
            severity: 'MEDIUM',
            title: 'Tax Haven Destination',
            description: `Funds being transferred to ${getCountryName(destUpper)}, a jurisdiction commonly used for tax avoidance and asset hiding.`
        });
    }
    
    if (RISK_DATA.GREY_LIST.includes(originUpper) || RISK_DATA.GREY_LIST.includes(destUpper)) {
        riskScore += 10;
        riskFactors.push({
            code: 'GREY_LIST_JURISDICTION',
            description: 'Transaction involves FATF grey list country',
            severity: 'MEDIUM',
            score: 10,
            category: 'geographic'
        });
    }
    
    decisionPath.push('amount_analysis:analyzing');
    
    if (tx.amount > 100000) {
        riskScore += 15;
        riskFactors.push({
            code: 'LARGE_TRANSACTION',
            description: `Large transaction amount: $${tx.amount.toLocaleString()}`,
            severity: 'MEDIUM',
            score: 15,
            category: 'transaction'
        });
        alerts.push({
            type: 'LARGE_TRANSACTION',
            severity: 'MEDIUM',
            title: 'Large Value Transaction',
            description: `Transaction amount of $${tx.amount.toLocaleString()} exceeds standard monitoring threshold.`
        });
    }
    
    if (tx.amount >= 9000 && tx.amount <= 10000) {
        riskScore += 20;
        riskFactors.push({
            code: 'STRUCTURING_INDICATOR',
            description: 'Amount near reporting threshold - possible structuring',
            severity: 'HIGH',
            score: 20,
            category: 'behavioral'
        });
        alerts.push({
            type: 'STRUCTURING',
            severity: 'HIGH',
            title: 'Possible Structuring',
            description: 'Transaction amount is suspiciously close to $10,000 reporting threshold, indicating possible structuring to avoid reporting requirements.'
        });
    }
    
    decisionPath.push('customer_analysis:analyzing');
    
    const customerNameLower = customer.name.toLowerCase();
    
    for (const keyword of RISK_DATA.SANCTION_KEYWORDS) {
        if (customerNameLower.includes(keyword)) {
            riskScore += 30;
            riskFactors.push({
                code: 'SANCTIONS_KEYWORD_MATCH',
                description: `Customer name contains sanctions-related keyword: "${keyword}"`,
                severity: 'CRITICAL',
                score: 30,
                category: 'sanctions'
            });
            alerts.push({
                type: 'SANCTIONS_ALERT',
                severity: 'CRITICAL',
                title: 'Potential Sanctions Concern',
                description: `Customer name "${customer.name}" contains keywords associated with sanctioned jurisdictions.`
            });
            break;
        }
    }
    
    for (const indicator of RISK_DATA.PEP_INDICATORS) {
        if (customerNameLower.includes(indicator)) {
            riskScore += 15;
            riskFactors.push({
                code: 'PEP_INDICATOR',
                description: `Customer name suggests politically exposed person: "${indicator}"`,
                severity: 'MEDIUM',
                score: 15,
                category: 'pep'
            });
            break;
        }
    }
    
    if (customer.customer_type === 'corporate') {
        riskScore += 5;
        riskFactors.push({
            code: 'CORPORATE_ENTITY',
            description: 'Corporate entities require enhanced due diligence',
            severity: 'LOW',
            score: 5,
            category: 'customer'
        });
    }
    
    if (customer.account_age_days < 90) {
        riskScore += 10;
        riskFactors.push({
            code: 'NEW_ACCOUNT',
            description: `Account is only ${customer.account_age_days} days old`,
            severity: 'MEDIUM',
            score: 10,
            category: 'behavioral'
        });
        alerts.push({
            type: 'NEW_ACCOUNT_ACTIVITY',
            severity: 'MEDIUM',
            title: 'New Account High Activity',
            description: `Large transaction on account that is only ${customer.account_age_days} days old.`
        });
    }
    
    decisionPath.push('transaction_type:analyzing');
    
    if (tx.transaction_type === 'CRYPTO') {
        riskScore += 15;
        riskFactors.push({
            code: 'CRYPTO_TRANSACTION',
            description: 'Cryptocurrency transactions carry elevated risk',
            severity: 'MEDIUM',
            score: 15,
            category: 'crypto'
        });
        alerts.push({
            type: 'CRYPTO_RISK',
            severity: 'MEDIUM',
            title: 'Cryptocurrency Transaction',
            description: 'Virtual asset transactions require enhanced monitoring due to pseudonymous nature.'
        });
    }
    
    if (tx.transaction_type === 'CASH') {
        riskScore += 10;
        riskFactors.push({
            code: 'CASH_TRANSACTION',
            description: 'Cash transactions have higher AML risk',
            severity: 'MEDIUM',
            score: 10,
            category: 'transaction'
        });
    }
    
    decisionPath.push('risk_scoring:calculating');
    
    riskScore = Math.min(riskScore, 100);
    
    let riskLevel;
    if (riskScore >= 80) riskLevel = 'CRITICAL';
    else if (riskScore >= 60) riskLevel = 'HIGH';
    else if (riskScore >= 40) riskLevel = 'MEDIUM';
    else riskLevel = 'LOW';
    
    let recommendedAction;
    let sarRequired = false;
    
    if (riskScore >= 75) {
        recommendedAction = 'BLOCK';
        sarRequired = true;
    } else if (riskScore >= 50) {
        recommendedAction = 'ESCALATE';
        sarRequired = riskScore >= 60;
    } else if (riskScore >= 30) {
        recommendedAction = 'REVIEW';
    } else {
        recommendedAction = 'APPROVE';
    }
    
    decisionPath.push(`decision:${recommendedAction.toLowerCase()}`);
    
    const reasoning = generateReasoning(tx, customer, riskFactors, riskScore, riskLevel);
    
    return {
        request_id: generateUUID(),
        processed_at: new Date().toISOString(),
        processing_time_ms: Math.floor(1500 + Math.random() * 1000),
        risk_assessment: {
            risk_score: riskScore,
            risk_level: riskLevel,
            risk_factors: riskFactors,
            decision_path: decisionPath,
            alerts_triggered: alerts.length
        },
        llm_analysis: {
            summary: `Transaction flagged as ${riskLevel} risk with score ${riskScore}/100`,
            risk_indicators: riskFactors.map(rf => rf.description),
            reasoning: reasoning,
            confidence_score: 0.85 + Math.random() * 0.1,
            recommendation: recommendedAction
        },
        alerts: alerts,
        recommended_action: recommendedAction,
        action_required: riskScore >= 30,
        next_steps: getNextSteps(recommendedAction),
        sar_required: sarRequired,
        _simulation: true
    };
}

function generateReasoning(tx, customer, factors, score, level) {
    const lines = [];
    
    lines.push(`ANALYSIS SUMMARY`);
    lines.push(`================`);
    lines.push(`Transaction: $${tx.amount.toLocaleString()} ${tx.transaction_type}`);
    lines.push(`Route: ${getCountryName(tx.origin_country)} → ${getCountryName(tx.destination_country)}`);
    lines.push(`Customer: ${customer.name} (${customer.customer_type})`);
    lines.push(``);
    lines.push(`RISK ASSESSMENT: ${level} (Score: ${score}/100)`);
    lines.push(``);
    
    if (factors.length > 0) {
        lines.push(`KEY RISK INDICATORS:`);
        factors.forEach((f, i) => {
            lines.push(`${i + 1}. [${f.severity}] ${f.description}`);
        });
    } else {
        lines.push(`No significant risk indicators detected.`);
    }
    
    lines.push(``);
    lines.push(`REASONING CHAIN:`);
    lines.push(`• Geographic analysis: ${factors.filter(f => f.category === 'geographic').length} factors identified`);
    lines.push(`• Transaction analysis: ${factors.filter(f => f.category === 'transaction').length} factors identified`);
    lines.push(`• Customer analysis: ${factors.filter(f => f.category === 'customer' || f.category === 'behavioral').length} factors identified`);
    lines.push(`• Sanctions/PEP screening: ${factors.filter(f => f.category === 'sanctions' || f.category === 'pep').length} matches`);
    
    return lines.join('\n');
}

function getNextSteps(action) {
    switch (action) {
        case 'BLOCK':
            return ['Immediately block transaction', 'File Suspicious Activity Report (SAR)', 'Escalate to compliance officer', 'Freeze related accounts for review'];
        case 'ESCALATE':
            return ['Escalate to senior analyst', 'Gather additional documentation', 'Review customer history', 'Consider enhanced due diligence'];
        case 'REVIEW':
            return ['Manual review required', 'Verify customer documentation', 'Check transaction purpose'];
        case 'APPROVE':
            return ['Transaction may proceed', 'Standard monitoring applies'];
        default:
            return ['Review case details'];
    }
}

function getCountryName(code) {
    const countries = {
        'US': 'United States', 'RU': 'Russia', 'CN': 'China', 'IR': 'Iran', 'KP': 'North Korea',
        'KY': 'Cayman Islands', 'CH': 'Switzerland', 'PA': 'Panama', 'VG': 'British Virgin Islands',
        'GB': 'United Kingdom', 'SG': 'Singapore', 'AE': 'UAE', 'NG': 'Nigeria', 'HK': 'Hong Kong',
        'SY': 'Syria', 'CU': 'Cuba', 'VE': 'Venezuela', 'MM': 'Myanmar', 'BY': 'Belarus'
    };
    return countries[code] || code;
}

function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function updateLoadingState(isLoading) {
    if (elements.analyzeBtn) {
        elements.analyzeBtn.disabled = isLoading;
        elements.analyzeBtn.classList.toggle('loading', isLoading);
    }
    if (elements.btnLoader) {
        elements.btnLoader.style.display = isLoading ? 'block' : 'none';
    }
}

// ============================================
// Results Display
// ============================================
function displayResults(result) {
    if (!elements.resultsPanel) return;
    
    const riskScore = result.risk_assessment?.risk_score || 0;
    const riskLevel = result.risk_assessment?.risk_level || 'LOW';
    const riskFactors = result.risk_assessment?.risk_factors || [];
    const alerts = result.alerts || [];
    const llmAnalysis = result.llm_analysis || {};
    const recommendedAction = result.recommended_action || 'REVIEW';
    const nextSteps = result.next_steps || [];
    const sarRequired = result.sar_required || false;
    const isSimulation = result._simulation || false;
    
    const riskLevelClass = riskLevel.toLowerCase();
    const actionClass = recommendedAction === 'BLOCK' ? 'block' : 
                        recommendedAction === 'ESCALATE' ? 'review' : 
                        recommendedAction === 'REVIEW' ? 'review' : 'approve';
    
    elements.resultsPanel.innerHTML = `
        <div class="analysis-result" style="animation: fadeIn 0.5s ease;">
            ${isSimulation ? `
                <div style="background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 8px; padding: 12px; margin-bottom: 16px; font-size: 12px; color: #a78bfa;">
                    <i class="fas fa-flask"></i> <strong>Demo Mode</strong> - Results generated by local AI simulation
                </div>
            ` : ''}
            
            <div class="risk-header">
                <div class="risk-score-circle ${riskLevelClass}">
                    <span class="risk-score-value">${Math.round(riskScore)}</span>
                    <span class="risk-score-label">Risk Score</span>
                </div>
                <div class="risk-info">
                    <h3>Analysis Complete</h3>
                    <span class="risk-level-badge ${riskLevelClass}">${riskLevel} Risk</span>
                    ${sarRequired ? '<span class="risk-level-badge high" style="margin-left: 8px;"><i class="fas fa-exclamation-triangle"></i> SAR Required</span>' : ''}
                </div>
            </div>
            
            ${alerts.length > 0 ? `
                <div class="result-section">
                    <h4><i class="fas fa-exclamation-triangle"></i> Alerts Triggered (${alerts.length})</h4>
                    ${alerts.map(alert => `
                        <div class="alert-item" style="border-left-color: ${alert.severity === 'CRITICAL' ? '#dc2626' : alert.severity === 'HIGH' ? '#ef4444' : '#f59e0b'};">
                            <i class="fas fa-flag" style="color: ${alert.severity === 'CRITICAL' ? '#dc2626' : alert.severity === 'HIGH' ? '#ef4444' : '#f59e0b'};"></i>
                            <div>
                                <strong>${alert.title}</strong>
                                <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--text-secondary);">${alert.description}</p>
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : `
                <div class="result-section">
                    <h4><i class="fas fa-check-circle" style="color: #10b981;"></i> No Critical Alerts</h4>
                    <div class="alert-item" style="background: rgba(16, 185, 129, 0.1); border-left-color: #10b981;">
                        <i class="fas fa-shield-alt" style="color: #10b981;"></i>
                        <span>No significant risk indicators detected in this transaction.</span>
                    </div>
                </div>
            `}
            
            ${riskFactors.length > 0 ? `
                <div class="result-section">
                    <h4><i class="fas fa-list"></i> Risk Factors (${riskFactors.length})</h4>
                    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                        ${riskFactors.map(factor => `
                            <span style="
                                display: inline-flex;
                                align-items: center;
                                gap: 6px;
                                padding: 6px 12px;
                                background: rgba(${factor.severity === 'CRITICAL' ? '220, 38, 38' : factor.severity === 'HIGH' ? '239, 68, 68' : factor.severity === 'MEDIUM' ? '245, 158, 11' : '107, 114, 128'}, 0.15);
                                border-radius: 20px;
                                font-size: 12px;
                                font-weight: 500;
                            ">
                                <span style="color: ${factor.severity === 'CRITICAL' ? '#dc2626' : factor.severity === 'HIGH' ? '#ef4444' : factor.severity === 'MEDIUM' ? '#f59e0b' : '#6b7280'};">●</span>
                                ${factor.code}
                                <span style="color: var(--text-muted);">+${factor.score}</span>
                            </span>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
            
            <div class="result-section">
                <h4><i class="fas fa-brain"></i> AI Analysis</h4>
                <div class="reasoning-text">${(llmAnalysis.reasoning || 'Analysis completed.').replace(/\n/g, '<br>')}</div>
            </div>
            
            <div class="result-section" style="display: flex; gap: 24px; flex-wrap: wrap;">
                <div>
                    <h4><i class="fas fa-gavel"></i> Recommended Action</h4>
                    <span class="decision-badge ${actionClass}">
                        <i class="fas fa-${recommendedAction === 'BLOCK' ? 'ban' : recommendedAction === 'APPROVE' ? 'check-circle' : 'search'}"></i>
                        ${recommendedAction}
                    </span>
                </div>
                <div style="flex: 1;">
                    <h4><i class="fas fa-tasks"></i> Next Steps</h4>
                    <ul style="margin: 0; padding-left: 20px; color: var(--text-secondary); font-size: 13px;">
                        ${nextSteps.map(step => `<li>${step}</li>`).join('')}
                    </ul>
                </div>
            </div>
            
            <div style="margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border-color); font-size: 12px; color: var(--text-muted);">
                <i class="fas fa-clock"></i> Processed in ${result.processing_time_ms || 0}ms
                <span style="margin-left: 16px;"><i class="fas fa-fingerprint"></i> ${result.request_id?.substring(0, 8) || 'N/A'}</span>
            </div>
        </div>
    `;
}

function displayErrorResult(errorMessage) {
    if (!elements.resultsPanel) return;
    
    elements.resultsPanel.innerHTML = `
        <div class="analysis-result" style="animation: fadeIn 0.5s ease;">
            <div class="risk-header" style="background: rgba(239, 68, 68, 0.1);">
                <div class="risk-score-circle high" style="border-color: #ef4444;">
                    <i class="fas fa-times" style="font-size: 32px; color: #ef4444;"></i>
                </div>
                <div class="risk-info">
                    <h3>Analysis Failed</h3>
                    <span class="risk-level-badge high">Error</span>
                </div>
            </div>
            <div class="result-section">
                <h4><i class="fas fa-exclamation-circle"></i> Error Details</h4>
                <div class="alert-item" style="background: rgba(239, 68, 68, 0.1); border-left-color: #ef4444;">
                    <i class="fas fa-bug" style="color: #ef4444;"></i>
                    <span>${errorMessage}</span>
                </div>
            </div>
        </div>
    `;
}

// ============================================
// Scenario Buttons
// ============================================
function initScenarioButtons() {
    const scenarios = {
        'high-risk': {
            amount: 500000,
            originCountry: 'RU',
            destCountry: 'KY',
            transactionType: 'WIRE_TRANSFER',
            customerName: 'Moscow Trading LLC',
            customerType: 'CORPORATE',
            accountAge: 32
        },
        'structuring': {
            amount: 9500,
            originCountry: 'US',
            destCountry: 'PA',
            transactionType: 'CASH',
            customerName: 'John Smith',
            customerType: 'INDIVIDUAL',
            accountAge: 15
        },
        'crypto': {
            amount: 75000,
            originCountry: 'CN',
            destCountry: 'SG',
            transactionType: 'CRYPTO',
            customerName: 'Digital Assets Corp',
            customerType: 'CORPORATE',
            accountAge: 60
        },
        'normal': {
            amount: 1500,
            originCountry: 'US',
            destCountry: 'GB',
            transactionType: 'WIRE_TRANSFER',
            customerName: 'Jane Doe',
            customerType: 'INDIVIDUAL',
            accountAge: 730
        }
    };
    
    document.querySelectorAll('.scenario-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const scenarioKey = btn.dataset.scenario;
            const scenario = scenarios[scenarioKey];
            
            if (scenario) {
                if (elements.amount) elements.amount.value = scenario.amount;
                if (elements.originCountry) elements.originCountry.value = scenario.originCountry;
                if (elements.destCountry) elements.destCountry.value = scenario.destCountry;
                if (elements.transactionType) elements.transactionType.value = scenario.transactionType;
                if (elements.customerName) elements.customerName.value = scenario.customerName;
                if (elements.customerType) elements.customerType.value = scenario.customerType;
                if (elements.accountAge) elements.accountAge.value = scenario.accountAge;
                
                showNotification(`Loaded "${scenarioKey}" scenario`, 'info');
                document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
}

// ============================================
// Animations
// ============================================
function initAnimations() {
    const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    document.querySelectorAll('.feature-card, .tech-card, .endpoint-card, .arch-layer').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
    
    if (!document.getElementById('animationStyles')) {
        const style = document.createElement('style');
        style.id = 'animationStyles';
        style.textContent = `.animate-in { opacity: 1 !important; transform: translateY(0) !important; }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }`;
        document.head.appendChild(style);
    }
}

function initCounterAnimation() {
    const counters = document.querySelectorAll('.stat-value');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const counter = entry.target;
                const target = counter.dataset.count || counter.textContent.replace(/[^0-9.]/g, '');
                const suffix = counter.dataset.suffix || counter.textContent.replace(/[0-9.]/g, '').trim();
                animateCounter(counter, parseFloat(target) || 0, suffix);
                observer.unobserve(counter);
            }
        });
    }, { threshold: 0.5 });
    
    counters.forEach(counter => {
        const text = counter.textContent;
        const numMatch = text.match(/[\d.]+/);
        if (numMatch) {
            counter.dataset.count = numMatch[0];
            counter.dataset.suffix = text.replace(/[\d.]+/, '').trim();
            counter.textContent = '0' + counter.dataset.suffix;
        }
        observer.observe(counter);
    });
}

function animateCounter(element, target, suffix) {
    const duration = CONFIG.ANIMATION.counterDuration;
    const start = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - start;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = target * easeOut;
        const displayValue = target % 1 !== 0 ? current.toFixed(1) : Math.round(current);
        element.textContent = displayValue + suffix;
        if (progress < 1) requestAnimationFrame(update);
    }
    
    requestAnimationFrame(update);
}

// ============================================
// Notifications
// ============================================
function showNotification(message, type = 'info') {
    document.querySelectorAll('.notification').forEach(n => n.remove());
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    
    const icons = { success: 'check-circle', error: 'exclamation-circle', info: 'info-circle', warning: 'exclamation-triangle' };
    const colors = { success: 'rgba(16, 185, 129, 0.95)', error: 'rgba(239, 68, 68, 0.95)', info: 'rgba(59, 130, 246, 0.95)', warning: 'rgba(245, 158, 11, 0.95)' };
    
    notification.innerHTML = `<i class="fas fa-${icons[type] || 'info-circle'}"></i><span>${message}</span>`;
    
    Object.assign(notification.style, {
        position: 'fixed', bottom: '24px', right: '24px', padding: '16px 24px', borderRadius: '12px',
        display: 'flex', alignItems: 'center', gap: '12px', fontSize: '14px', fontWeight: '500', zIndex: '10000',
        animation: 'slideIn 0.3s ease', background: colors[type] || colors.info, color: 'white',
        backdropFilter: 'blur(10px)', boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)'
    });
    
    document.body.appendChild(notification);
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

if (!document.getElementById('notificationStyles')) {
    const style = document.createElement('style');
    style.id = 'notificationStyles';
    style.textContent = `@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }`;
    document.head.appendChild(style);
}

console.log('%c🛡️ SentinelAI v2.0', 'font-size: 24px; font-weight: bold; color: #6366f1;');
console.log('%cFinancial Crime Intelligence Platform', 'font-size: 14px; color: #a1a1aa;');
