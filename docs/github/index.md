# GitHub Integration

SWE-agent provides a flexible GitHub integration that can operate as both a GitHub Action and a bot. While GitHub Actions and GitHub Bots are technically distinct integration types, SWE-agent's implementation serves both purposes through a unified codebase with mode-specific optimizations.

## Features

- Dual-mode operation (Action/Bot)
- Cost-optimized processing (target: 10 rupees/hour)
- Event deduplication and batching
- Persistent state management
- Comprehensive event support:
  - Issues
  - Pull Requests
  - Discussions

## Configuration

Configuration is managed through `config/github.yaml`:

```yaml
github:
  # Common settings
  cost_limits:
    target_hourly_rate: 10.0  # Target cost in rupees per hour
    max_hourly_rate: 15.0     # Maximum allowed cost rate
    max_total_cost: 1000.0    # Maximum total cost allowed

  # Mode-specific configurations below...
```

See [github.yaml](../../config/github.yaml) for the complete configuration reference.

## GitHub Action Mode

### Setup

1. Add the action to your workflow:

```yaml
name: SWE Agent
on:
  issues:
    types: [opened, edited]
  pull_request:
    types: [opened, synchronize]
  discussion:
    types: [created, edited]

jobs:
  swe-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: SWE-agent/SWE-agent@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Configuration

Action-specific settings in `github.yaml`:

```yaml
action:
  events:
    issues:
      actions: ["opened", "edited"]
      batch_size: 5
      min_tokens: 100
      max_tokens: 2000
    # Additional event configurations...
```

## Bot Mode

### Setup

1. Create a GitHub App
2. Configure webhook URL and secret
3. Install the app on your repositories
4. Run SWE-agent in bot mode:

```bash
swe-agent github bot \
  --token YOUR_GITHUB_TOKEN \
  --webhook-secret YOUR_WEBHOOK_SECRET
```

### Configuration

Bot-specific settings in `github.yaml`:

```yaml
bot:
  webhook:
    port: 8000
    host: "0.0.0.0"
    timeout: 10
  events:
    # Event configurations...
  rate_limit:
    requests_per_hour: 100
    burst: 10
```

## Cost Optimization

SWE-agent maintains a target cost efficiency of 10 rupees per hour through several strategies:

1. Event batching
2. Token limits per event
3. Concurrent event processing limits
4. Cost tracking and throttling

The state management system tracks costs and can automatically throttle processing when approaching limits.

## State Management

SWE-agent maintains persistent state using SQLite, tracking:

- Processed events
- Model states
- Cost metrics
- Processing statistics

State is automatically cleaned up after 30 days to prevent database growth.

### Cost Tracking

The state system maintains detailed cost metrics:

```sql
-- Example cost query
SELECT SUM(cost) / 24 as daily_rate
FROM cost_tracking
WHERE timestamp >= datetime('now', '-24 hours')
```

## Development

### Testing

Tests are automatically run in CI and cover:

- Action routing
- Bot webhook handling
- State management
- Cost tracking

### Adding New Event Types

1. Update `SUPPORTED_EVENTS` in both routers
2. Add handler method
3. Update configuration schema
4. Add tests

## Troubleshooting

### Common Issues

1. Cost Limits
   - Check hourly cost rate
   - Adjust batch sizes
   - Review token limits

2. Webhook Issues
   - Verify signature configuration
   - Check port availability
   - Review rate limits

3. State Management
   - Check database permissions
   - Monitor disk space
   - Review cleanup settings

## Security

- Webhook signatures required
- Token-based authentication
- Rate limiting
- Input validation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests
4. Submit pull request

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for details.
