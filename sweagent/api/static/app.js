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
            
            // Add trajectory steps
            if (data.trajectory && data.trajectory.length > 0) {
                data.trajectory.forEach(step => {
                    if (step.observation) {
                        addChatMessage('assistant', step.observation);
                    }
                    if (step.action) {
                        addChatMessage('system', `Action: ${step.action}`);
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
        
        try {
            const response = await fetch('/api/runs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    problem_statement: problemStatement
                })
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
            addChatMessage('system', `Update: ${data.status || 'progress'}`);
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
