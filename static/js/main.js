// Main JavaScript for Town Zoning Lookup Application

class ZoningApp {
    constructor() {
        this.form = document.getElementById('zoningForm');
        this.cityInput = document.getElementById('city');
        this.submitBtn = document.getElementById('submitBtn');
        this.resultDiv = document.getElementById('result');
        this.currentResult = null;
        
        this.init();
    }
    
    init() {
        this.form.addEventListener('submit', this.handleSubmit.bind(this));
        this.cityInput.addEventListener('input', this.handleInputChange.bind(this));
    }
    
    handleInputChange() {
        // Enable/disable submit button based on input
        const hasInput = this.cityInput.value.trim().length > 0;
        this.submitBtn.disabled = !hasInput;
    }
    
    async handleSubmit(e) {
        e.preventDefault();
        
        const city = this.cityInput.value.trim();
        if (!city) return;
        
        this.showLoading();
        
        try {
            const response = await fetch('/api/zoning', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ city })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.currentResult = data;
                this.showSuccess(data);
            } else {
                this.showError(data.error || 'An unknown error occurred');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showError('Failed to connect to the server. Please try again.');
        }
    }
    
    showLoading() {
        this.submitBtn.disabled = true;
        this.submitBtn.innerHTML = `
            <span class="spinner"></span>
            Searching...
        `;
        
        this.resultDiv.innerHTML = `
            <div class="result-card loading">
                <div class="status-indicator loading">
                    <span class="spinner"></span>
                    Searching for zoning ordinance...
                </div>
                <p class="mt-4">This may take a few moments as we search through municipal documents.</p>
            </div>
        `;
    }
    
    showSuccess(data) {
        this.resetSubmitButton();
        
        this.resultDiv.innerHTML = `
            <div class="result-card success">
                <div class="status-indicator success">
                    ✓ Zoning Ordinance Found
                </div>
                
                <h3 class="result-title">Document Found for ${this.escapeHtml(data.city)}</h3>
                
                <div class="result-item">
                    <div class="result-label">Document Link</div>
                    <div class="result-value">
                        <a href="${this.escapeHtml(data.link)}" target="_blank" class="result-link">
                            ${this.escapeHtml(data.link)}
                        </a>
                    </div>
                </div>
                
                <div class="result-item">
                    <div class="result-label">File Type</div>
                    <div class="result-value">${this.escapeHtml(data.file_type || 'PDF')}</div>
                </div>
                
                ${data.notes ? `
                    <div class="result-item">
                        <div class="result-label">Notes</div>
                        <div class="result-value">${this.escapeHtml(data.notes)}</div>
                    </div>
                ` : ''}
            </div>
            
            <div class="pdf-preview" id="pdfPreview">
                <h3>Verify This Document</h3>
                <p>Please review the document to ensure it's the correct zoning ordinance for ${this.escapeHtml(data.city)}.</p>
                
                <div class="pdf-actions">
                    <button type="button" class="btn btn-secondary" onclick="app.openDocument()">
                        📄 Open Document
                    </button>
                    <button type="button" class="btn btn-success" onclick="app.confirmDocument()">
                        ✓ This is Correct
                    </button>
                    <button type="button" class="btn btn-error" onclick="app.rejectDocument()">
                        ✗ This is Wrong
                    </button>
                </div>
                
                <div id="verificationResult" class="mt-4 hidden"></div>
            </div>
        `;
    }
    
    showError(message) {
        this.resetSubmitButton();
        
        this.resultDiv.innerHTML = `
            <div class="result-card error">
                <div class="status-indicator error">
                    ✗ Error
                </div>
                <h3 class="result-title">Unable to Find Zoning Ordinance</h3>
                <p><strong>Error:</strong> ${this.escapeHtml(message)}</p>
                <div class="mt-4">
                    <p><strong>Suggestions:</strong></p>
                    <ul style="margin-left: 1.5rem; margin-top: 0.5rem;">
                        <li>Try including the state (e.g., "Boston, MA")</li>
                        <li>Check the spelling of the city name</li>
                        <li>Try a nearby larger city if yours is very small</li>
                    </ul>
                </div>
            </div>
        `;
    }
    
    resetSubmitButton() {
        this.submitBtn.disabled = false;
        this.submitBtn.innerHTML = `
            🔍 Find Zoning Ordinance
        `;
    }
    
    openDocument() {
        if (this.currentResult && this.currentResult.link) {
            window.open(this.currentResult.link, '_blank');
        }
    }
    
    confirmDocument() {
        const verificationDiv = document.getElementById('verificationResult');
        verificationDiv.className = 'mt-4';
        verificationDiv.innerHTML = `
            <div class="status-indicator success">
                ✓ Document Verified
            </div>
            <p class="mt-4">Great! This document has been confirmed as the correct zoning ordinance. 
            In the future, this will be analyzed against zoning best practices.</p>
        `;
        
        // TODO: Send verification to backend
        console.log('Document confirmed:', this.currentResult);
    }
    
    rejectDocument() {
        const verificationDiv = document.getElementById('verificationResult');
        verificationDiv.className = 'mt-4';
        verificationDiv.innerHTML = `
            <div class="status-indicator error">
                ✗ Document Rejected
            </div>
            <p class="mt-4">Thank you for the feedback. You can try searching again with a more specific city name or state.</p>
            <button type="button" class="btn btn-secondary mt-4" onclick="app.searchAgain()">
                Try Another Search
            </button>
        `;
        
        // TODO: Send rejection to backend for learning
        console.log('Document rejected:', this.currentResult);
    }
    
    searchAgain() {
        this.resultDiv.innerHTML = '';
        this.cityInput.focus();
        this.currentResult = null;
    }
    
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }
}

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.app = new ZoningApp();
    initStickyHeader();
});

// Sticky header functionality
function initStickyHeader() {
    const header = document.getElementById('siteHeader');
    const headerHeight = header.offsetHeight;
    let isScrolled = false;
    
    window.addEventListener('scroll', function() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        if (scrollTop > headerHeight / 2 && !isScrolled) {
            header.classList.add('scrolled');
            isScrolled = true;
        } else if (scrollTop <= headerHeight / 2 && isScrolled) {
            header.classList.remove('scrolled');
            isScrolled = false;
        }
    });
}

// Utility functions for enhanced UX
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