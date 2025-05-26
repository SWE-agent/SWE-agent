#!/bin/bash

set -e

# --- Configuration ---
GITHUB_TOKEN="${INPUT_GITHUB_TOKEN}"
TRIGGER_PHRASE="${INPUT_TRIGGER_PHRASE:-@swe-agent}"
LLM_API_KEY="${INPUT_LLM_API_KEY}"
MODEL_NAME="${INPUT_MODEL_NAME:-gpt-4o}"
TIMEOUT_MINUTES="${INPUT_TIMEOUT_MINUTES:-30}"

# GitHub API URL
GITHUB_API_URL="${GITHUB_API_URL:-https://api.github.com}"

# --- Utility Functions ---
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

post_comment() {
    local message="$1"
    local json_payload=$(jq -n --arg body "$message" '{body: $body}')
    
    local response=$(curl -s -X POST \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "${GITHUB_API_URL}/repos/${GITHUB_REPOSITORY}/issues/${ISSUE_NUMBER}/comments" \
        -d "$json_payload")
    
    if [ $? -eq 0 ]; then
        # Extract comment ID for future updates
        echo "$response" | jq -r '.id'
    else
        log "⚠️ Failed to post comment to GitHub"
        echo ""
    fi
}

update_comment() {
    local comment_id="$1"
    local message="$2"
    local json_payload=$(jq -n --arg body "$message" '{body: $body}')
    
    curl -s -X PATCH \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "${GITHUB_API_URL}/repos/${GITHUB_REPOSITORY}/issues/comments/${comment_id}" \
        -d "$json_payload" > /dev/null
    
    if [ $? -ne 0 ]; then
        log "⚠️ Failed to update comment on GitHub"
    fi
}

add_reaction() {
    local reaction="$1"
    
    curl -s -X POST \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "${GITHUB_API_URL}/repos/${GITHUB_REPOSITORY}/issues/comments/${COMMENT_ID}/reactions" \
        -d "{\"content\": \"$reaction\"}" > /dev/null
    
    if [ $? -ne 0 ]; then
        log "⚠️ Failed to add reaction to GitHub comment"
    fi
}

# --- Main Execution ---
log "🚀 SWE-Agent Issue Resolver started"

# Parse GitHub event
EVENT_PATH="${GITHUB_EVENT_PATH}"
if [ ! -f "$EVENT_PATH" ]; then
    log "❌ GitHub event file not found"
    exit 1
fi

# Extract comment details
COMMENT_BODY=$(jq -r '.comment.body' "$EVENT_PATH")
COMMENT_ID=$(jq -r '.comment.id' "$EVENT_PATH")
ISSUE_NUMBER=$(jq -r '.issue.number' "$EVENT_PATH")
ISSUE_TITLE=$(jq -r '.issue.title' "$EVENT_PATH")
ISSUE_BODY=$(jq -r '.issue.body // ""' "$EVENT_PATH")
REPO_URL=$(jq -r '.repository.clone_url' "$EVENT_PATH")

# Validate extracted data
if [ -z "$COMMENT_BODY" ] || [ "$COMMENT_BODY" == "null" ]; then
    log "❌ Could not extract comment body"
    exit 1
fi

if [ -z "$ISSUE_NUMBER" ] || [ "$ISSUE_NUMBER" == "null" ]; then
    log "❌ Could not extract issue number"
    exit 1
fi

# Check if comment contains trigger phrase
if [[ "$COMMENT_BODY" != *"$TRIGGER_PHRASE"* ]]; then
    log "🔍 Comment doesn't contain trigger phrase '$TRIGGER_PHRASE'"
    exit 0
fi

log "✅ Trigger phrase found. Processing issue #$ISSUE_NUMBER"
log "📋 Issue: $ISSUE_TITLE"

# Add eyes reaction to show we're processing
add_reaction "eyes"

# Create initial progress comment
INITIAL_MESSAGE="🤖 **SWE-Agent is working on this issue...**

**Issue:** #${ISSUE_NUMBER} - ${ISSUE_TITLE}
**Model:** ${MODEL_NAME}
**Timeout:** ${TIMEOUT_MINUTES} minutes

## 📊 Progress Status
⏳ **Starting up...** - Initializing SWE-Agent environment

---
*This comment will be updated with real-time progress. Please wait...*"

PROGRESS_COMMENT_ID=$(post_comment "$INITIAL_MESSAGE")

if [ -z "$PROGRESS_COMMENT_ID" ]; then
    log "⚠️ Could not create progress comment, continuing without real-time updates"
fi

# Set up API keys for SWE-Agent
export OPENAI_API_KEY="$LLM_API_KEY"
export ANTHROPIC_API_KEY="$LLM_API_KEY"

# Create temporary directories
TEMP_DIR="/tmp/swe_agent_$(date +%s)"
REPO_DIR="$TEMP_DIR/repo"
OUTPUT_DIR="$TEMP_DIR/output"
mkdir -p "$REPO_DIR" "$OUTPUT_DIR"

# Track start time for progress calculations
echo "$(date +%s)" > "$TEMP_DIR/start_time"

# Clone repository
log "📥 Cloning repository..."
if ! git clone "$REPO_URL" "$REPO_DIR"; then
    log "❌ Failed to clone repository"
    post_comment "❌ Failed to clone repository. Please check permissions."
    add_reaction "confused"
    exit 1
fi

cd "$REPO_DIR"

# Create problem statement file
PROBLEM_STATEMENT_FILE="$OUTPUT_DIR/problem_statement.md"
cat > "$PROBLEM_STATEMENT_FILE" << EOF
# Issue: $ISSUE_TITLE

## Problem Description
$ISSUE_BODY

## User Request
$COMMENT_BODY

## Task
Please analyze and fix this issue in the repository.
EOF

log "🤖 Running SWE-Agent with model: $MODEL_NAME"

# Validate timeout (minimum 5 minutes for SWE-Agent to work effectively)
if [ "$TIMEOUT_MINUTES" -lt 5 ]; then
    log "⚠️ Timeout too short ($TIMEOUT_MINUTES min), setting to 5 minutes minimum"
    TIMEOUT_MINUTES=5
fi

# Execute SWE-Agent with correct 1.0+ command format
timeout "${TIMEOUT_MINUTES}m" sweagent run \
    --agent.model.name "$MODEL_NAME" \
    --agent.model.per_instance_cost_limit 2.0 \
    --env.repo.path "$REPO_DIR" \
    --problem_statement.path "$PROBLEM_STATEMENT_FILE" \
    --output_dir "$OUTPUT_DIR" \
    --config /app/swe-agent/config/default.yaml \
    > "$OUTPUT_DIR/swe_agent.log" 2>&1

SWE_EXIT_CODE=$?

if [ $SWE_EXIT_CODE -eq 0 ]; then
    log "✅ SWE-Agent completed successfully"
    
    # Update progress comment with completion status
    local start_time_file="$TEMP_DIR/start_time"
    local elapsed_minutes=0
    if [ -f "$start_time_file" ]; then
        local start_time=$(cat "$start_time_file")
        elapsed_minutes=$(( ($(date +%s) - start_time) / 60 ))
    fi
    update_progress "✅ **Analysis complete!** Processing results..." "$elapsed_minutes" "$OUTPUT_DIR/swe_agent.log"
    
    # Look for patches in SWE-Agent 1.0 output format
    PATCH_FOUND=false
    PATCH_CONTENT=""
    
    # Check for .patch files
    for patch_file in $(find "$OUTPUT_DIR" -name "*.patch" 2>/dev/null || true); do
        if [ -s "$patch_file" ]; then
            PATCH_CONTENT=$(cat "$patch_file")
            PATCH_FOUND=true
            log "📄 Found patch file: $patch_file"
            break
        fi
    done
    
    # Check for trajectory files with patches
    if [ "$PATCH_FOUND" = false ]; then
        for traj_file in $(find "$OUTPUT_DIR" -name "*.traj" 2>/dev/null || true); do
            if [ -s "$traj_file" ]; then
                # Extract patch from trajectory file if present
                PATCH_CONTENT=$(grep -A 1000 "diff --git" "$traj_file" | head -n 500 || true)
                if [ -n "$PATCH_CONTENT" ] && [[ "$PATCH_CONTENT" == *"diff --git"* ]]; then
                    PATCH_FOUND=true
                    log "📄 Found patch in trajectory file: $traj_file"
                    break
                fi
            fi
        done
    fi
    
    # Check for any diff output in logs
    if [ "$PATCH_FOUND" = false ]; then
        PATCH_CONTENT=$(grep -A 100 "diff --git" "$OUTPUT_DIR/swe_agent.log" 2>/dev/null || true)
        if [ -n "$PATCH_CONTENT" ] && [[ "$PATCH_CONTENT" == *"diff --git"* ]]; then
            PATCH_FOUND=true
            log "📄 Found patch in SWE-Agent logs"
        fi
    fi
    
    # Generate final response and update the progress comment
    if [ "$PATCH_FOUND" = true ] && [ -n "$PATCH_CONTENT" ]; then
        # Truncate patch if too long (GitHub comment limit)
        if [ ${#PATCH_CONTENT} -gt 40000 ]; then
            PATCH_CONTENT="${PATCH_CONTENT:0:40000}
...
(Patch truncated - too long for comment)"
        fi
        
        FINAL_MESSAGE="✅ **Solution Generated Successfully!**

**Issue:** #${ISSUE_NUMBER} - ${ISSUE_TITLE}
**Model:** ${MODEL_NAME}
**Execution Time:** Complete

## 🔧 Generated Patch
\`\`\`diff
$PATCH_CONTENT
\`\`\`

## 📝 Next Steps
1. **Review** the proposed changes carefully
2. **Test** the solution in your development environment  
3. **Apply** the patch if it looks good: \`git apply <patch_file>\`
4. **Verify** the fix resolves the original issue

## 🎯 How to Apply This Patch
\`\`\`bash
# Save the patch to a file
curl -o fix.patch \"data:text/plain,$(echo "$PATCH_CONTENT" | sed 's/"/\\"/g')\"

# Apply the patch
git apply fix.patch

# Or apply directly (copy the diff content to a file)
git apply <<'EOF'
$PATCH_CONTENT
EOF
\`\`\`

---
*✨ Generated by SWE-Agent using $MODEL_NAME*"
        
        # Update the progress comment with final results
        if [ -n "$PROGRESS_COMMENT_ID" ]; then
            update_comment "$PROGRESS_COMMENT_ID" "$FINAL_MESSAGE"
        else
            post_comment "$FINAL_MESSAGE"
        fi
        
        add_reaction "thumbsup"
        
    else
        log "⚠️ No patch found in SWE-Agent output"
        
        FINAL_MESSAGE="✅ **SWE-Agent Analysis Complete**

**Issue:** #${ISSUE_NUMBER} - ${ISSUE_TITLE}
**Model:** ${MODEL_NAME}
**Result:** Analysis completed but no patch generated

## 🔍 Analysis Results
I've analyzed the issue but didn't generate a code patch. This might mean:

- 📋 **Investigation needed** - The issue requires manual investigation
- ℹ️ **More information needed** - Additional details would help provide a solution
- ✅ **Already resolved** - The problem may already be fixed
- 📝 **Documentation issue** - The issue might be related to documentation rather than code
- 🔧 **Complex solution required** - The fix might require architectural changes

## 💡 What You Can Do
1. **Provide more details** about the issue
2. **Add specific examples** of the problem
3. **Include error messages** or logs if available
4. **Specify expected behavior** vs actual behavior
5. **Try rephrasing** the request with more specific requirements

Feel free to comment with additional information and trigger the agent again!

---
*🤖 Analysis by SWE-Agent using $MODEL_NAME*"
        
        # Update the progress comment with final results
        if [ -n "$PROGRESS_COMMENT_ID" ]; then
            update_comment "$PROGRESS_COMMENT_ID" "$FINAL_MESSAGE"
        else
            post_comment "$FINAL_MESSAGE"
        fi
        
        add_reaction "thinking_face"
    fi
    
else
    # SWE-Agent failed - determine the cause and update progress comment
    local start_time_file="$TEMP_DIR/start_time"
    local elapsed_minutes=0
    if [ -f "$start_time_file" ]; then
        local start_time=$(cat "$start_time_file")
        elapsed_minutes=$(( ($(date +%s) - start_time) / 60 ))
    fi
    
    if [ $SWE_EXIT_CODE -eq 124 ]; then
        log "⏰ SWE-Agent timed out after ${TIMEOUT_MINUTES} minutes"
        
        TIMEOUT_MESSAGE="⏰ **SWE-Agent Timeout**

**Issue:** #${ISSUE_NUMBER} - ${ISSUE_TITLE}  
**Model:** ${MODEL_NAME}
**Result:** Timed out after ${TIMEOUT_MINUTES} minutes

## ⏱️ What Happened
The analysis took longer than expected and was stopped to prevent resource exhaustion.

## 🔧 Possible Solutions
- **Simplify the request** - Break down complex issues into smaller, specific parts
- **Provide more details** - Help SWE-Agent focus on the core problem with specific examples
- **Increase timeout** - For complex issues, consider requesting a longer timeout
- **Try different approach** - Rephrase the issue description to be more specific

## 💡 Tips for Better Results
1. **Be specific** - \"Fix login bug on line 45\" vs \"Fix login issues\"
2. **Include context** - Provide error messages, expected vs actual behavior
3. **One issue at a time** - Don't mix multiple problems in one request
4. **Add examples** - Show input/output or steps to reproduce

## 🔄 Ready to Try Again?
Comment \`@swe-agent\` with a more focused request!

---
*⏰ SWE-Agent using $MODEL_NAME (timeout: ${TIMEOUT_MINUTES}m)*"
        
        # Update progress comment with timeout message
        if [ -n "$PROGRESS_COMMENT_ID" ]; then
            update_comment "$PROGRESS_COMMENT_ID" "$TIMEOUT_MESSAGE"
        else
            post_comment "$TIMEOUT_MESSAGE"
        fi
        
        add_reaction "hourglass_flowing_sand"
        
    elif [ $SWE_EXIT_CODE -eq 137 ]; then
        log "💀 SWE-Agent was killed (likely due to hanging or resource limits)"
        
        KILLED_MESSAGE="💀 **SWE-Agent Process Terminated**

**Issue:** #${ISSUE_NUMBER} - ${ISSUE_TITLE}
**Model:** ${MODEL_NAME}  
**Result:** Process was terminated due to hanging or resource limits

## ⚠️ What Happened
The analysis process was terminated because it appeared to be hanging or consuming too many resources.

## 🔍 Common Causes
- **Large repository** - Very large codebases can overwhelm the analysis
- **Complex issue** - Some problems require more resources than available
- **Network issues** - API connectivity problems with the AI model
- **Resource limits** - Memory or CPU exhaustion in the container
- **Infinite loops** - Rare cases where the AI gets stuck in reasoning loops

## 🛠️ What to Try
1. **Simplify the issue** - Focus on one specific problem at a time
2. **Provide clear context** - Include specific file names, line numbers, or error messages
3. **Check repository size** - Very large repos might need special handling
4. **Retry the request** - Sometimes it's just a temporary glitch
5. **Break down the problem** - Split complex issues into smaller parts

## 🔄 Ready to Try Again?
Comment \`@swe-agent\` with a more targeted, specific request!

---
*💀 SWE-Agent using $MODEL_NAME*"
        
        # Update progress comment with killed message
        if [ -n "$PROGRESS_COMMENT_ID" ]; then
            update_comment "$PROGRESS_COMMENT_ID" "$KILLED_MESSAGE"
        else
            post_comment "$KILLED_MESSAGE"
        fi
        
        add_reaction "skull"
        
    else
        log "❌ SWE-Agent execution failed with exit code: $SWE_EXIT_CODE"
        
        # Extract error information
        ERROR_INFO=""
        if [ -f "$OUTPUT_DIR/swe_agent.log" ]; then
            ERROR_INFO=$(tail -20 "$OUTPUT_DIR/swe_agent.log" 2>/dev/null | grep -E "(Error|Exception|Failed)" | head -3 || echo "Check logs for details")
        fi
        
        FAILURE_MESSAGE="❌ **SWE-Agent Execution Failed**

**Issue:** #${ISSUE_NUMBER} - ${ISSUE_TITLE}
**Model:** ${MODEL_NAME}
**Exit Code:** ${SWE_EXIT_CODE}

## 🚨 What Happened
I encountered an error while trying to analyze and fix this issue.

## 🔍 Possible Causes
- **Issue complexity** - The problem might require human intervention
- **API limits** - Rate limiting or model constraints from the AI provider
- **Repository issues** - Access permissions or repository-specific limitations  
- **Service problems** - Temporary issues with SWE-Agent or AI model services
- **Configuration issues** - Problems with model setup or parameters

$(if [ -n "$ERROR_INFO" ] && [ "$ERROR_INFO" != "Check logs for details" ]; then echo "## 📋 Error Details"; echo "\`\`\`"; echo "$ERROR_INFO"; echo "\`\`\`"; fi)

## 🛠️ What You Can Try
1. **Rephrase the request** - Provide more details or context about the issue
2. **Check the issue description** - Ensure it's clear and complete
3. **Try again later** - If this was a temporary API or service issue
4. **Simplify the request** - Focus on one specific aspect of the problem
5. **Use a different model** - Try switching between GPT-4o and Claude models

## 🔄 Ready to Try Again?  
Comment \`@swe-agent\` with additional context or a rephrased request!

---
*❌ SWE-Agent using $MODEL_NAME*"
        
        # Update progress comment with failure message
        if [ -n "$PROGRESS_COMMENT_ID" ]; then
            update_comment "$PROGRESS_COMMENT_ID" "$FAILURE_MESSAGE"
        else
            post_comment "$FAILURE_MESSAGE"
        fi
        
        add_reaction "confused"
    fi
fi

# Cleanup
log "🧹 Cleaning up temporary files..."
rm -rf "$TEMP_DIR"

log "🏁 SWE-Agent Issue Resolver finished"

exit $SWE_EXIT_CODE