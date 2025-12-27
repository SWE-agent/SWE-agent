// Connect to Socket.IO server
document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    
    // DOM elements
    const problemStatementInput = document.getElementById('problemStatement');
    const startRunButton = document.getElementById('startRun');
    const activeRunsContainer = document.getElementById('activeRuns');
    const chatMessagesContainer = document.getElementById('chatMessages');
    const timelineViewContainer = document.getElementById('timelineView');
    const runDetailsContainer = document.getElementById('runDetails');
    const runStatusElement = document.getElementById('runStatus');
    const exitStatusElement = document.getElementById('exitStatus');
    const stepCountElement = document.getElementById('stepCount');
    
    // Problem statement type radio buttons
    const textProblemTypeRadio = document.getElementById('textProblemType');
    const githubProblemTypeRadio = document.getElementById('githubProblemType');
    const inputHint = document.getElementById('inputHint');
    const githubHint = document.getElementById('githubHint');
    
    // Cost display elements
    const costDisplayContainer = document.getElementById('costDisplay');
    const costStatsContainer = document.getElementById('costStats');
    
    // Repository configuration elements
    const repoTypeSelect = document.getElementById('repoType');
    const repoPathGroup = document.getElementById('repoPathGroup');
    const githubRepoGroup = document.getElementById('githubRepoGroup');
    const repoPathInput = document.getElementById('repoPath');
    const githubRepoUrlInput = document.getElementById('githubRepoUrl');
    
    // Config file upload elements
    const configFileInput = document.getElementById('configFile');
    const fileNameDisplay = document.getElementById('fileName');
    
    // Model selection element
    const modelSelect = document.getElementById('modelName');
    
    let currentRunId = null;
    
    // Handle repository type selection
    repoTypeSelect.addEventListener('change', function() {
        const repoType = this.value;
        if (repoType === 'local') {
            repoPathGroup.style.display = 'block';
            githubRepoGroup.style.display = 'none';
        } else if (repoType === 'github') {
            repoPathGroup.style.display = 'none';
            githubRepoGroup.style.display = 'block';
        } else {
            repoPathGroup.style.display = 'none';
            githubRepoGroup.style.display = 'none';
        }
    });
    
    // Handle problem statement type selection
    textProblemTypeRadio.addEventListener('change', function() {
        if (this.checked) {
            inputHint.classList.remove('hidden');
            githubHint.classList.add('hidden');
            problemStatementInput.placeholder = "Enter your problem statement here...";
        }
    });
    
    githubProblemTypeRadio.addEventListener('change', function() {
        if (this.checked) {
            inputHint.classList.add('hidden');
            githubHint.classList.remove('hidden');
            problemStatementInput.placeholder = "Enter GitHub issue URL: https://github.com/owner/repo/issues/123";
        }
    });
    
    // Handle config file upload
    configFileInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            fileNameDisplay.textContent = file.name;
            
            // Validate file type
            if (!file.name.endsWith('.yaml') && !file.name.endsWith('.yml')) {
                alert('Please upload a YAML file (.yaml or .yml)');
                configFileInput.value = ''; // Clear the input
                fileNameDisplay.textContent = 'No file chosen';
            }
        } else {
            fileNameDisplay.textContent = 'No file chosen';
        }
    });
    
    // Add step to timeline view
    function addStepToTimeline(stepNum, stepData) {
        const stepCard = document.createElement('div');
        stepCard.className = 'step-card';
        
        let thoughtContent = '';
        let actionContent = '';
        let observationContent = '';
        let responseContent = '';
        
        if (stepData.thought) {
            thoughtContent = formatComponent('Thought', stepData.thought, 'thought');
        }
        
        if (stepData.action) {
            // Check if action is a bash command
            const bashRegex = /^bash: (.+)$/i;
            if (bashRegex.test(stepData.action)) {
                const bashCommand = stepData.action.replace(bashRegex, '$1');
                actionContent = formatComponent('Action', `<pre>${escapeHtml(bashCommand)}</pre>`, 'action');
            } else {
                actionContent = formatComponent('Action', escapeHtml(stepData.action), 'action');
            }
        }
        
        if (stepData.observation) {
            observationContent = formatComponent('Observation', escapeHtml(stepData.observation), 'observation');
        }
        
        if (stepData.response && stepData.response.trim() !== '') {
            // Check if response looks like code
            const lines = stepData.response.split('\n');
            if (lines.length > 1 || stepData.response.includes('\t') || stepData.response.match(/^[a-zA-Z0-9_]+:/)) {
                responseContent = formatComponent('Response', `<pre>${escapeHtml(stepData.response)}</pre>`, 'response');
            } else {
                responseContent = formatComponent('Response', escapeHtml(stepData.response), 'response');
            }
        }
        
        stepCard.innerHTML = `
            <div class="step-header">
                <span class="step-number">Step ${stepNum}</span>
                <span class="step-icon">▼</span>
            </div>
            <div class="step-content">
                <div class="step-details">
                    ${thoughtContent}
                    ${actionContent}
                    ${observationContent}
                    ${responseContent}
                </div>
            </div>`;
        
        // Add click handler for accordion
        stepCard.addEventListener('click', function(e) {
            // Don't toggle if clicking on a copy button or link
            if (e.target.tagName === 'BUTTON' || e.target.tagName === 'A') {
                return;
            }
            
            stepCard.classList.toggle('active');
        });
        
        timelineViewContainer.appendChild(stepCard);
    }
    
    // Format a component (thought, action, observation, response) with proper styling
    function formatComponent(label, content, type) {
        const className = `${type}-section component-section`;
        return `<div class="${className}"><span class="component-label">${label}</span><div class="component-content">${content}</div></div>`;
    }
    
    // Update cost display with model stats
    function updateCostDisplay(stats) {
        let html = '';
        
        // Format stat key for display
        const formatStatKey = (key) => {
            const mappings = {
                'total_tokens': 'Total Tokens',
                'input_tokens': 'Input Tokens',
                'output_tokens': 'Output Tokens',
                'cost_usd': 'Cost ($)',
                'execution_time': 'Time (s)'
            };
            return mappings[key] || key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
        };
        
        // Display all stats except cost
        Object.entries(stats).forEach(([key, value]) => {
            if (key !== 'cost_usd') {
                const formattedValue = typeof value === 'number' ? value.toFixed(2) : value;
                html += `<div class="cost-stat"><span class="cost-label">${formatStatKey(key)}:</span><span class="cost-value">${formattedValue}</span></div>`;
            }
        });
        
        // Display cost separately with emphasis
        if (stats.cost_usd !== undefined) {
            const costValue = typeof stats.cost_usd === 'number' ? stats.cost_usd.toFixed(2) : stats.cost_usd;
            html += `<div class="cost-stat cost-total"><span class="cost-label">Total Cost:</span><span class="cost-value">$${costValue}</span></div>`;
        }
        
        costStatsContainer.innerHTML = html;
    }
    
    // Add message to chat
    function addChatMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message message-${role}`;
        
        // Check if content contains code (bash commands or file content)
        let formattedContent = content;
        
        // Detect bash commands
        const bashRegex = /^bash: (.+)$/i;
        const bashMatch = content.match(bashRegex);
        
        if (bashMatch) {
            // Format as code block with copy button
            formattedContent = `
                <div class="message-content">
                    <div class="code-header">
                        <span class="code-language">Bash</span>
                        <button class="copy-button" onclick="copyToClipboard('${encodeHTML(bashMatch[1])}')">Copy</button>
                    </div>
                    <pre class="code-block"><code>${escapeHtml(bashMatch[1])}</code></pre>
                </div>`;
        } else if (content.includes('\n')) {
            // Multi-line content - format as preformatted
            formattedContent = `
                <div class="message-content">
                    <pre>${escapeHtml(content)}</pre>
                </div>`;
        }
        
        messageDiv.innerHTML = `<strong>${role}:</strong> ${formattedContent}`;
        chatMessagesContainer.appendChild(messageDiv);
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }
    
    // Add collapsible code block
    function addCodeBlock(role, language, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message message-${role}`;
        
        messageDiv.innerHTML = `
            <strong>${role}:</strong>
            <div class="message-content">
                <details class="code-details">
                    <summary class="code-summary">
                        <span class="code-language">${language}</span>
                        <button class="copy-button" onclick="copyToClipboard('${encodeHTML(content)}')">Copy</button>
                    </summary>
                    <pre class="code-block"><code>${escapeHtml(content)}</code></pre>
                </details>
            </div>`;
        
        chatMessagesContainer.appendChild(messageDiv);
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }
    
    // Add model stats display
    function addModelStats(stats) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message message-system model-stats';
        
        let statsHtml = '<strong>Model Stats:</strong> ';
        statsHtml += Object.entries(stats)
            .map(([key, value]) => {
                const formattedValue = typeof value === 'number' ? value.toFixed(2) : value;
                return `<span class="stat-item">${formatStatKey(key)}: ${formattedValue}</span>`;
            })
            .join(' | ');
        
        messageDiv.innerHTML = statsHtml;
        chatMessagesContainer.appendChild(messageDiv);
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }
    
    // Format stat key for display
    function formatStatKey(key) {
        const mappings = {
            'total_tokens': 'Total Tokens',
            'input_tokens': 'Input Tokens',
            'output_tokens': 'Output Tokens',
            'cost_usd': 'Cost ($)',
            'execution_time': 'Time (s)'
        };
        return mappings[key] || key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    }
    
    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Encode HTML for use in onclick handlers
    function encodeHTML(str) {
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    
    // Copy to clipboard utility
    window.copyToClipboard = function(text) {
        navigator.clipboard.writeText(text).then(function() {
            alert('Copied to clipboard!');
        });
    }
    
    // Fetch available models from API and populate dropdown
    async function fetchModels() {
        try {
            const response = await fetch('/api/models');
            if (!response.ok) throw new Error('Failed to load models');
            
            const data = await response.json();
            
            if (data.model_names && data.model_names.length > 0) {
                // Clear existing options except the default one
                while (modelSelect.options.length > 1) {
                    modelSelect.remove(1);
                }
                
                // Add model options
                data.model_names.forEach(modelName => {
                    const option = document.createElement('option');
                    option.value = modelName;
                    option.textContent = modelName;
                    modelSelect.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error loading models:', error);
            // Show a message to the user or keep the dropdown empty
        }
    }
    
    // Create run card with enhanced information
    function createRunCard(run) {
        const card = document.createElement('div');
        card.className = 'run-card';
        card.dataset.runId = run.run_id;
        
        let statusClass = 'status-started';
        if (run.completed) {
            statusClass = run.error ? 'status-error' : 'status-completed';
        }
        
        // Build problem statement display
        const problemStatement = run.problem_statement ? 
            `<div class="run-problem">${escapeHtml(run.problem_statement)}</div>` : '';
        
        // Build current action display
        let currentActionDisplay = '';
        if (run.current_action) {
            const actionText = run.current_action.length > 100 ? 
                escapeHtml(run.current_action.substring(0, 100)) + '...' : 
                escapeHtml(run.current_action);
            currentActionDisplay = `
                <div class="run-action">
                    <strong>Current Action:</strong> ${actionText}
                </div>`;
        }
        
        // Build model stats display
        let modelStatsDisplay = '';
        if (run.model_stats && Object.keys(run.model_stats).length > 0) {
            const cost = run.model_stats.cost_usd || 0;
            const tokens = run.model_stats.total_tokens || 0;
            modelStatsDisplay = `
                <div class="run-stats">
                    <strong>Cost:</strong> $${typeof cost === 'number' ? cost.toFixed(2) : cost} | 
                    <strong>Tokens:</strong> ${typeof tokens === 'number' ? tokens.toFixed(0) : tokens}
                </div>`;
        }
        
        card.innerHTML = `
            <div class="run-header">
                <span class="run-id">Run ${run.run_id}</span>
                <span class="run-status ${statusClass}">
                    ${run.completed ? (run.error ? 'Error' : 'Completed') : 'Running'}
                </span>
            </div>
            ${problemStatement}
            <div class="run-steps">Steps: ${run.steps || 0}</div>
            ${currentActionDisplay}
            ${modelStatsDisplay}
        `;
        
        card.addEventListener('click', function() {
            loadRunDetails(run.run_id);
        });
        
        return card;
    }
    
    // Load run details
    async function loadRunDetails(runId) {
        currentRunId = runId;
        
        try {
            const response = await fetch(`/api/runs/${runId}/trajectory`);
            if (!response.ok) throw new Error('Failed to load trajectory');
            
            const data = await response.json();
            
            // Clear previous content
            chatMessagesContainer.innerHTML = '';
            timelineViewContainer.innerHTML = '';
            runDetailsContainer.classList.remove('hidden');
            
            // Add problem statement to chat (for context)
            addChatMessage('user', data.problem_statement);
            
            // Use timeline view for trajectory steps
            if (data.trajectory && data.trajectory.length > 0) {
                // Switch to timeline view
                chatMessagesContainer.classList.add('hidden');
                timelineViewContainer.classList.remove('hidden');
                
                data.trajectory.forEach((step, index) => {
                    const stepNum = index + 1;
                    addStepToTimeline(stepNum, step);
                });
            }
            
            // Update run info
            updateRunInfo(data);
            
        } catch (error) {
            console.error('Error loading run details:', error);
            addChatMessage('system', `Error: ${error.message}`);
        }
    }
    
    // Update run info display
    function updateRunInfo(data) {
        if (data.exit_status) {
            exitStatusElement.innerHTML = `<span class="info-item">Exit: ${data.exit_status}</span>`;
        }
        
        stepCountElement.innerHTML = `<span class="info-item">Steps: ${data.trajectory ? data.trajectory.length : 0}</span>`;
        
        if (data.model_stats && Object.keys(data.model_stats).length > 0) {
            // Update cost display sidebar
            updateCostDisplay(data.model_stats);
            costDisplayContainer.classList.remove('hidden');
            
            // Add model stats to the chat as well (for backward compatibility)
            addModelStats(data.model_stats);
            
            // Also update the info bar for quick reference
            const statsHtml = Object.entries(data.model_stats)
                .map(([key, value]) => `
                    <span class="info-item">${formatStatKey(key)}: ${typeof value === 'number' ? value.toFixed(2) : value}</span>
                `)
                .join('');
            
            if (statsHtml) {
                stepCountElement.innerHTML += statsHtml;
            }
        }
    }
    
    // Start a new run
    startRunButton.addEventListener('click', async function() {
        const problemStatement = problemStatementInput.value.trim();
        
        if (!problemStatement) {
            alert('Please enter a problem statement');
            return;
        }
        
        // Build configuration from UI inputs
        const config = {};
        
        // Handle repository configuration
        const repoType = repoTypeSelect.value;
        if (repoType === 'local' && repoPathInput.value) {
            if (!config.env) config.env = {};
            if (!config.env.repo) config.env.repo = {};
            config.env.repo.type = 'local';
            config.env.repo.path = repoPathInput.value;
        } else if (repoType === 'github' && githubRepoUrlInput.value) {
            if (!config.env) config.env = {};
            if (!config.env.repo) config.env.repo = {};
            config.env.repo.type = 'github';
            config.env.repo.github_url = githubRepoUrlInput.value;
        }
        
        // Handle problem statement based on radio button selection
        let finalProblemStatement = problemStatement;
        const problemType = document.querySelector('input[name="problem-statement-type"]:checked').value;
        
        if (problemType === 'github') {
            // It's a GitHub issue URL
            finalProblemStatement = {
                type: 'github',
                github_url: problemStatement
            };
        } else {
            // It's text
            finalProblemStatement = problemStatement;
        }
        
        // Handle agent configuration
        const modelTemperature = document.getElementById('modelTemperature').value;
        const modelName = document.getElementById('modelName').value;
        const costLimit = document.getElementById('costLimit').value;
        const enableBash = document.getElementById('enableBash').value;
        
        if (modelTemperature || modelName || costLimit || enableBash) {
            config.agent = {};
            
            if (modelTemperature || modelName || costLimit) {
                config.agent.model = {};
                
                if (modelTemperature) {
                    config.agent.model.temperature = parseFloat(modelTemperature);
                }
                
                if (modelName) {
                    config.agent.model.name = modelName;
                }
                
                if (costLimit) {
                    config.agent.model.per_instance_cost_limit = parseFloat(costLimit);
                }
            }
            
            if (enableBash !== '') {
                if (!config.agent.tools) config.agent.tools = {};
                config.agent.tools.enable_bash_tool = enableBash === 'true';
            }
        }
        
        try {
            // Handle config file upload if present
            let uploadedConfig = null;
            if (configFileInput.files.length > 0) {
                const file = configFileInput.files[0];
                const reader = new FileReader();
                
                // Read the file asynchronously
                const yamlText = await new Promise((resolve, reject) => {
                    reader.onload = (e) => resolve(e.target.result);
                    reader.onerror = reject;
                    reader.readAsText(file);
                });
                
                // Parse YAML content using js-yaml
                let yamlConfig;
                try {
                    // Load js-yaml dynamically if not available
                    let jsyaml;
                    if (typeof window.jsyaml === 'undefined') {
                        const response = await fetch('/static/js-yaml.min.js');
                        if (!response.ok) {
                            throw new Error('js-yaml library not found. Please ensure it\'s included in the static files.');
                        }
                        const yamlScript = document.createElement('script');
                        yamlScript.src = '/static/js-yaml.min.js';
                        yamlScript.onload = () => {
                            jsyaml = window.jsyaml;
                        };
                        await new Promise((resolve) => { yamlScript.onload = resolve; document.head.appendChild(yamlScript); });
                    }
                    
                    // Use js-yaml to parse the YAML content
                    yamlConfig = jsyaml ? window.jsyaml.load(yamlText) : JSON.parse(yamlText.replace(/\:/g, '"'));
                    uploadedConfig = yamlConfig || {};
                } catch (parseError) {
                    console.error('Error parsing YAML file:', parseError);
                    alert('Error parsing configuration file. Please ensure it is a valid YAML file.');
                    throw parseError;
                }
            }
            
            const requestBody = { problem_statement: finalProblemStatement };
            if (Object.keys(config).length > 0) {
                requestBody.config = config;
            }
            if (uploadedConfig) {
                // If we have both inline config and uploaded config, merge them
                // Uploaded config takes precedence over inline config
                const mergedConfig = JSON.parse(JSON.stringify(uploadedConfig)); // Deep copy
                
                // Merge inline config into uploaded config
                for (const [key, value] of Object.entries(config)) {
                    if (typeof value === 'object' && value !== null) {
                        if (!mergedConfig[key]) {
                            mergedConfig[key] = {};
                        }
                        Object.assign(mergedConfig[key], value);
                    } else {
                        mergedConfig[key] = value;
                    }
                }
                
                requestBody.config = mergedConfig;
            }
            
            const response = await fetch('/api/runs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                addChatMessage('system', `Started new run: ${data.run_id}`);
                currentRunId = data.run_id;
                
                // Refresh runs list
                refreshRunsList();
            } else {
                throw new Error(data.error || 'Failed to start run');
            }
        } catch (error) {
            console.error('Error starting run:', error);
            addChatMessage('system', `Error: ${error.message}`);
        }
    });
    
    // Refresh runs list
    async function refreshRunsList() {
        try {
            const response = await fetch('/api/runs');
            if (!response.ok) throw new Error('Failed to load runs');
            
            const data = await response.json();
            activeRunsContainer.innerHTML = '';
            
            data.runs.forEach(run => {
                activeRunsContainer.appendChild(createRunCard(run));
            });
        } catch (error) {
            console.error('Error refreshing runs list:', error);
        }
    }
    
    // Socket.IO event handlers
    socket.on('connect', function() {
        console.log('Connected to server');
        addChatMessage('system', 'Connected to SWE-agent server');
        refreshRunsList();
    });
    
    socket.on('update', function(data) {
        console.log('Received update:', data);
        
        if (data.run_id === currentRunId) {
            // Handle different types of updates with meaningful messages
            if (data.status === 'running' && data.current_step) {
                // Show the actual action and observation from the step
                const step = data.current_step;
                
                // Group related messages together for real-time updates
                addChatMessage('system', `<strong>Step ${data.step_count}</strong>`);
                
                if (step.thought) {
                    addChatMessage('assistant', `Thought: ${step.thought}`);
                }
                
                if (step.action) {
                    // Check if action contains code that should be collapsible
                    const bashRegex = /^bash: (.+)$/i;
                    if (bashRegex.test(step.action)) {
                        addCodeBlock('system', 'Bash', step.action.replace(bashRegex, '$1'));
                    } else {
                        addChatMessage('system', `Action: ${step.action}`);
                    }
                }
                
                if (step.observation) {
                    addChatMessage('assistant', `Observation: ${step.observation}`);
                }
                
                // Display model stats in a consistent format
                if (data.model_stats && Object.keys(data.model_stats).length > 0) {
                    updateCostDisplay(data.model_stats);
                    costDisplayContainer.classList.remove('hidden');
                    addModelStats(data.model_stats);
                }
            } else if (data.status === 'completed') {
                addChatMessage('system', `Run completed! Exit status: ${data.exit_status || 'success'}. Total steps: ${data.step_count}`);
                
                // Display final model stats
                if (data.model_stats && Object.keys(data.model_stats).length > 0) {
                    updateCostDisplay(data.model_stats);
                    costDisplayContainer.classList.remove('hidden');
                    addModelStats(data.model_stats);
                }
            } else if (data.status === 'running' && data.message) {
                // Handle intermediate messages like step start, action planning, etc.
                addChatMessage('system', data.message);
            } else if (data.status === 'running') {
                // Generic running update
                addChatMessage('system', `Agent is running... Step ${data.step_count || 0}`);
            } else {
                // Fallback for other statuses
                const statusText = data.message || data.status || 'progress';
                addChatMessage('system', `Update: ${statusText}`);
            }
        }
        
        // Refresh runs list on any update
        refreshRunsList();
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        addChatMessage('system', 'Disconnected from SWE-agent server');
    });
    
    // Initial load
    refreshRunsList();
    
    // Load available models for the dropdown
    fetchModels();
});
