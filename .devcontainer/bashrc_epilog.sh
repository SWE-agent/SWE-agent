
if [ -z "$(docker images -q sweagent/swe-agent 2> /dev/null)" ]; then
  echo "⚠️ Please wait for the postCreateCommand to start and finish (a new window will appear shortly) ⚠️"
fi

echo "Here's an example SWE-agent command to try out:"

echo "sweagent run \\
  --agent.model.name=claude-3-7-sonnet-latest \\
  --agent.model.per_instance_cost_limit=2.00 \\
  --env.repo.github_url=https://github.com/SWE-agent/test-repo \\
  --problem_statement.github_url=https://github.com/SWE-agent/test-repo/issues/1 \\
"
