# promptctl Docker Guide

This guide covers running promptctl in Docker with **Ollama integration** for the complete DSPy automation pipeline.

## Quick Start (Recommended)

The simplest way to run promptctl with full functionality:

```bash
# Start everything (Ollama + promptctl daemon)
docker-compose up -d

# That's it! The browser extension now works at http://localhost:9090
```

**What starts automatically:**
- Ollama LLM server (port 11434)
- promptctl daemon with socket API (port 9090)
- Model auto-download (phi3.5)
- Git repository initialization

### Verify It's Running

```bash
# Check status
curl http://localhost:9090/health

# View logs
docker-compose logs -f

# Stop everything
docker-compose down
```

## Browser Extension Setup

1. Start the container: `docker-compose up -d`
2. Load the extension in Chrome (Developer mode → Load unpacked → `extension/`)
3. The extension auto-connects to `http://localhost:9090`
4. Capture prompts, optimize with DSPy - everything works!

## Manual Build (Optional)

```bash
# Build the image
docker build -t promptctl:latest .

# Run a single command
docker run --rm promptctl:latest list

# Interactive shell
docker run -it --rm promptctl:latest bash
```

## Persistent Storage

By default, prompts are stored inside the container and lost when it's removed. Use a volume for persistence:

```bash
# Create a named volume
docker volume create promptctl-data

# Use the volume
docker run --rm -v promptctl-data:/home/promptctl/.promptctl promptctl:latest save --name test -m "Test prompt"

# List prompts (data persists)
docker run --rm -v promptctl-data:/home/promptctl/.promptctl promptctl:latest list
```

## Architecture

The Docker setup uses **supervisor** to manage multiple services:

```
┌─────────────────────────────────────────────┐
│              Docker Container               │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │           supervisord               │   │
│  │                                     │   │
│  │  ┌─────────────┐  ┌──────────────┐ │   │
│  │  │   Ollama    │  │  promptctl   │ │   │
│  │  │   Server    │  │   Daemon     │ │   │
│  │  │ :11434      │  │   :9090      │ │   │
│  │  └─────────────┘  └──────────────┘ │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  Volumes:                                   │
│  - /home/promptctl/.promptctl (prompts)    │
│  - /root/.ollama (models)                  │
└─────────────────────────────────────────────┘
```

## Docker Compose Services

### Main Service (auto-start)

```bash
# Start with auto mode (default)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### CLI Commands

```bash
# Run CLI commands against the running container
docker exec promptctl python /app/promptctl.py list
docker exec promptctl python /app/promptctl.py show my-prompt

# Or use the CLI profile
docker-compose run --rm promptctl-cli list
```

## Advanced Usage

### Interactive Shell

```bash
# Start interactive container
docker run -it --rm -v promptctl-data:/home/promptctl/.promptctl promptctl:latest /bin/bash

# Inside container, run commands directly
promptctl@container:/app$ python promptctl.py list
promptctl@container:/app$ python promptctl.py save --name test -m "Test"
```

### Bind Mount Local Directory

Instead of a volume, use a local directory:

```bash
# Create directory
mkdir -p ~/.promptctl-docker

# Run with bind mount
docker run --rm -v ~/.promptctl-docker:/home/promptctl/.promptctl promptctl:latest list

# Your prompts are now in ~/.promptctl-docker
ls -la ~/.promptctl-docker/prompts/
```

### Environment Variables

```bash
# Custom repository path
docker run --rm -e PROMPTCTL_REPO=/data promptctl:latest list

# With docker-compose
PROMPTCTL_REPO=/data docker-compose run --rm promptctl list
```

### Socket API Endpoints

Once running, the daemon exposes these endpoints on port 9090:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/prompts` | GET | List all prompts |
| `/prompts/<id>` | GET | Get specific prompt |
| `/jobs` | GET | List background jobs |
| `/jobs/<id>` | GET | Get job status |
| `/save` | POST | Save prompt (with optional auto-optimize) |
| `/optimize` | POST | Start DSPy optimization |
| `/evaluate` | POST | Run evaluation |
| `/chain` | POST | Create prompt chain |
| `/agent` | POST | Start agent run |

### Testing the API

```bash
# Health check
curl http://localhost:9090/health

# List prompts
curl http://localhost:9090/prompts

# Save a prompt
curl -X POST http://localhost:9090/save \
  -H "Content-Type: application/json" \
  -d '{"content": "You are a helpful assistant", "name": "my-prompt", "tags": ["ai"]}'

# Optimize a prompt
curl -X POST http://localhost:9090/optimize \
  -H "Content-Type: application/json" \
  -d '{"prompt_id": "my-prompt", "rounds": 3}'

# Check job status
curl http://localhost:9090/jobs/<job_id>
```

## Development

### Build and Test

```bash
# Build image
docker build -t promptctl:dev .

# Run tests
docker run --rm promptctl:dev python -m pytest tests/ -v

# Run example scripts
docker run --rm promptctl:dev /bin/bash examples/basic_usage.sh
```

### Multi-stage Build Benefits

The Dockerfile uses multi-stage builds for optimization:

- **Stage 1 (builder)**: Installs dependencies, ~500MB
- **Stage 2 (runtime)**: Only runtime files, ~200MB

This keeps the final image small and secure.

## Image Details

### Base Image
- `ollama/ollama:latest` - Official Ollama image with LLM runtime

### Size
- Uncompressed: ~2.5GB (includes Ollama)
- Compressed: ~1GB
- Additional ~2GB for phi3.5 model (auto-downloaded)

### Includes
- Ollama LLM server
- Python 3.11
- Git CLI
- GitPython, requests, dspy-ai
- All promptctl core modules
- Supervisor for process management

### Security
- Non-root user (`promptctl`, UID 1000)
- Minimal attack surface (slim base)
- No unnecessary packages

## Troubleshooting

### Permission Errors

If you get permission errors with volumes:

```bash
# Check volume permissions
docker run --rm -v promptctl-data:/data alpine ls -la /data

# Fix ownership (if needed)
docker run --rm -v promptctl-data:/data alpine chown -R 1000:1000 /data
```

### Git Configuration

Git is pre-configured in the image with:
- User: `promptctl`
- Email: `promptctl@localhost`

To use your own identity:

```bash
docker run --rm \
  -e GIT_AUTHOR_NAME="Your Name" \
  -e GIT_AUTHOR_EMAIL="you@example.com" \
  -v promptctl-data:/home/promptctl/.promptctl \
  promptctl:latest save --name test -m "Test"
```

### Volume Not Found

If you get "volume not found" errors:

```bash
# List volumes
docker volume ls

# Create volume explicitly
docker volume create promptctl-data

# Or let Docker create it automatically
docker run --rm -v promptctl-data:/home/promptctl/.promptctl promptctl:latest list
```

## Cleanup

### Remove Containers

```bash
# Remove all stopped containers
docker container prune

# Remove specific container
docker rm promptctl-daemon
```

### Remove Images

```bash
# Remove promptctl image
docker rmi promptctl:latest

# Remove all unused images
docker image prune -a
```

### Remove Volumes

**WARNING**: This deletes all your prompts!

```bash
# Remove specific volume
docker volume rm promptctl-data

# Remove all unused volumes
docker volume prune
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build Docker Image

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build image
        run: docker build -t promptctl:${{ github.sha }} .
      
      - name: Test
        run: |
          docker run --rm promptctl:${{ github.sha }} list
          docker run --rm promptctl:${{ github.sha }} status
      
      - name: Push to registry
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker tag promptctl:${{ github.sha }} yourusername/promptctl:latest
          docker push yourusername/promptctl:latest
```

## Docker Hub Deployment

To share your image:

```bash
# Tag for Docker Hub
docker tag promptctl:latest yourusername/promptctl:latest

# Login
docker login

# Push
docker push yourusername/promptctl:latest

# Others can pull and use
docker pull yourusername/promptctl:latest
docker run --rm yourusername/promptctl:latest list
```

## Kubernetes Deployment

Example StatefulSet for daemon:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: promptctl-daemon
spec:
  serviceName: promptctl
  replicas: 1
  selector:
    matchLabels:
      app: promptctl
  template:
    metadata:
      labels:
        app: promptctl
    spec:
      containers:
      - name: promptctl
        image: promptctl:latest
        command: ["daemon", "--interval", "60", "--socket", "--socket-port", "9090"]
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: data
          mountPath: /home/promptctl/.promptctl
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 1Gi
```

## Best Practices

1. **Always use volumes** for data persistence
2. **Use docker-compose** for easier management
3. **Pin versions** in production (`promptctl:1.0.0` not `:latest`)
4. **Backup volumes** regularly
5. **Use named volumes** instead of bind mounts in production
6. **Monitor daemon logs** when running in background
7. **Limit resources** in production (CPU, memory limits)

## Comparison: Docker vs Native

| Aspect | Docker | Native Python |
|--------|--------|---------------|
| Installation | Just Docker | Python + deps |
| Portability | Runs anywhere | Platform-specific |
| Updates | Pull new image | pip install -U |
| Isolation | Full isolation | System deps |
| Performance | ~5% overhead | Native speed |
| Debugging | More complex | Easier |

**Recommendation**: 
- **Docker** for production, CI/CD, distribution
- **Native** for development, debugging

---

For more details, see [README.md](README.md) and [QUICKSTART.md](QUICKSTART.md).
