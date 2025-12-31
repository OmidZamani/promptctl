# promptctl Docker Quick Start

## Build the Image

```bash
docker build -t promptctl:latest .
```

## Basic Usage

```bash
# Create a persistent volume
docker volume create promptctl-data

# Save a prompt
echo "You are a helpful assistant" | docker run --rm -i \
  -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest save --name my-prompt --tags ai

# List prompts
docker run --rm -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest list

# Show a prompt
docker run --rm -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest show my-prompt

# Add tags
docker run --rm -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest tag add --prompt-id my-prompt --tags production

# Filter by tags
docker run --rm -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest tag filter --tags ai production --match-all
```

## Using Docker Compose (Easier!)

```bash
# Run any command
docker-compose run --rm promptctl list

# Save a prompt
echo "Hello" | docker-compose run --rm -T promptctl save --name hello --tags test

# Start daemon in background
docker-compose --profile daemon up -d

# View daemon logs
docker-compose logs -f promptctl-daemon

# Stop daemon
docker-compose --profile daemon down
```

## Key Points

- **Volume Required**: Always use `-v promptctl-data:/home/promptctl/.promptctl` for persistence
- **Stdin Mode**: Use `-i` flag when piping input to `save` command
- **Automatic Init**: Repository auto-initializes on first run
- **Git Integration**: All operations create git commits automatically
- **Port 9090**: Exposed for daemon socket server (optional)

## Complete Documentation

- **Full Guide**: See [DOCKER.md](DOCKER.md)
- **Test Results**: See [DOCKER_TEST_RESULTS.md](DOCKER_TEST_RESULTS.md)
- **Main README**: See [README.md](README.md)
