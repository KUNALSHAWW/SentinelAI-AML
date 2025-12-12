/**
 * SentinelAI - Enterprise AML Detection Platform
 * Frontend Application JavaScript v3.0
 * 
 * REFACTORED: Now uses real RAG-powered backend API
 * - Removed hardcoded simulation logic
 * - Real-time web search for corporate entities
 * - LLM-powered analysis via HuggingFace
 */

// ============================================
// Configuration
// ============================================
const CONFIG = {
    // CHANGE IS HERE: 
    // Logic: "Are we running locally? If yes, use localhost:8000. If no (we are on cloud), use relative path."
    API_BASE_URL: (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') 
        ? 'http://127.0.0.1:8000' 
        : '', // Empty string means "use the same domain I am currently on"

    ENDPOINTS: {
        health: '/health',
        analyze: '/api/v1/analyze/rag',       // NEW: RAG-powered endpoint
        analyzeRules: '/api/v1/analyze/rules', // Fallback: rule-based endpoint
        analyzeLLM: '/api/v1/analyze',        // Legacy LLM endpoint
        cases: '/api/v1/cases'
    },
    ANIMATION: {
        counterDuration: 2000,
        typingSpeed: 50
    },
    // Request timeouts
    TIMEOUTS: {
        health: 10000,
        analysis: 120000  // RAG + LLM can take up to 2 minutes
    }
};

// ============================================
// State Management
// ============================================
const state = {
    isLoading: false,
    apiStatus: 'checking',
    lastAnalysis: null,
    analysisMode: 'rag'  // 'rag', 'llm', 'rules'
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
    console.log('🛡️ SentinelAI Frontend v3.0 (RAG-Powered) Initializing...');
    
    cacheElements();
    initNavigation();
    initNeuralNetwork();
    initAPIStatusCheck();
    initForm();
    initScenarioButtons();
    initAnimations();
    initCounterAnimation();
    
    console.log('✅ SentinelAI Frontend Ready');
    console.log('📡 API Endpoint:', CONFIG.API_BASE_URL || window.location.origin);
    console.log('🧠 Analysis Mode: RAG + LLM (Real AI)');
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
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.TIMEOUTS.health);
        
        const response = await fetch(`${CONFIG.API_BASE_URL}/health`, {
            method: 'GET',
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
            const data = await response.json();
            state.apiStatus = 'online';
            state.analysisMode = 'rag';
            updateAPIStatus('online', 'AI Ready');
            console.log('✅ API Status:', data);
        } else {
            throw new Error('API returned non-OK status');
        }
    } catch (error) {
        state.apiStatus = 'offline';
        state.analysisMode = 'rules';
        updateAPIStatus('warning', 'Fallback Mode');
        console.warn('⚠️ API check failed, will try on analysis:', error.message);
    }
}

function updateAPIStatus(status, text) {
    if (elements.statusDot) {
        const colors = {
            'checking': '#f59e0b',
            'online': '#10b981',
            'offline': '#ef4444',
            'warning': '#f59e0b'
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

/**
 * Main transaction analysis function
 * Now calls real RAG-powered backend API
 */
async function analyzeTransaction() {
    if (state.isLoading) return;
    
    // Gather form data
    const amount = parseFloat(elements.amount?.value) || 0;
    const originCountry = elements.originCountry?.value || 'US';
    const destCountry = elements.destCountry?.value || 'US';
    const transactionType = elements.transactionType?.value || 'WIRE_TRANSFER';
    const customerName = elements.customerName?.value || 'Demo Customer';
    const customerType = elements.customerType?.value || 'INDIVIDUAL';
    const accountAge = parseInt(elements.accountAge?.value) || 365;
    
    // Validation
    if (!amount || amount <= 0) {
        showNotification('Please enter a valid amount', 'error');
        return;
    }
    
    state.isLoading = true;
    updateLoadingState(true);
    
    // Determine if RAG will be triggered (corporate entity check)
    const isCorporate = isCorporateEntity(customerName, customerType);
    const statusMessage = isCorporate 
        ? 'Searching entity intelligence & analyzing with AI...' 
        : 'Analyzing transaction with AI...';
    
    showNotification(statusMessage, 'info');
    showAnalysisProgress(isCorporate);
    
    // Build request payload for RAG API
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
        enable_rag: true,
        enable_llm: true
    };
    
    console.log('📤 RAG Analysis Request:', requestData);
    
    try {
        // Call the real RAG API
        const result = await callRAGAPI(requestData);
        
        console.log('📥 RAG Analysis Result:', result);
        state.lastAnalysis = result;
        displayResults(result);
        
        const modeLabel = result._rag_enabled ? 'RAG + LLM' : 'LLM';
        showNotification(`Analysis completed with ${modeLabel}!`, 'success');
        
    } catch (error) {
        console.error('❌ RAG Analysis Error:', error);
        
        // Attempt fallback to rule-based endpoint
        console.log('🔄 Attempting fallback to rule-based analysis...');
        
        try {
            const fallbackResult = await callRulesAPI(requestData);
            state.lastAnalysis = fallbackResult;
            displayResults(fallbackResult);
            showNotification('Analysis completed (Rule-Based Fallback)', 'warning');
        } catch (fallbackError) {
            showNotification(`Analysis failed: ${error.message}`, 'error');
            displayErrorResult(error.message);
        }
    } finally {
        state.isLoading = false;
        updateLoadingState(false);
        hideAnalysisProgress();
    }
}

/**
 * Check if customer represents a corporate entity
 * (determines if RAG web search will be triggered)
 */
function isCorporateEntity(customerName, customerType) {
    if (customerType?.toUpperCase() === 'CORPORATE' || 
        customerType?.toUpperCase() === 'FINANCIAL_INSTITUTION') {
        return true;
    }
    
    const corporateIndicators = [
        'ltd', 'llc', 'inc', 'corp', 'corporation', 'limited',
        'gmbh', 'plc', 'llp', 'lp', 'sa', 'ag', 'nv', 'bv',
        'company', 'co.', 'holdings', 'group', 'international',
        'enterprises', 'partners', 'investments', 'capital',
        'bank', 'financial', 'trust', 'fund', 'asset'
    ];
    
    const nameLower = customerName.toLowerCase();
    return corporateIndicators.some(indicator => nameLower.includes(indicator));
}

/**
 * Call the RAG-powered analysis API
 */
async function callRAGAPI(requestData) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), CONFIG.TIMEOUTS.analysis);
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.analyze}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-API-Key': 'demo-key'
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
            throw new Error('Request timeout - RAG analysis is taking longer than expected');
        }
        throw error;
    }
}

/**
 * Call the rule-based analysis API (fallback)
 */
async function callRulesAPI(requestData) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    try {
        // Convert to the expected schema format
        const rulesRequestData = {
            transaction: {
                amount: requestData.transaction.amount,
                currency: requestData.transaction.currency,
                origin_country: requestData.transaction.origin_country,
                destination_country: requestData.transaction.destination_country,
                transaction_type: requestData.transaction.transaction_type,
                timestamp: requestData.transaction.timestamp
            },
            customer: {
                name: requestData.customer.name,
                customer_type: requestData.customer.customer_type,
                account_age_days: requestData.customer.account_age_days
            },
            enable_llm_analysis: false
        };
        
        const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.analyzeRules}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-API-Key': 'demo-key'
            },
            body: JSON.stringify(rulesRequestData),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const result = await response.json();
        result._simulation = false;
        result._fallback = true;
        return result;
    } catch (error) {
        clearTimeout(timeoutId);
        throw error;
    }
}

/**
 * Show analysis progress indicator
 */
function showAnalysisProgress(includeRAG) {
    if (!elements.resultsPanel) return;
    
    const steps = includeRAG ? [
        { icon: 'search', text: 'Searching entity intelligence...', delay: 0 },
        { icon: 'globe', text: 'Retrieving web sources...', delay: 2000 },
        { icon: 'newspaper', text: 'Checking adverse media...', delay: 4000 },
        { icon: 'brain', text: 'Running AI analysis...', delay: 6000 },
        { icon: 'chart-line', text: 'Calculating risk score...', delay: 9000 }
    ] : [
        { icon: 'brain', text: 'Running AI analysis...', delay: 0 },
        { icon: 'chart-line', text: 'Calculating risk score...', delay: 3000 }
    ];
    
    elements.resultsPanel.innerHTML = `
        <div class="analysis-progress" style="padding: 40px; text-align: center;">
            <div class="progress-spinner" style="margin-bottom: 24px;">
                <div style="width: 60px; height: 60px; border: 3px solid rgba(99, 102, 241, 0.2); border-top-color: #6366f1; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto;"></div>
            </div>
            <div id="progressSteps" style="text-align: left; max-width: 300px; margin: 0 auto;">
                ${steps.map((step, i) => `
                    <div class="progress-step" data-step="${i}" style="display: flex; align-items: center; gap: 12px; padding: 8px 0; opacity: 0.4; transition: opacity 0.3s;">
                        <i class="fas fa-${step.icon}" style="color: #6366f1; width: 20px;"></i>
                        <span>${step.text}</span>
                        <i class="fas fa-check" style="color: #10b981; margin-left: auto; display: none;"></i>
                    </div>
                `).join('')}
            </div>
            <p style="margin-top: 20px; font-size: 12px; color: var(--text-muted);">
                ${includeRAG ? 'RAG + LLM analysis may take 15-60 seconds' : 'LLM analysis in progress...'}
            </p>
        </div>
    `;
    
    // Add spin animation if not exists
    if (!document.getElementById('spinAnimation')) {
        const style = document.createElement('style');
        style.id = 'spinAnimation';
        style.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
        document.head.appendChild(style);
    }
    
    // Animate progress steps
    steps.forEach((step, index) => {
        setTimeout(() => {
            const stepEl = document.querySelector(`[data-step="${index}"]`);
            if (stepEl) {
                stepEl.style.opacity = '1';
                // Mark previous step as complete
                if (index > 0) {
                    const prevStep = document.querySelector(`[data-step="${index - 1}"]`);
                    if (prevStep) {
                        prevStep.querySelector('.fa-check').style.display = 'inline';
                    }
                }
            }
        }, step.delay);
    });
}

function hideAnalysisProgress() {
    // Progress will be replaced by results
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
    const ragAnalysis = result.rag_analysis || null;
    const recommendedAction = result.recommended_action || 'REVIEW';
    const nextSteps = result.next_steps || [];
    const sarRequired = result.sar_required || false;
    const isRAGEnabled = result._rag_enabled || false;
    const isFallback = result._fallback || false;
    
    const riskLevelClass = riskLevel.toLowerCase();
    const actionClass = recommendedAction === 'BLOCK' ? 'block' : 
                        recommendedAction === 'ESCALATE' ? 'review' : 
                        recommendedAction === 'REVIEW' ? 'review' : 'approve';
    
    elements.resultsPanel.innerHTML = `
        <div class="analysis-result" style="animation: fadeIn 0.5s ease;">
            <!-- Analysis Mode Badge -->
            <div style="background: ${isRAGEnabled ? 'rgba(16, 185, 129, 0.1)' : 'rgba(99, 102, 241, 0.1)'}; border: 1px solid ${isRAGEnabled ? 'rgba(16, 185, 129, 0.3)' : 'rgba(99, 102, 241, 0.3)'}; border-radius: 8px; padding: 12px; margin-bottom: 16px; font-size: 12px; color: ${isRAGEnabled ? '#10b981' : '#6366f1'};">
                <i class="fas fa-${isRAGEnabled ? 'robot' : 'brain'}"></i> 
                <strong>${isRAGEnabled ? 'RAG + LLM Analysis' : isFallback ? 'Rule-Based Analysis' : 'LLM Analysis'}</strong>
                ${isRAGEnabled ? ' - Entity intelligence retrieved via web search' : ''}
            </div>
            
            <!-- Risk Score Header -->
            <div class="risk-header">
                <div class="risk-score-circle ${riskLevelClass}">
                    <span class="risk-score-value">${Math.round(riskScore)}</span>
                    <span class="risk-score-label">Risk Score</span>
                </div>
                <div class="risk-info">
                    <h3>Analysis Complete</h3>
                    <span class="risk-level-badge ${riskLevelClass}">${riskLevel} Risk</span>
                    ${sarRequired ? '<span class="risk-level-badge high" style="margin-left: 8px;"><i class="fas fa-exclamation-triangle"></i> SAR Required</span>' : ''}
                    ${llmAnalysis.confidence_score ? `<span style="margin-left: 8px; font-size: 12px; color: var(--text-muted);">Confidence: ${(llmAnalysis.confidence_score * 100).toFixed(0)}%</span>` : ''}
                </div>
            </div>
            
            <!-- RAG Analysis Section (if enabled) -->
            ${ragAnalysis ? `
                <div class="result-section" style="background: rgba(99, 102, 241, 0.05); border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                    <h4><i class="fas fa-search"></i> Entity Intelligence (RAG)</h4>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-top: 12px;">
                        <div>
                            <span style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Entity Searched</span>
                            <p style="margin: 4px 0; font-weight: 500;">${ragAnalysis.entity_searched}</p>
                        </div>
                        <div>
                            <span style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Sources Analyzed</span>
                            <p style="margin: 4px 0; font-weight: 500;">${ragAnalysis.sources_analyzed || 0}</p>
                        </div>
                        <div>
                            <span style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Adverse Media</span>
                            <p style="margin: 4px 0; font-weight: 500; color: ${ragAnalysis.adverse_media_found ? '#ef4444' : '#10b981'};">
                                ${ragAnalysis.adverse_media_found ? '⚠️ DETECTED' : '✓ None Found'}
                            </p>
                        </div>
                        ${ragAnalysis.sanctions_indicators?.length ? `
                            <div>
                                <span style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Sanctions Keywords</span>
                                <p style="margin: 4px 0; font-weight: 500; color: #ef4444;">${ragAnalysis.sanctions_indicators.join(', ')}</p>
                            </div>
                        ` : ''}
                    </div>
                    ${ragAnalysis.key_findings?.length ? `
                        <div style="margin-top: 12px;">
                            <span style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Key Findings</span>
                            <ul style="margin: 8px 0 0 0; padding-left: 20px; font-size: 13px;">
                                ${ragAnalysis.key_findings.slice(0, 5).map(f => `<li>${f}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            ` : ''}
            
            <!-- Alerts Section -->
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
            
            <!-- Risk Factors -->
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
            
            <!-- AI Analysis -->
            <div class="result-section">
                <h4><i class="fas fa-brain"></i> AI Analysis</h4>
                <div class="reasoning-text">${(llmAnalysis.reasoning || 'Analysis completed.').replace(/\n/g, '<br>')}</div>
            </div>
            
            <!-- Actions -->
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
            
            <!-- Footer -->
            <div style="margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border-color); font-size: 12px; color: var(--text-muted);">
                <i class="fas fa-clock"></i> Processed in ${result.processing_time_ms || 0}ms
                <span style="margin-left: 16px;"><i class="fas fa-fingerprint"></i> ${result.request_id?.substring(0, 8) || 'N/A'}</span>
                ${isRAGEnabled ? '<span style="margin-left: 16px;"><i class="fas fa-globe"></i> RAG Enabled</span>' : ''}
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
            <div class="result-section">
                <h4><i class="fas fa-lightbulb"></i> Troubleshooting</h4>
                <ul style="margin: 0; padding-left: 20px; color: var(--text-secondary); font-size: 13px;">
                    <li>Check if the API server is running</li>
                    <li>Verify API keys are configured (HUGGINGFACE_API_KEY, GROQ_API_KEY)</li>
                    <li>Try again in a few moments (API may be warming up)</li>
                    <li>Check browser console for detailed error information</li>
                </ul>
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

// ============================================
// Console Branding
// ============================================
console.log('%c🛡️ SentinelAI v3.0', 'font-size: 24px; font-weight: bold; color: #6366f1;');
console.log('%cFinancial Crime Intelligence Platform', 'font-size: 14px; color: #a1a1aa;');
console.log('%c🧠 RAG + LLM Powered Analysis', 'font-size: 12px; color: #10b981;');
