# Sanskrit Analyzer Homelab Deployment Design

**Date:** 2026-03-12
**Status:** Approved
**Domains:** sa.naren.me, sa.hanuma.com

## Overview

Deploy Sanskrit Analyzer to the homelab Kubernetes cluster with both API and Streamlit UI accessible via two domains.

## Architecture

### Single Combined Container

```
┌─────────────────────────────────────────┐
│          sanskrit-analyzer pod          │
│  ┌───────────────────────────────────┐  │
│  │      Combined Container           │  │
│  │  ┌─────────────┐ ┌─────────────┐  │  │
│  │  │  Uvicorn    │ │  Streamlit  │  │  │
│  │  │  API :8000  │ │  UI :8501   │  │  │
│  │  └─────────────┘ └─────────────┘  │  │
│  │         ↑               ↑         │  │
│  │         └───supervisord──┘        │  │
│  └───────────────────────────────────┘  │
│              ports: 8000, 8501          │
└─────────────────────────────────────────┘
```

### Ingress Routing

```
sa.naren.me (Cloudflare) ──┐
                          ├──► Traefik ──► Service :80 ──► Streamlit :8501
sa.hanuma.com (Pi-hole) ──┘

sa.naren.me/api/* ──────────► Traefik ──► Service :8000 ──► API :8000
```

## Decisions

| Component | Decision | Rationale |
|-----------|----------|-----------|
| UI | Streamlit only | Simpler, same stack as API |
| Architecture | Single container | Fewer moving parts, easier debugging |
| Process manager | supervisord | Lightweight, standard approach |
| Node target | ARM64 only | Matches hanuma/srirama nodes |
| Monitoring | Skipped | Can add later if needed |

## Files to Create

### Sanskrit Analyzer Repository

```
sanskrit_analyzer/
├── docker/
│   ├── Dockerfile.combined    # Combined API + Streamlit image
│   └── supervisord.conf       # Process manager config
└── jenkins/
    └── Jenkinsfile            # CI/CD pipeline
```

### Homelab Repository

```
homelab/base/applications/sanskrit-analyzer/
├── namespace.yaml
├── deployment.yaml
├── service.yaml
├── ingress.yaml
└── kustomization.yaml
```

## Docker Configuration

### Dockerfile.combined

- Base: `python:3.11-slim`
- Includes Rust toolchain for vidyut-cheda
- Installs supervisord
- Exposes ports 8000 and 8501
- Runs supervisord as entrypoint

### supervisord.conf

- `nodaemon=true` for container foreground
- Two programs: api and streamlit
- Auto-restart on failure
- Logs to stdout/stderr
- Streamlit connects to API via localhost:8000

## Kubernetes Configuration

### Resources

- Requests: 256Mi RAM, 250m CPU
- Limits: 2Gi RAM, 1000m CPU
- Replicas: 1

### Health Checks

- Liveness: GET /health on port 8000, 30s initial delay
- Readiness: GET /health on port 8000, 10s initial delay

### Node Affinity

- ARM64 architecture only
- Targets hanuma/srirama nodes

## Build & Deploy

### Image Registry

- Registry: `192.168.68.124:30501`
- Image: `sanskrit-analyzer`
- Tag format: `HHMMSS-DDMMYY-<git-hash>`

### Jenkins Pipeline

1. Triggered on push to main
2. Builds ARM64 image on hanuma node
3. Pushes to local registry
4. Updates K8s deployment image tag

## Domain Configuration

| Domain | DNS | TLS |
|--------|-----|-----|
| sa.naren.me | Cloudflare Tunnel | Cloudflare-managed |
| sa.hanuma.com | Pi-hole (internal) | None (HTTP only) |
