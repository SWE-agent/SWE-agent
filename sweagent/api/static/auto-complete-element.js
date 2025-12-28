// Simplified auto-complete element based on GitHub's auto-complete-element
// Customized for use with our existing GitHub search API endpoint

class AutoCompleteElement extends HTMLElement {
    constructor() {
        super();
        this._inputElement = null;
        this._resultsElement = null;
        this._clearButton = null;
        this._feedbackElement = null;
        this._requestController = null;
        this._timeout = null;
        this._interactingWithList = false;
        
        // Store event handler references for cleanup
        this._inputChangeHandler = (e) => this._onInputChange(e);
        this._keyDownHandler = (e) => this._onKeyDown(e);
        this._focusHandler = () => this._onFocus();
        this._blurHandler = () => this._onBlur();
        this._clearClickHandler = (e) => this._handleClear(e);
    }

    static get observedAttributes() {
        return ['open', 'value'];
    }

    connectedCallback() {
        // Find child elements
        const input = this.querySelector('input');
        const results = this.querySelector('ul');
        const clearButton = this.querySelector('button');
        const feedback = this.querySelector('div[id$="-feedback"]');

        if (input) {
            this._inputElement = input;
            this._inputElement.setAttribute('autocomplete', 'off');
            this._inputElement.setAttribute('spellcheck', 'false');
            
            // Set up event listeners
            this._inputElement.addEventListener('input', this._inputChangeHandler);
            this._inputElement.addEventListener('keydown', this._keyDownHandler);
            this._inputElement.addEventListener('focus', this._focusHandler);
            this._inputElement.addEventListener('blur', this._blurHandler);
        }

        if (results) {
            this._resultsElement = results;
            this._resultsElement.setAttribute('role', 'listbox');
            this._resultsElement.hidden = true;
        }

        if (clearButton) {
            this._clearButton = clearButton;
            this._clearButton.addEventListener('click', this._clearClickHandler);
        }

        if (feedback) {
            this._feedbackElement = feedback;
            this._feedbackElement.setAttribute('aria-live', 'polite');
            this._feedbackElement.setAttribute('aria-atomic', 'true');
        }
    }

    disconnectedCallback() {
        // Clean up event listeners - use the stored references
        if (this._inputElement) {
            this._inputElement.removeEventListener('input', this._inputChangeHandler);
            this._inputElement.removeEventListener('keydown', this._keyDownHandler);
            this._inputElement.removeEventListener('focus', this._focusHandler);
            this._inputElement.removeEventListener('blur', this._blurHandler);
        }

        if (this._clearButton) {
            this._clearButton.removeEventListener('click', this._clearClickHandler);
        }
    }

    attributeChangedCallback(name, oldValue, newValue) {
        if (name === 'open') {
            if (newValue !== null) {
                this.open();
            } else {
                this.close();
            }
        } else if (name === 'value' && newValue !== null) {
            if (this._inputElement) {
                this._inputElement.value = newValue;
            }
        }
    }

    get src() {
        return this.getAttribute('src') || '';
    }

    set src(url) {
        this.setAttribute('src', url);
    }

    get value() {
        return this.getAttribute('value') || '';
    }

    set value(value) {
        this.setAttribute('value', value);
    }

    get open() {
        return this.hasAttribute('open');
    }

    set open(value) {
        if (value) {
            this.setAttribute('open', '');
        } else {
            this.removeAttribute('open');
        }
    }

    get fetchOnEmpty() {
        return this.hasAttribute('fetch-on-empty');
    }

    set fetchOnEmpty(fetchOnEmpty) {
        this.toggleAttribute('fetch-on-empty', fetchOnEmpty);
    }

    async _onInputChange(e) {
        if (this._feedbackElement && this._feedbackElement.textContent) {
            this._feedbackElement.textContent = '';
        }
        
        // Clear any pending value attribute
        this.removeAttribute('value');
        
        // Debounce the search request
        clearTimeout(this._timeout);
        this._timeout = setTimeout(() => {
            this.fetchResults();
        }, 300);
    }

    _onKeyDown(e) {
        if (e.key === 'Escape' && this.open) {
            e.preventDefault();
            this.close();
        } else if (e.altKey && e.key === 'ArrowUp' && this.open) {
            e.preventDefault();
            this.close();
        } else if (e.altKey && e.key === 'ArrowDown' && !this.open) {
            if (!this._inputElement.value.trim()) return;
            e.preventDefault();
            this.open();
        } else if (e.key === 'Enter' && this.open) {
            // Handle Enter key to select the first option
            const firstOption = this._resultsElement?.querySelector('[role="option"]');
            if (firstOption) {
                e.preventDefault();
                const value = firstOption.getAttribute('data-autocomplete-value') || firstOption.textContent;
                if (value && this._inputElement) {
                    this._inputElement.value = value;
                    this.close();
                }
            }
        }
    }

    _onFocus() {
        if (this._interactingWithList) return;
        this.fetchResults();
    }

    _onBlur() {
        // Small delay to allow click events on results to complete
        setTimeout(() => {
            if (!this._interactingWithList) {
                this.close();
            }
        }, 200);
    }

    _handleClear(e) {
        e.preventDefault();
        
        if (this.open) {
            this.close();
            if (this._feedbackElement) {
                this._feedbackElement.textContent = 'Results hidden.';
            }
        }

        if (this._inputElement) {
            this._inputElement.value = '';
            this._inputElement.focus();
            this._inputElement.dispatchEvent(new Event('change'));
        }
    }

    async fetchResults() {
        const query = this._inputElement ? this._inputElement.value.trim() : '';
        
        // Close if empty and fetchOnEmpty is not enabled
        if (!query && !this.fetchOnEmpty) {
            this.close();
            return;
        }

        const src = this.src;
        if (!src || !query) return;

        // Abort any pending request
        if (this._requestController) {
            this._requestController.abort();
        }
        
        const controller = new AbortController();
        this._requestController = controller;
        
        try {
            // Dispatch loadstart event
            this.dispatchEvent(new CustomEvent('loadstart'));
            
            // Fetch results from our API endpoint
            const response = await fetch(`${src}?q=${encodeURIComponent(query)}`, {
                signal: controller.signal,
                headers: {
                    'Accept': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error('Search failed');
            }
            
            const data = await response.json();
            
            // Convert JSON results to HTML list items
            let html = '';
            
            if (data.repositories && data.repositories.length > 0) {
                data.repositories.forEach((repo, index) => {
                    const fullName = repo.full_name || `${repo.owner}/${repo.name}`;
                    html += `
                        <li role="option" id="${this._resultsElement?.id}-option-${index}" 
                            data-autocomplete-value="https://github.com/${fullName}">
                            <span class="autocomplete-repo-icon">🐙</span>
                            <div class="autocomplete-repo-info">
                                <div class="autocomplete-repo-name">${repo.name || 'Unknown'}</div>
                                <div class="autocomplete-repo-fullname">${fullName}</div>
                                ${repo.description ? `<div class="autocomplete-repo-description">${repo.description}</div>` : ''}
                                <div class="autocomplete-repo-stats">
                                    <span class="autocomplete-repo-stat">⭐ ${repo.stargazers_count || 0}</span>
                                    <span class="autocomplete-repo-stat">🍴 ${repo.forks_count || 0}</span>
                                </div>
                            </div>
                        </li>`;
                });
            } else {
                // No results found
                html += `
                    <li role="presentation" aria-hidden="true" data-no-result-found="true">
                        🔍 No repositories found
                    </li>`;
            }
            
            if (this._resultsElement) {
                this._resultsElement.innerHTML = html;
                
                // Update screen reader feedback
                const numOptions = data.repositories ? data.repositories.length : 0;
                if (this._feedbackElement) {
                    this._feedbackElement.textContent = `${numOptions || 'No'} results.`;
                }
                
                // Show/hide based on results
                if (html.trim() && numOptions > 0) {
                    this.open();
                } else {
                    this.close();
                }
            }
            
            // Dispatch load event
            this.dispatchEvent(new CustomEvent('load'));
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Autocomplete error:', error);
                this.dispatchEvent(new CustomEvent('error'));
            }
        } finally {
            this.dispatchEvent(new CustomEvent('loadend'));
        }
    }

    open() {
        if (this._resultsElement) {
            this._resultsElement.hidden = false;
        }
        this.open = true;
        this._interactingWithList = true;
    }

    close() {
        if (this._resultsElement) {
            this._resultsElement.hidden = true;
        }
        this.open = false;
        this._interactingWithList = false;
    }
}

// Define the custom element
customElements.define('auto-complete', AutoCompleteElement);

export default AutoCompleteElement;