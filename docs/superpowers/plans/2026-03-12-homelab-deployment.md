# Sanskrit Analyzer Homelab Deployment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Sanskrit Analyzer (API + Streamlit UI) to homelab K8s cluster at sa.naren.me and sa.hanuma.com

**Architecture:** Single combined container running supervisord to manage both uvicorn (API :8000) and streamlit (UI :8501). ARM64-only build targeting hanuma/srirama nodes.

**Tech Stack:** Python 3.11, supervisord, Traefik ingress, Kustomize, Jenkins CI/CD

---

## File Structure

### Sanskrit Analyzer Repository
| File | Purpose |
|------|---------|
| `docker/Dockerfile.combined` | Multi-stage build for combined API + Streamlit container |
| `docker/supervisord.conf` | Process manager config for running both services |
| `jenkins/Jenkinsfile` | CI/CD pipeline for building and deploying |

### Homelab Repository
| File | Purpose |
|------|---------|
| `base/applications/sanskrit-analyzer/namespace.yaml` | K8s namespace |
| `base/applications/sanskrit-analyzer/deployment.yaml` | Pod spec with ARM64 affinity |
| `base/applications/sanskrit-analyzer/service.yaml` | ClusterIP service exposing ports |
| `base/applications/sanskrit-analyzer/ingress.yaml` | Traefik routes for both domains |
| `base/applications/sanskrit-analyzer/kustomization.yaml` | Kustomize bundle |

---

## Chunk 1: Docker Configuration

### Task 1: Create supervisord.conf

**Files:**
- Create: `docker/supervisord.conf`

- [ ] **Step 1: Create supervisord configuration file**

```ini
[supervisord]
nodaemon=true
user=root
logfile=/dev/null
logfile_maxbytes=0
pidfile=/var/run/supervisord.pid

[program:api]
command=python -m uvicorn sanskrit_analyzer.api.app:create_app --factory --host 0.0.0.0 --port 8000
directory=/app
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
priority=10

[program:streamlit]
command=streamlit run sanskrit_analyzer/ui/app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false
directory=/app
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
environment=SANSKRIT_API_URL="http://localhost:8000"
priority=20
```

- [ ] **Step 2: Commit supervisord.conf**

```bash
git add docker/supervisord.conf
git commit -m "Add supervisord config for combined container"
```

---

### Task 2: Create Dockerfile.combined

**Files:**
- Create: `docker/Dockerfile.combined`

- [ ] **Step 1: Create combined Dockerfile**

```dockerfile
# Sanskrit Analyzer Combined Dockerfile
# Runs both API and Streamlit UI via supervisord

FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (required for vidyut-cheda)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy package files
COPY pyproject.toml README.md ./
COPY sanskrit_analyzer ./sanskrit_analyzer

# Build the package with all extras
RUN pip install --no-cache-dir build && \
    python -m build && \
    pip wheel --no-cache-dir --wheel-dir /app/wheels -r <(echo ".[api,ui]")

# Production stage
FROM python:3.11-slim as production

WORKDIR /app

# Install runtime dependencies and supervisord
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy built wheels and install
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/dist/*.whl /wheels/
RUN pip install --no-cache-dir /wheels/*.whl && \
    rm -rf /wheels

# Copy configuration files
COPY config.yaml.example /app/config.yaml
COPY sanskrit_analyzer/data/*.db /app/data/
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy source for Streamlit (needs access to ui/app.py)
COPY sanskrit_analyzer /app/sanskrit_analyzer

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SANSKRIT_CONFIG_PATH=/app/config.yaml
ENV SANSKRIT_CORPUS_PATH=/app/data/corpus.db
ENV SANSKRIT_API_URL=http://localhost:8000

# Expose ports
EXPOSE 8000 8501

# Health check on API
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run supervisord
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
```

- [ ] **Step 2: Commit Dockerfile.combined**

```bash
git add docker/Dockerfile.combined
git commit -m "Add combined Dockerfile for API + Streamlit"
```

---

### Task 3: Test Docker build locally

**Files:**
- None (testing only)

- [ ] **Step 1: Build the combined image locally**

```bash
docker build -f docker/Dockerfile.combined -t sanskrit-analyzer:test .
```

Expected: Build completes successfully

- [ ] **Step 2: Run container and verify both services start**

```bash
docker run -d --name sa-test -p 8000:8000 -p 8501:8501 sanskrit-analyzer:test
sleep 10
curl http://localhost:8000/health
curl http://localhost:8501
docker logs sa-test
docker stop sa-test && docker rm sa-test
```

Expected: Both services respond, logs show supervisord managing both processes

---

## Chunk 2: Kubernetes Manifests

### Task 4: Create namespace.yaml

**Files:**
- Create: `../deployment/homelab/base/applications/sanskrit-analyzer/namespace.yaml`

- [ ] **Step 1: Create namespace manifest**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: sanskrit-analyzer
  labels:
    app.kubernetes.io/name: sanskrit-analyzer
    app.kubernetes.io/part-of: homelab-applications
```

- [ ] **Step 2: Commit namespace.yaml**

```bash
cd ../deployment/homelab
git add base/applications/sanskrit-analyzer/namespace.yaml
git commit -m "Add sanskrit-analyzer namespace"
```

---

### Task 5: Create deployment.yaml

**Files:**
- Create: `../deployment/homelab/base/applications/sanskrit-analyzer/deployment.yaml`

- [ ] **Step 1: Create deployment manifest**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sanskrit-analyzer
  namespace: sanskrit-analyzer
  labels:
    app: sanskrit-analyzer
    app.kubernetes.io/name: sanskrit-analyzer
    app.kubernetes.io/component: web
spec:
  replicas: 1
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabels:
      app: sanskrit-analyzer
  template:
    metadata:
      labels:
        app: sanskrit-analyzer
        app.kubernetes.io/name: sanskrit-analyzer
    spec:
      dnsPolicy: Default
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
              - key: kubernetes.io/arch
                operator: In
                values:
                - arm64
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: sanskrit-analyzer
        image: 192.168.68.124:30501/sanskrit-analyzer:latest
        imagePullPolicy: Always
        ports:
        - name: api
          containerPort: 8000
          protocol: TCP
        - name: ui
          containerPort: 8501
          protocol: TCP
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: api
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: api
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: false
          runAsNonRoot: true
          runAsUser: 1000
          capabilities:
            drop:
              - ALL
      restartPolicy: Always
```

- [ ] **Step 2: Commit deployment.yaml**

```bash
git add base/applications/sanskrit-analyzer/deployment.yaml
git commit -m "Add sanskrit-analyzer deployment"
```

---

### Task 6: Create service.yaml

**Files:**
- Create: `../deployment/homelab/base/applications/sanskrit-analyzer/service.yaml`

- [ ] **Step 1: Create service manifest**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: sanskrit-analyzer-service
  namespace: sanskrit-analyzer
  labels:
    app: sanskrit-analyzer
    app.kubernetes.io/name: sanskrit-analyzer
spec:
  type: ClusterIP
  ports:
  - name: ui
    port: 80
    targetPort: ui
    protocol: TCP
  - name: api
    port: 8000
    targetPort: api
    protocol: TCP
  selector:
    app: sanskrit-analyzer
```

- [ ] **Step 2: Commit service.yaml**

```bash
git add base/applications/sanskrit-analyzer/service.yaml
git commit -m "Add sanskrit-analyzer service"
```

---

### Task 7: Create ingress.yaml

**Files:**
- Create: `../deployment/homelab/base/applications/sanskrit-analyzer/ingress.yaml`

- [ ] **Step 1: Create ingress manifest for both domains**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: sanskrit-analyzer-hanuma-ingress
  namespace: sanskrit-analyzer
  labels:
    app: sanskrit-analyzer
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  ingressClassName: traefik
  rules:
  - host: sa.hanuma.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: sanskrit-analyzer-service
            port:
              number: 80
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: sanskrit-analyzer-service
            port:
              number: 8000
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: sanskrit-analyzer-naren-cloudflare-ingress
  namespace: sanskrit-analyzer
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
    traefik.ingress.kubernetes.io/router.tls: "false"
spec:
  ingressClassName: traefik
  rules:
  - host: sa.naren.me
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: sanskrit-analyzer-service
            port:
              number: 80
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: sanskrit-analyzer-service
            port:
              number: 8000
```

- [ ] **Step 2: Commit ingress.yaml**

```bash
git add base/applications/sanskrit-analyzer/ingress.yaml
git commit -m "Add sanskrit-analyzer ingress for sa.naren.me and sa.hanuma.com"
```

---

### Task 8: Create kustomization.yaml

**Files:**
- Create: `../deployment/homelab/base/applications/sanskrit-analyzer/kustomization.yaml`

- [ ] **Step 1: Create kustomization manifest**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

metadata:
  name: sanskrit-analyzer-application
  annotations:
    config.kubernetes.io/local-config: "true"

resources:
  - namespace.yaml
  - deployment.yaml
  - service.yaml
  - ingress.yaml

namespace: sanskrit-analyzer

commonLabels:
  app.kubernetes.io/part-of: homelab-applications
  app.kubernetes.io/managed-by: kustomize
  environment: homelab

commonAnnotations:
  homelab.local/managed-by: "homelab-applications"
  homelab.local/description: "Sanskrit Analyzer - Sanskrit text analysis API and UI"

images:
  - name: 192.168.68.124:30501/sanskrit-analyzer
    newTag: "latest"
```

- [ ] **Step 2: Commit kustomization.yaml**

```bash
git add base/applications/sanskrit-analyzer/kustomization.yaml
git commit -m "Add sanskrit-analyzer kustomization"
```

---

### Task 9: Register in parent kustomization

**Files:**
- Modify: `../deployment/homelab/base/applications/kustomization.yaml`

- [ ] **Step 1: Add sanskrit-analyzer to applications kustomization**

Add `- sanskrit-analyzer` to the resources list.

- [ ] **Step 2: Commit the change**

```bash
git add base/applications/kustomization.yaml
git commit -m "Register sanskrit-analyzer in applications"
```

---

## Chunk 3: CI/CD Pipeline

### Task 10: Create Jenkinsfile

**Files:**
- Create: `jenkins/Jenkinsfile`

- [ ] **Step 1: Create Jenkins pipeline**

```groovy
@Library('homelab-shared-library') _

gitopsPipeline(
    appName: 'sanskrit-analyzer',
    registry: '192.168.68.124:30501',
    manifestRelativePath: 'base/applications/sanskrit-analyzer',
    namespace: 'sanskrit-analyzer',
    multiArch: false,  // ARM64 only
    buildContext: '.',
    dockerfilePath: 'docker/Dockerfile.combined'
)
```

- [ ] **Step 2: Commit Jenkinsfile**

```bash
cd /Users/narenmudivarthy/Projects/sanskrit_analyzer
git add jenkins/Jenkinsfile
git commit -m "Add Jenkins pipeline for homelab deployment"
```

---

## Chunk 4: DNS and Final Deployment

### Task 11: Configure Cloudflare Tunnel for sa.naren.me

**Files:**
- None (Cloudflare dashboard configuration)

- [ ] **Step 1: Add public hostname in Cloudflare Zero Trust dashboard**

Navigate to: Zero Trust → Networks → Tunnels → homelab-tunnel → Public Hostname

Add:
- Subdomain: `sa`
- Domain: `naren.me`
- Service: `http://traefik.kube-system.svc.cluster.local:80`
- HTTP Host Header: `sa.naren.me`

---

### Task 12: Configure Pi-hole for sa.hanuma.com

**Files:**
- None (Pi-hole configuration)

- [ ] **Step 1: Add DNS record in Pi-hole**

Add Local DNS Record:
- Domain: `sa.hanuma.com`
- IP: `192.168.68.124` (hanuma control plane)

---

### Task 13: Deploy to cluster

**Files:**
- None (kubectl commands)

- [ ] **Step 1: Build and push image manually (first time)**

SSH to hanuma and build:

```bash
ssh narenuday@192.168.68.124
cd /tmp
git clone https://github.com/naren-m/sanskrit_analyser.git
cd sanskrit_analyser
docker build -f docker/Dockerfile.combined -t 192.168.68.124:30501/sanskrit-analyzer:initial .
docker push 192.168.68.124:30501/sanskrit-analyzer:initial
```

- [ ] **Step 2: Update kustomization with initial tag**

```bash
cd ../deployment/homelab
sed -i '' 's/newTag: "latest"/newTag: "initial"/' base/applications/sanskrit-analyzer/kustomization.yaml
git add base/applications/sanskrit-analyzer/kustomization.yaml
git commit -m "Set initial image tag for sanskrit-analyzer"
git push
```

- [ ] **Step 3: Apply manifests**

```bash
kubectl apply -k base/applications/sanskrit-analyzer/
```

- [ ] **Step 4: Verify deployment**

```bash
kubectl -n sanskrit-analyzer get pods
kubectl -n sanskrit-analyzer get svc
kubectl -n sanskrit-analyzer get ingress
```

Expected: Pod running, services created, ingress routes configured

- [ ] **Step 5: Test endpoints**

```bash
curl http://sa.hanuma.com/
curl http://sa.hanuma.com/api/health
```

Expected: Streamlit UI and API health check respond

---

## Summary

| Task | Description | Repo |
|------|-------------|------|
| 1-3 | Docker configuration (supervisord, Dockerfile, test) | sanskrit_analyzer |
| 4-9 | Kubernetes manifests (namespace, deployment, service, ingress, kustomization) | homelab |
| 10 | Jenkins CI/CD pipeline | sanskrit_analyzer |
| 11-13 | DNS configuration and deployment | Cloudflare/Pi-hole/kubectl |

After completion, Sanskrit Analyzer will be accessible at:
- **https://sa.naren.me** (public via Cloudflare)
- **http://sa.hanuma.com** (internal via Pi-hole)
