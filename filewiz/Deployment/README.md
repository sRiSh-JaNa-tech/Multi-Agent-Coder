# FileWiz Kubernetes Deployment Guide

This directory contains standalone Kubernetes manifests for deploying the FileWiz microservices platform.

## Architecture

```
                    ┌───────────────────────────┐
                    │      FileWiz Ingress      │
                    │       (port 80/443)       │
                    └─────────────┬─────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │ /auth                  │ /compress, /peek, ...  │ / (UI)
         ▼                        ▼                        ▼
┌──────────────────┐    ┌──────────────────┐     ┌──────────────────┐
│   auth-service   │    │  backend-service │     │ frontend-service │
│   (Port: 4000)   │    │   (Port: 3000)   │     │   (Port: 80)     │
└────────┬─────────┘    └────────┬─────────┘     └──────────────────┘
         │                       │
         │ http://:5000          │ (PVC: temp scratch storage)
         ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│ database-service │    │ backend-temp-pvc │
│  (SQLite: 5000)  │    │      (5 Gi)      │
└──────────────────┘    └──────────────────┘
```

## Manifests

| File | Resource | Description |
|---|---|---|
| `00-namespace.yaml` | `Namespace` | Creates isolated `filewiz` namespace. |
| `01-config-secrets.yaml` | `ConfigMap`, `Secret` | Central environment configs, URLs, and JWT secrets. |
| `02-database-deployment.yaml` | `PVC`, `Deployment`, `Service` | Dedicated SQLite database service on port `5000`. |
| `03-auth-deployment.yaml` | `Deployment`, `Service` | Authentication service (`auth-service`) on port `4000`. |
| `04-backend-deployment.yaml` | `PVC`, `Deployment`, `Service` | Document processing service (`backend-service`) on port `3000`. |
| `05-frontend-deployment.yaml` | `Deployment`, `Service` | React web UI on NodePort `30080` (port `80`). |
| `06-ingress.yaml` | `Ingress` | Optional HTTP ingress path routing. |
| `07-network-policy.yaml` | `NetworkPolicy` | Enforces strict network isolation between Database, Auth, Backend, and Frontend pods. |

## Quick Start Deployment

### 1. Build and Tag Container Images
```bash
# Frontend
docker build -t filewiz-frontend:v1 ./frontend

# Backend
docker build -t filewiz-backend:v1 ./backend

# Authentication
docker build -t filewiz-auth:v1 ./authentication

# Database (optional if using standard mongo:7.0)
docker build -t filewiz-database:v1 ./database
```

### 2. Apply Kubernetes Manifests in Order
```bash
kubectl apply -f Deployment/00-namespace.yaml
kubectl apply -f Deployment/01-config-secrets.yaml
kubectl apply -f Deployment/02-database-deployment.yaml
kubectl apply -f Deployment/03-auth-deployment.yaml
kubectl apply -f Deployment/04-backend-deployment.yaml
kubectl apply -f Deployment/05-frontend-deployment.yaml
```

Or deploy all at once:
```bash
kubectl apply -f Deployment/
```

### 3. Check Status
```bash
kubectl get pods -n filewiz
kubectl get svc -n filewiz
```

### 4. Access the Application
- If using NodePort: Open `http://<node-ip>:30080`
- If using Minikube: `minikube service frontend-service -n filewiz`
- If using Ingress: Configure DNS or `/etc/hosts` and access via Ingress IP / hostname.
