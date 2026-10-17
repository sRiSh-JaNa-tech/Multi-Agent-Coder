# <p align="center"><img src="frontend/public/assets/open-folder.png" width="100" height="100" alt="FileWiz Logo"><br>FileWiz</p>

<p align="center">
  <strong>The Ultimate Universal File Utility Engine</strong><br>
  <em>Compress, Extract, Optimize, and Secure your files through a high-performance, decoupled microservices web interface.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Architecture-Microservices-blueviolet.svg" alt="Microservices">
  <img src="https://img.shields.io/badge/Orchestration-Kubernetes-blue.svg" alt="Kubernetes">
  <img src="https://img.shields.io/badge/Node.js-v18+-green.svg" alt="Node.js">
  <img src="https://img.shields.io/badge/React-v18%2F19-cyan.svg" alt="React">
  <img src="https://img.shields.io/badge/Database-SQLite-003B57.svg" alt="SQLite">
  <img src="https://img.shields.io/badge/Compression-7--Zip-FF6600.svg" alt="7-Zip">
  <img src="https://img.shields.io/badge/Security-Hardened%20(10%2F10)-brightgreen.svg" alt="Security Hardened">
  <img src="https://img.shields.io/badge/Tests-45%2F45%20Passing-success.svg" alt="Tests">
</p>

---

## 📖 Table of Contents
- [Overview](#-overview)
- [Decoupled Microservices Architecture](#-decoupled-microservices-architecture)
- [Core Features](#-core-features)
- [Security Hardening & Threat Mitigations](#-security-hardening--threat-mitigations)
- [Kubernetes Deployment](#-kubernetes-deployment)
- [Local Development](#-local-development)
- [Automated End-to-End Testing](#-automated-end-to-end-testing)
- [System Architecture Document](#-system-architecture-document)

---

## 🌟 Overview

**FileWiz** is an enterprise-ready, containerized microservices file utility platform designed to perform secure, high-throughput document manipulation directly from the browser. It eliminates the need for desktop installations or risky third-party cloud converters by isolating processing engines inside dedicated, sandboxed environments.

FileWiz handles high-efficiency **7-Zip PDF compression**, archive inspection with anti-Zip-Slip/Zip-Bomb protections, encrypted document delivery, PDF splitting, redaction, and multi-format conversion.

---

## 🏗️ Decoupled Microservices Architecture

The platform is structured into four decoupled services running in isolated pods with zero-trust networking:

```
                                ┌───────────────────────────┐
                                │  Kubernetes NGINX Ingress │
                                └─────────────┬─────────────┘
                                              │
         ┌────────────────────────────────────┼────────────────────────────────────┐
         │ /auth                              │ /compress, /split, /peek, ...     │ / (SPA)
         ▼                                    ▼                                    ▼
┌──────────────────┐                ┌──────────────────┐                 ┌──────────────────┐
│  authentication  │                │     backend      │                 │     frontend     │
│  (Node.js / JWT) │                │ (Node.js/7-Zip)  │                 │  (React / Vite)  │
│    Port: 4000    │                │    Port: 3000    │                 │    Port: 80      │
└────────┬─────────┘                └────────┬─────────┘                 └──────────────────┘
         │                                   │
         │ x-internal-service-key            │ Ephemeral Workspace
         ▼ (ClusterIP Only)                  ▼
┌──────────────────┐                ┌──────────────────┐
│     database     │                │ backend-temp-pvc │
│ (SQLite Service) │                │    (Storage)     │
│    Port: 5000    │                └──────────────────┘
└──────────────────┘
```

1. **`frontend/`**: Single-Page Application (SPA) built with React, Vite, TypeScript, and Tailwind CSS.
2. **`authentication/`**: Dedicated authentication microservice handling bcrypt password hashing (10 salt rounds), JWT issuance/verification, and secure session management.
3. **`backend/`**: High-performance document processing engine powered by 7-Zip (`7za`), Python 3 automation scripts invoked safely via `child_process.execFile()`, and ephemeral workspace managers.
4. **`database/`**: Dedicated SQLite microservice with RESTful CRUD endpoints, in-memory WASM execution via `sql.js`, persistent disk synchronization, and internal service key access control.

---

## 🚀 Core Features

- **📄 7-Zip Ultra PDF Compression**: High-efficiency compression engine powered by 7-Zip (`7za`) supporting Normal, Low, and Extreme compression profiles with verification of binary signatures (`377abcaf271c`).
- **📦 Hardened ZIP Inspector**: Peek inside ZIP archives, browse directory hierarchies, and inspect files with protection against Zip Slip path traversals and Zip Bomb denial of service.
- **✂️ Secure PDF Splitter**: Split multi-page documents by page ranges or fixed parts with strict parameter allowlists preventing command injection.
- **🔐 AES PDF Encryption & Redaction**: Password-protect documents and safely redact confidential text strings.
- **🔑 Decoupled Auth & Role Controls**: Independent authentication service providing stateless JWT authentication with admin-gated user management.
- **🛡️ Multi-Layer Security Suite**: Rate limiting, magic-byte inspection, strict CORS whitelisting, stripped credential responses, and fail-closed boot checks.
- **🧪 45-Point Automated Test Suite**: Full coverage spanning database CRUD, authentication flows, 7-Zip processing, security regression exploits, and cross-service integration journeys.

---

## 🛡️ Security Hardening & Threat Mitigations

FileWiz has been systematically audited and hardened against 10 critical security vectors:

| ID | Vulnerability / Threat | Severity | Mitigation Implemented |
|:---|:---|:---:|:---|
| **1** | **Remote Code Execution (RCE)** | Critical (9.8) | Replaced `exec()` shell concatenation with `execFile()` (`shell: false`) in `pythonRunner.js`. Enforced strict parameter allowlists for compression levels, split modes, and page range formats (`/^\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*$/`). |
| **2** | **Zip Slip & Zip Bomb** | Critical (9.1) | Implemented `safeExtractZip()` in `peekRouter.js` enforcing canonical base-directory checks. Added resource limits: 2,000 files, 100MB uncompressed limit, 50MB per-file limit, and 50:1 decompression ratio caps. |
| **3** | **Arbitrary File Read / Packaging** | Critical (8.6) | Confined archive downloads in `splitRouter.js` strictly within the generated job sandbox (`temp/splits/jobId`). Path traversals and unauthorized paths return `403 Forbidden`. |
| **4** | **Static `/temp` Exposure** | High (8.5) | Removed `express.static('/temp')` and removed `/temp` from Kubernetes Ingress. File previews and downloads require authentication and job ownership verification. |
| **5** | **Unauthenticated Database Endpoints** | High (8.2) | Gated all database service endpoints behind `x-internal-service-key`. Stripped password hashes completely from public responses. Gated debug auth endpoints behind admin keys. |
| **6** | **Unauthenticated File Processing** | High (7.5) | Attached `isAuthenticated` across all compute-heavy routes (`/compress/*`, `/split/*`, `/peek/*`, `/convert`, `/encrypt`, etc.). Added `express-rate-limit` (60 req / 15 min). |
| **7** | **Permissive CORS Configurations** | High (7.4) | Replaced wildcard `origin: true` reflection with strict origin whitelisting (`FRONTEND_ORIGIN || http://localhost:5173`). Unknown origins are rejected when credentials are enabled. |
| **8** | **Plaintext & Stale Secrets** | High (7.5) | Removed plaintext secrets from Kubernetes manifests. Added fail-closed checks on boot terminating in production if `JWT_SECRET` is unset, default, or `< 32` characters. |
| **9** | **Client Cookie Quota Manipulation** | Medium (5.3) | Migrated usage tracking from client cookies to server-side sliding-window stores keyed by client IP, backed by HMAC-signed tamper-evident cookies. |
| **10** | **File Upload Hardening & Headers** | Medium (6.5) | Enforced 50MB file size caps, added binary magic byte validation (`%PDF-`, `PK\x03\x04`, `7z`), applied `helmet()` headers across microservices, and enforced TLS/HSTS in Ingress. |

---

## ☸️ Kubernetes Deployment

All Kubernetes manifests are located in [`Deployment/`](file:///c:/Users/srish/Desktop/FileWiz/Deployment/):

```bash
# 1. Apply namespace & secrets
kubectl apply -f Deployment/00-namespace.yaml
kubectl apply -f Deployment/01-config-secrets.yaml

# 2. Deploy isolated microservices
kubectl apply -f Deployment/02-database-deployment.yaml
kubectl apply -f Deployment/03-auth-deployment.yaml
kubectl apply -f Deployment/04-backend-deployment.yaml
kubectl apply -f Deployment/05-frontend-deployment.yaml

# 3. Apply ingress & zero-trust network policies
kubectl apply -f Deployment/06-ingress.yaml
kubectl apply -f Deployment/07-network-policy.yaml
```

Verify the deployment:
```bash
kubectl get pods -n filewiz
kubectl get svc -n filewiz
kubectl get networkpolicies -n filewiz
```

---

## 💻 Local Development

### 1. Database Microservice (SQLite)
```bash
cd database
npm install
npm run dev
# Running on http://localhost:5000 (Internal Key: filewiz-internal-db-secret)
```

### 2. Authentication Microservice
```bash
cd authentication
npm install
npm run dev
# Running on http://localhost:4000
```

### 3. Backend Processing Microservice
```bash
cd backend
npm install
npm run dev
# Running on http://localhost:3000
```

### 4. Frontend Single-Page App
```bash
cd frontend
npm install
npm run dev
# Running on http://localhost:5173
```

---

## 🧪 Automated End-to-End Testing

FileWiz includes a unified automated test framework that boots isolated microservice test instances on dedicated ports (`5001`, `4001`, `3001`), executes all checks, and tears down cleanly.

```bash
# Run all 45 automated tests from the workspace root:
npm test
```

### Test Suite Structure:
- **Suite 1: SQLite Database Microservice (10/10)**: Health checks, unauthorized direct access blocking (403), user creation, duplicate prevention (409), password hash stripping on query, password access with internal flag, query by ID, user listing, and record deletion.
- **Suite 2: Authentication Microservice (15/15)**: Registration, duplicate rejection, credential validation, bcrypt login, JWT issuance, wrong password rejection (401), cookie session verification, profile endpoint, token verification, public user dump prevention (403), admin access, and logout.
- **Suite 3: Backend & Security Hardening (13/13)**: Auth middleware protection across all endpoints (401), authenticated 7-Zip PDF compression, `.7z` magic byte verification (`377abcaf271c`), command injection attempt rejection, Zip Slip directory traversal blocking, arbitrary file exfiltration blocking, MIME spoofing blocking, and authenticated ZIP inspection.
- **Suite 4: Cross-Microservice Integration Flow (7/7)**: Full user journey (Registration -> Direct SQLite verification -> Login -> JWT -> Backend access -> 7-Zip compression -> `.7z` download & integrity check -> Database cleanup).

---

## 📐 System Architecture Document

For a comprehensive deep-dive into the technical architecture, sequence diagrams, network topologies, and microservice contracts, consult:
👉 **[`architecture.md`](file:///c:/Users/srish/Desktop/FileWiz/architecture.md)**

---

<p align="center">Built with ❤️ for High-Performance, Secure Document Workflows</p>
