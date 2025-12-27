// Connect to Socket.IO server
document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    
    // DOM elements
    const problemStatementInput = document.getElementById('problemStatement');
    const startRunButton = document.getElementById('startRun');
    const activeRunsContainer = document.getElementById('activeRuns');
    const chatMessagesContainer = document.getElementById('chatMessages');
    const runDetailsContainer = document.getElementById('runDetails');
    const runStatusElement = document.getElementById('runStatus');
    const exitStatusElement = document.getElementById('exitStatus');
    const stepCountElement = document.getElementById('stepCount');
    
    let currentRunId = null;
    
    // Add message to chat
    function addChatMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message message-${role}`;
        messageDiv.innerHTML = `<strong>${role}:</strong> ${content}`;
        chatMessagesContainer.appendChild(messageDiv);
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }
    
    // Create run card
    function createRunCard(run) {
        const card = document.createElement('div');
        card.className = 'run-card';
        card.dataset.runId = run.run_id;
        
        let statusClass = 'status-started';
        if (run.completed) {
            statusClass = run.error ? 'status-error' : 'status-completed';
        }
        
        card.innerHTML = `
            <div class="run-header">
                <span class="run-id">Run ${run.run_id}</span>
                <span class="run-status ${statusClass}">
                    ${run.completed ? (run.error ? 'Error' : 'Completed') : 'Running'}
                </span>
            </div>
            <div>Steps: ${run.steps || 0}</div>
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
            
            // Clear previous messages
            chatMessagesContainer.innerHTML = '';
            runDetailsContainer.classList.remove('hidden');
            
            // Add problem statement
            addChatMessage('user', data.problem_statement);
            
            // Add trajectory steps with better formatting
            if (data.trajectory && data.trajectory.length > 0) {
                data.trajectory.forEach((step, index) => {
                    const stepNum = index + 1;
                    
                    if (step.thought) {
                        addChatMessage('assistant', `Step ${stepNum} - Thought: ${step.thought}`);
                    }
                    
                    if (step.action) {
                        addChatMessage('system', `Step ${stepNum} - Action: ${step.action}`);
                    }
                    
                    if (step.observation) {
                        addChatMessage('assistant', `Step ${stepNum} - Observation: ${step.observation}`);
                    }
                    
                    if (step.response) {
                        addChatMessage('system', `Step ${stepNum} - Response: ${step.response}`);
                    }
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
            const statsHtml = Object.entries(data.model_stats)
                .map(([key, value]) => `
                    <span class="info-item">${key}: ${typeof value === 'number' ? value.toFixed(2) : value}</span>
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
            const requestBody = { problem_statement: problemStatement };
            if (Object.keys(config).length > 0) {
                requestBody.config = config;
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
                let message = `Step ${data.step_count}: ${step.action}`;
                
                if (step.thought) {
                    addChatMessage('assistant', `Thought: ${step.thought}`);
                }
                
                if (step.action) {
                    addChatMessage('system', message);
                }
                
                if (step.observation) {
                    addChatMessage('assistant', `Observation: ${step.observation}`);
                }
                
                if (data.model_stats && Object.keys(data.model_stats).length > 0) {
                    const statsText = Object.entries(data.model_stats)
                        .map(([key, value]) => `${key}: ${typeof value === 'number' ? value.toFixed(2) : value}`)
                        .join(' | ');
                    addChatMessage('system', `Model stats: ${statsText}`);
                }
            } else if (data.status === 'completed') {
                addChatMessage('system', `Run completed! Exit status: ${data.exit_status || 'success'}. Total steps: ${data.step_count}`);
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
});
