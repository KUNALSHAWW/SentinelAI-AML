/**
 * SentinelAI - Enterprise AML Detection Platform
 * Frontend Application JavaScript
 */

// ============================================
// Configuration
// ============================================
const CONFIG = {
    API_BASE_URL: 'https://sentinelai-api.onrender.com',
    ENDPOINTS: {
        health: '/health',
        analyze: '/api/v1/analysis/analyze',
        cases: '/api/v1/cases'
    },
    ANIMATION: {
        counterDuration: 2000,
        typingSpeed: 50
    }
};

// ============================================
// State Management
// ============================================
const state = {
    isLoading: false,
    apiStatus: 'checking',
    lastAnalysis: null
};

// ============================================
// DOM Elements
// ============================================
const elements = {
    // Navigation
    navbar: document.querySelector('.navbar'),
    mobileMenuBtn: document.querySelector('.mobile-menu-btn'),
    mobileMenu: document.querySelector('.mobile-menu'),
    
    // API Status
    statusDot: document.querySelector('.status-dot'),
    statusText: document.querySelector('.status-text'),
    
    // Form Elements
    analyzeForm: document.getElementById('analyzeForm'),
    amountInput: document.getElementById('amount'),
    senderCountry: document.getElementById('senderCountry'),
    receiverCountry: document.getElementById('receiverCountry'),
    transactionType: document.getElementById('transactionType'),
    analyzeBtn: document.querySelector('.btn-analyze'),
    
    // Results
    resultsPanel: document.querySelector('.results-placeholder')?.parentElement,
    
    // Stats
    statValues: document.querySelectorAll('.stat-value')
};

// ============================================
// Initialization
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    console.log('🛡️ SentinelAI Frontend Initializing...');
    
    // Initialize components
    initNavigation();
    initNeuralNetwork();
    initAPIStatusCheck();
    initForm();
    initScenarioButtons();
    initAnimations();
    initCounterAnimation();
    
    console.log('✅ SentinelAI Frontend Ready');
}

// ============================================
// Navigation
// ============================================
function initNavigation() {
    // Scroll effect for navbar
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            elements.navbar?.classList.add('scrolled');
        } else {
            elements.navbar?.classList.remove('scrolled');
        }
    });
    
    // Mobile menu toggle
    elements.mobileMenuBtn?.addEventListener('click', () => {
        elements.mobileMenu?.classList.toggle('active');
        elements.mobileMenuBtn.classList.toggle('active');
    });
    
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                // Close mobile menu if open
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
    let animationId;
    
    // Resize canvas
    function resize() {
        canvas.width = canvas.offsetWidth * 2;
        canvas.height = canvas.offsetHeight * 2;
        ctx.scale(2, 2);
        initNodes();
    }
    
    // Initialize nodes
    function initNodes() {
        nodes = [];
        connections = [];
        const centerX = canvas.offsetWidth / 2;
        const centerY = canvas.offsetHeight / 2;
        const radius = Math.min(centerX, centerY) * 0.8;
        
        // Create orbital nodes
        for (let i = 0; i < 12; i++) {
            const angle = (i / 12) * Math.PI * 2;
            const r = radius * (0.5 + Math.random() * 0.5);
            nodes.push({
                x: centerX + Math.cos(angle) * r,
                y: centerY + Math.sin(angle) * r,
                baseX: centerX + Math.cos(angle) * r,
                baseY: centerY + Math.sin(angle) * r,
                radius: 4 + Math.random() * 4,
                angle: angle,
                speed: 0.001 + Math.random() * 0.002,
                orbitRadius: r
            });
        }
        
        // Create connections
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                if (Math.random() > 0.5) {
                    connections.push({ from: i, to: j, active: false, progress: 0 });
                }
            }
        }
    }
    
    // Animation loop
    function animate() {
        ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight);
        const centerX = canvas.offsetWidth / 2;
        const centerY = canvas.offsetHeight / 2;
        
        // Update node positions
        nodes.forEach(node => {
            node.angle += node.speed;
            node.x = centerX + Math.cos(node.angle) * node.orbitRadius;
            node.y = centerY + Math.sin(node.angle) * node.orbitRadius;
        });
        
        // Draw connections
        connections.forEach(conn => {
            const from = nodes[conn.from];
            const to = nodes[conn.to];
            
            ctx.beginPath();
            ctx.moveTo(from.x, from.y);
            ctx.lineTo(to.x, to.y);
            ctx.strokeStyle = 'rgba(99, 102, 241, 0.15)';
            ctx.lineWidth = 1;
            ctx.stroke();
            
            // Animate data flow
            if (Math.random() > 0.995) {
                conn.active = true;
                conn.progress = 0;
            }
            
            if (conn.active) {
                conn.progress += 0.02;
                if (conn.progress >= 1) {
                    conn.active = false;
                }
                
                const x = from.x + (to.x - from.x) * conn.progress;
                const y = from.y + (to.y - from.y) * conn.progress;
                
                ctx.beginPath();
                ctx.arc(x, y, 3, 0, Math.PI * 2);
                ctx.fillStyle = '#6366f1';
                ctx.fill();
            }
        });
        
        // Draw nodes
        nodes.forEach(node => {
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, node.radius);
            gradient.addColorStop(0, 'rgba(99, 102, 241, 0.8)');
            gradient.addColorStop(1, 'rgba(139, 92, 246, 0.4)');
            ctx.fillStyle = gradient;
            ctx.fill();
        });
        
        animationId = requestAnimationFrame(animate);
    }
    
    resize();
    animate();
    
    window.addEventListener('resize', resize);
}

// ============================================
// API Status Check
// ============================================
async function initAPIStatusCheck() {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/health`, {
            method: 'GET',
            timeout: 10000
        });
        
        if (response.ok) {
            const data = await response.json();
            state.apiStatus = 'online';
            if (statusDot) statusDot.style.background = '#10b981';
            if (statusText) statusText.textContent = 'API Online';
            console.log('✅ API Status:', data);
        } else {
            throw new Error('API returned non-OK status');
        }
    } catch (error) {
        state.apiStatus = 'offline';
        if (statusDot) statusDot.style.background = '#ef4444';
        if (statusText) statusText.textContent = 'API Offline';
        console.warn('⚠️ API Status Check Failed:', error.message);
    }
}

// ============================================
// Form Handling
// ============================================
function initForm() {
    const form = document.getElementById('analyzeForm');
    if (!form) return;
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await analyzeTransaction();
    });
}

async function analyzeTransaction() {
    if (state.isLoading) return;
    
    const amount = document.getElementById('amount')?.value;
    const senderCountry = document.getElementById('senderCountry')?.value;
    const receiverCountry = document.getElementById('receiverCountry')?.value;
    const transactionType = document.getElementById('transactionType')?.value;
    
    if (!amount || !senderCountry || !receiverCountry || !transactionType) {
        showNotification('Please fill in all fields', 'error');
        return;
    }
    
    state.isLoading = true;
    updateLoadingState(true);
    
    try {
        const payload = {
            case_id: generateCaseId(),
            transaction: {
                amount: parseFloat(amount),
                currency: 'USD',
                sender_country: senderCountry,
                receiver_country: receiverCountry,
                transaction_type: transactionType,
                timestamp: new Date().toISOString()
            },
            customer: {
                id: 'CUST-' + Math.random().toString(36).substr(2, 9).toUpperCase(),
                name: 'Demo Customer',
                risk_rating: 'medium'
            }
        };
        
        console.log('📤 Sending analysis request:', payload);
        
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/v1/analysis/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `API Error: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('📥 Analysis result:', result);
        
        state.lastAnalysis = result;
        displayResults(result);
        showNotification('Analysis completed successfully!', 'success');
        
    } catch (error) {
        console.error('❌ Analysis Error:', error);
        showNotification(`Analysis failed: ${error.message}`, 'error');
        displayErrorResult(error.message);
    } finally {
        state.isLoading = false;
        updateLoadingState(false);
    }
}

function generateCaseId() {
    return 'CASE-' + Date.now().toString(36).toUpperCase() + '-' + 
           Math.random().toString(36).substr(2, 5).toUpperCase();
}

function updateLoadingState(isLoading) {
    const btn = document.querySelector('.btn-analyze');
    if (!btn) return;
    
    if (isLoading) {
        btn.classList.add('loading');
        btn.disabled = true;
    } else {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}

// ============================================
// Results Display
// ============================================
function displayResults(result) {
    const container = document.querySelector('.panel-content:last-of-type') || 
                     document.querySelector('.results-placeholder')?.parentElement;
    if (!container) return;
    
    // Extract risk information
    const riskScore = result.risk_score || result.overall_risk_score || 75;
    const riskLevel = getRiskLevel(riskScore);
    const alerts = result.alerts || result.risk_factors || [];
    const reasoning = result.reasoning || result.analysis_summary || 'Analysis completed using multi-agent AI system.';
    const decision = result.decision || result.recommended_action || getDecision(riskScore);
    
    container.innerHTML = `
        <div class="analysis-result">
            <div class="risk-header">
                <div class="risk-score-circle ${riskLevel.toLowerCase()}">
                    <span class="risk-score-value">${Math.round(riskScore)}</span>
                    <span class="risk-score-label">Risk Score</span>
                </div>
                <div class="risk-info">
                    <h3>Analysis Complete</h3>
                    <span class="risk-level-badge ${riskLevel.toLowerCase()}">${riskLevel} Risk</span>
                </div>
            </div>
            
            <div class="result-section">
                <h4><i class="fas fa-exclamation-triangle"></i> Risk Indicators</h4>
                ${alerts.length > 0 ? alerts.map(alert => `
                    <div class="alert-item">
                        <i class="fas fa-flag"></i>
                        <span>${typeof alert === 'string' ? alert : alert.description || alert.message || JSON.stringify(alert)}</span>
                    </div>
                `).join('') : `
                    <div class="alert-item" style="background: rgba(16, 185, 129, 0.1); border-color: #10b981;">
                        <i class="fas fa-check-circle" style="color: #10b981;"></i>
                        <span>No significant risk indicators detected</span>
                    </div>
                `}
            </div>
            
            <div class="result-section">
                <h4><i class="fas fa-brain"></i> AI Reasoning</h4>
                <div class="reasoning-text">${reasoning}</div>
            </div>
            
            <div class="result-section">
                <h4><i class="fas fa-gavel"></i> Recommended Action</h4>
                <span class="decision-badge ${decision.toLowerCase()}">
                    <i class="fas fa-${decision === 'BLOCK' ? 'ban' : decision === 'REVIEW' ? 'search' : 'check'}"></i>
                    ${decision}
                </span>
            </div>
        </div>
    `;
}

function displayErrorResult(errorMessage) {
    const container = document.querySelector('.panel-content:last-of-type') || 
                     document.querySelector('.results-placeholder')?.parentElement;
    if (!container) return;
    
    container.innerHTML = `
        <div class="analysis-result">
            <div class="risk-header" style="background: rgba(239, 68, 68, 0.1);">
                <div class="risk-score-circle high">
                    <i class="fas fa-times" style="font-size: 32px; color: #ef4444;"></i>
                </div>
                <div class="risk-info">
                    <h3>Analysis Failed</h3>
                    <span class="risk-level-badge high">Error</span>
                </div>
            </div>
            <div class="result-section">
                <h4><i class="fas fa-exclamation-circle"></i> Error Details</h4>
                <div class="alert-item">
                    <i class="fas fa-bug"></i>
                    <span>${errorMessage}</span>
                </div>
                <p style="color: var(--text-muted); margin-top: 16px; font-size: 14px;">
                    The API might be starting up (cold start takes ~30-60 seconds on free tier). 
                    Please try again in a moment.
                </p>
            </div>
        </div>
    `;
}

function getRiskLevel(score) {
    if (score >= 80) return 'CRITICAL';
    if (score >= 60) return 'HIGH';
    if (score >= 40) return 'MEDIUM';
    return 'LOW';
}

function getDecision(score) {
    if (score >= 80) return 'BLOCK';
    if (score >= 60) return 'REVIEW';
    return 'APPROVE';
}

// ============================================
// Scenario Buttons
// ============================================
function initScenarioButtons() {
    const scenarios = {
        structuring: {
            amount: 9500,
            senderCountry: 'US',
            receiverCountry: 'MX',
            transactionType: 'wire'
        },
        highRisk: {
            amount: 150000,
            senderCountry: 'RU',
            receiverCountry: 'CH',
            transactionType: 'wire'
        },
        layering: {
            amount: 75000,
            senderCountry: 'CN',
            receiverCountry: 'SG',
            transactionType: 'wire'
        },
        normal: {
            amount: 250,
            senderCountry: 'US',
            receiverCountry: 'GB',
            transactionType: 'payment'
        }
    };
    
    document.querySelectorAll('.scenario-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const scenarioName = btn.dataset.scenario;
            const scenario = scenarios[scenarioName];
            
            if (scenario) {
                document.getElementById('amount').value = scenario.amount;
                document.getElementById('senderCountry').value = scenario.senderCountry;
                document.getElementById('receiverCountry').value = scenario.receiverCountry;
                document.getElementById('transactionType').value = scenario.transactionType;
                
                showNotification(`Loaded "${btn.querySelector('.scenario-name').textContent}" scenario`, 'info');
                
                // Smooth scroll to demo
                document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
}

// ============================================
// Animations
// ============================================
function initAnimations() {
    // Intersection Observer for scroll animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observe elements for animation
    document.querySelectorAll('.feature-card, .tech-card, .endpoint-card, .arch-layer').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
    
    // Add animate-in class styles
    const style = document.createElement('style');
    style.textContent = `
        .animate-in {
            opacity: 1 !important;
            transform: translateY(0) !important;
        }
    `;
    document.head.appendChild(style);
}

function initCounterAnimation() {
    const counters = document.querySelectorAll('.stat-value');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const counter = entry.target;
                const target = counter.dataset.count || counter.textContent.replace(/[^0-9.]/g, '');
                const suffix = counter.querySelector('.stat-suffix')?.textContent || '';
                
                animateCounter(counter, parseFloat(target), suffix);
                observer.unobserve(counter);
            }
        });
    }, { threshold: 0.5 });
    
    counters.forEach(counter => {
        // Store original value
        const text = counter.textContent;
        const numMatch = text.match(/[\d.]+/);
        if (numMatch) {
            counter.dataset.count = numMatch[0];
            counter.innerHTML = '0' + (counter.querySelector('.stat-suffix')?.outerHTML || text.replace(/[\d.]+/, ''));
        }
        observer.observe(counter);
    });
}

function animateCounter(element, target, suffix) {
    const duration = CONFIG.ANIMATION.counterDuration;
    const start = performance.now();
    const startValue = 0;
    
    function update(currentTime) {
        const elapsed = currentTime - start;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = startValue + (target - startValue) * easeOut;
        
        // Format number
        let displayValue;
        if (target % 1 !== 0) {
            displayValue = current.toFixed(1);
        } else {
            displayValue = Math.round(current);
        }
        
        element.innerHTML = displayValue + `<span class="stat-suffix">${suffix}</span>`;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

// ============================================
// Notifications
// ============================================
function showNotification(message, type = 'info') {
    // Remove existing notifications
    document.querySelectorAll('.notification').forEach(n => n.remove());
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    // Add styles
    Object.assign(notification.style, {
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        padding: '16px 24px',
        borderRadius: '12px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        fontSize: '14px',
        fontWeight: '500',
        zIndex: '10000',
        animation: 'slideIn 0.3s ease',
        background: type === 'success' ? 'rgba(16, 185, 129, 0.9)' : 
                    type === 'error' ? 'rgba(239, 68, 68, 0.9)' : 
                    'rgba(59, 130, 246, 0.9)',
        color: 'white',
        backdropFilter: 'blur(10px)',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)'
    });
    
    document.body.appendChild(notification);
    
    // Auto remove
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

// Add notification animations
const notificationStyles = document.createElement('style');
notificationStyles.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(notificationStyles);

// ============================================
// Utility Functions
// ============================================
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ============================================
// Export for testing
// ============================================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        CONFIG,
        state,
        analyzeTransaction,
        getRiskLevel,
        getDecision,
        generateCaseId
    };
}

console.log('🛡️ SentinelAI v1.0.0 - Financial Crime Intelligence Platform');
console.log('📡 API Endpoint:', CONFIG.API_BASE_URL);
