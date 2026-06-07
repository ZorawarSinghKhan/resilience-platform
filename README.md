# Resilience Testing Platform

A web-based chaos engineering platform that accepts any Docker image, deploys it dynamically to Kubernetes, runs automated chaos experiments, and produces a scored resilience report with live Grafana monitoring.

**Developer:** Ashu Chaudhary  
**GitHub:** [ZorawarSinghKhan/resilience-platform](https://github.com/ZorawarSinghKhan/resilience-platform)  
**Docker Hub:** `ashu804/resilience-platform:latest`  
**Live URL:** `c41d694a9a2269ab9eed-290100455.us-east-1.elb.amazonaws.com`  
**Stack:** Flask · Docker · Kubernetes · AWS EKS · Chaos Mesh · Prometheus · Grafana  

---

## What It Does

1. User enters any public Docker image (e.g. `nginx:latest`)
2. Platform deploys it to AWS EKS (2 replicas)
3. Runs 5 automated chaos experiments via Chaos Mesh
4. Collects live CPU and memory metrics during each test
5. Scores recovery performance using a weighted formula and assigns a letter grade (A+ to F)
6. Displays a full breakdown dashboard with per-test results and live Grafana monitoring panels
7. Supports batch testing (multiple images at once) with a comparison table
8. Sends email notifications when tests complete
9. Saves test history per user account
10. Generates a downloadable PDF report

**Total test time:** ~5–8 minutes per image

---

## Architecture

```
Browser → Flask App (port 5001)
            ├── services/deployer.py     → kubectl apply dynamic YAML
            ├── services/chaos_runner.py → Chaos Mesh experiments + CPU/memory metrics
            └── services/scorer.py      → Weighted score calculation engine

Infrastructure (AWS EKS):
EKS Cluster (us-east-1, 2x t3.small nodes)
    ├── Chaos Mesh          (chaos-testing namespace)
    ├── Prometheus          (monitoring namespace)
    └── Grafana             (monitoring namespace, LoadBalancer exposed)
```

---

## Chaos Tests

| # | Test | Type | Condition | Pass Criteria |
|---|------|------|-----------|---------------|
| 1 | Pod Chaos | PodChaos / pod-kill | 1 pod killed | 2+ pods running |
| 2 | CPU Stress | StressChaos | 80% CPU, 60s | 2+ pods running |
| 3 | Memory Stress | StressChaos | 256MB, 60s | 2+ pods running |
| 4 | Network Delay | NetworkChaos | 3000ms latency | 2+ pods running |
| 5 | Packet Loss | NetworkChaos | 30% loss, 60s | 2+ pods running |
| 6 | Recovery Validation | — | Final check | 2+ pods running |

---

## Scoring System (v5.0)

Scores are calculated using real metrics collected during each chaos test — not just pass/fail.

| Component | Weight | Logic |
|-----------|--------|-------|
| Recovery Time | 40% | Banded scoring — faster recovery = higher score |
| Peak CPU Usage | 20% | Lower peak CPU millicores = better score |
| Peak Memory Usage | 20% | Lower peak memory MB = better score |
| Restart Count | 10% | Penalty per container restart |
| Deployment Health | 10% | Derived from recovery time and restarts |

**Category Weights:**

| Category | Weight |
|----------|--------|
| Self-Healing (Pod Chaos) | 25% |
| CPU Resilience | 15% |
| Memory Resilience | 15% |
| Network Resilience | 15% |
| Packet Resilience | 15% |
| Recovery Validation | 15% |

**Grades:** A+ (90–100) · A (80–89) · B (70–79) · C (60–69) · D (45–59) · F (0–44)

**Expected scores by image:**

| Image | Peak CPU | Peak Memory | Expected Score |
|-------|----------|-------------|----------------|
| nginx:latest | ~10m | ~5MB | 95–98 |
| redis:alpine | ~50m | ~30MB | 85–90 |
| httpd:latest | ~80m | ~50MB | 80–86 |
| mysql:8.0 | ~200m | ~400MB | 55–65 |
| python:3.9 | ~30m | ~20MB | 88–92 |

---

## Monitoring

Each test result page includes a **View Grafana Metrics** button that embeds live Grafana panels inline:

- CPU Usage
- Memory Usage (WSS)
- Receive Bandwidth
- Transmit Bandwidth

Panels are scoped to the specific pod being tested and show data from the last 1 hour with 10-second refresh. A link to the full Grafana dashboard is also provided.

---

## Feature Status

| # | Feature | Status |
|---|---------|--------|
| 1 | Web Dashboard (dark terminal UI) | Done |
| 2 | Dynamic Kubernetes Deployment | Done |
| 3 | Automated Chaos Testing (5 tests) | Done |
| 4 | Resilience Scoring Engine | Done |
| 5 | Letter Grades A+/A/B/C/D/F | Done |
| 6 | Loading Screen (async + polling) | Done |
| 7 | Auto-cleanup after testing | Done |
| 8 | GitHub Repository + README | Done |
| 9 | PDF Report Download | Done |
| 10 | Batch Testing (multiple images) | Done |
| 11 | User Accounts + Login + Register | Done |
| 12 | Test History per User (SQLite) | Done |
| 13 | Email Notifications (Gmail SMTP) | Done |
| 14 | Docker image (amd64 fix for M2) | Done |
| 15 | AWS EKS Cluster (2x t3.small) | Done |
| 16 | Chaos Mesh on EKS | Done |
| 17 | Prometheus + Grafana on EKS | Done |
| 18 | Live public URL (AWS Load Balancer) | Done |
| 19 | CPU + Memory metrics during chaos tests | Done |
| 20 | Realistic scoring (CPU + Mem + Recovery) | Done |
| 21 | Grafana monitoring button on results page | Done |
| 22 | Cloud SSL + Custom Domain | Pending |

---

## File Structure

```
resilience-platform/
├── app.py                        # Flask web server (port 5001)
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Docker build (linux/amd64)
├── templates/
│   ├── index.html                # Dashboard — Docker image input
│   ├── result.html               # Results page with scores + Grafana monitoring
│   ├── history.html              # Test history per user
│   ├── loading.html              # Async loading screen
│   ├── monitoring.html           # Monitoring page
│   ├── login.html                # Login page
│   └── register.html             # Register page
├── static/
│   └── style.css                 # Dark terminal-style theme
└── services/
    ├── deployer.py               # Dynamic K8s deployment generator
    ├── chaos_runner.py           # Chaos experiment engine + metrics collection
    └── scorer.py                 # Weighted score calculation engine
```

---

## How to Run (Local)

### Prerequisites
- Python 3 + pip
- kubectl configured (minikube or EKS)
- Chaos Mesh installed in `chaos-testing` namespace
- Prometheus + Grafana running in `monitoring` namespace

### Start the platform
```bash
cd ~/kitchenofthebunny/resilience-platform
source venv/bin/activate
python3 app.py
```

Open `http://127.0.0.1:5001`

---

## How to Run (AWS EKS)

### Switch kubectl to EKS
```bash
aws eks update-kubeconfig --region us-east-1 --name resilience-cluster
kubectl get nodes
```

### Rebuild and deploy after any code change
```bash
docker buildx build --platform linux/amd64 -t ashu804/resilience-platform:latest --push .
kubectl rollout restart deployment resilience-platform
kubectl rollout status deployment resilience-platform


### Live URL

c41d694a9a2269ab9eed-290100455.us-east-1.elb.amazonaws.com


---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| kubectl points to minikube | `aws eks update-kubeconfig --region us-east-1 --name resilience-cluster` |
| ImagePullBackOff on EKS | Rebuild with `--platform linux/amd64` (M2 Mac issue) |
| All images get same score | Update `chaos_runner.py` + `scorer.py` with v5.0 code |
| Port 5001 in use | `lsof -i :5001` then `kill -9 <PID>` |
| venv not activated | `source venv/bin/activate` |
| Chaos test FAIL | `kubectl get pods -n chaos-testing` — all must be Running |
| Grafana panels blank | Check anonymous access env vars on grafana deployment |
| No metrics data | Run `kubectl top nodes` to verify metrics-server is running |

---

## License

MIT — built for learning, portfolio, and chaos engineering exploration.
