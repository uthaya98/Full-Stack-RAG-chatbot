# Full-Stack-RAG-chatbot

A **cloud-native chatbot platform** for Zus Coffee built using **React (Vite)** for the frontend, a **Python-based backend API**, **Docker**, **GitHub Actions CI/CD**, and **Kubernetes**.

This project demonstrates an end-to-end **DevOps + Full-Stack** workflow suitable for production and technical interviews.

---

## 📁 Project Structure

```text
ZUSCOFFEE-CHATBOT
│
├── .github/workflows/
│   └── CI-CD.yaml                # GitHub Actions CI/CD pipeline
│
├── backend/                      # Backend REST API (Dockerized)
│   ├── app/                      # Application source code
│   ├── dependencies/             # Dependency artifacts
│   ├── layer/                    # Shared libraries / internal layers
│   ├── dockerfile                # Backend Dockerfile
│   ├── dockerfile_old.txt        # Legacy Dockerfile (reference)
│   ├── handler.py                # Backend entry logic
│   ├── requirements.txt          # Python dependencies
│   ├── response.json             # Sample API response
│   └── zuscoffee-chatbot-config.json
│
├── CICD/k8s/                     # Kubernetes manifests
│   ├── backend-deployment.yaml   # Backend Deployment & Service
│   ├── frontend-deployment.yaml  # Frontend Deployment & Service
│   └── ingress.yaml              # Ingress configuration
│
├── frontend/                     # Frontend (React + Vite)
│   ├── dist/                     # Production build output
│   ├── node_modules/             # Node dependencies
│   ├── public/                   # Static assets
│   ├── src/                      # React source code
│   ├── dockerfile                # Frontend Dockerfile
│   ├── eslint.config.js           # ESLint configuration
│   ├── index.html                # App entry point
│   ├── package.json              # NPM config
│   ├── package-lock.json         # Dependency lock file
│   └── vite.config.js             # Vite configuration
│
└── README.md                     # Project documentation
```

---

## 🧠 Architecture Overview

### High-Level Components

**Frontend (React + Vite)**
- Single Page Application (SPA)
- Communicates with backend via REST APIs
- Served as a containerized app in Kubernetes

**Backend (Python REST API)**
- Handles chatbot logic and request processing
- Exposes REST endpoints
- Runs as a Kubernetes service

**CI/CD Pipeline**
- Automated via GitHub Actions
- Builds Docker images
- Pushes images to AWS ECR
- Deploys to Kubernetes cluster

---

## 🔄 Application Flow (Request Lifecycle)

```text
User Browser
     │
     ▼
React Frontend (Vite SPA)
     │  HTTP/JSON
     ▼
Kubernetes Ingress (NGINX / ALB)
     │
     ▼
Backend Service (Python API Pod)
     │
     ▼
Chatbot Processing Logic
     │
     ▼
Response Returned to Frontend
     │
     ▼
User Sees Chatbot Reply
```

---

## 🔄 CI/CD Flow (GitHub Actions)

```text
Developer Pushes Code
        │
        ▼
GitHub Actions Triggered
        │
        ├─ Build Frontend Docker Image
        ├─ Build Backend Docker Image
        │
        ▼
Authenticate to AWS ECR
        │
        ▼
Push Docker Images to ECR
        │
        ▼
Deploy to Kubernetes Cluster
        │
        ▼
Rolling Update of Pods
```

---

## 🐳 Docker

### Backend

```bash
docker build -t zuscoffee-backend ./backend
docker run -p 8000:8000 zuscoffee-backend
```

### Frontend (React)

```bash
docker build -t zuscoffee-frontend ./frontend
docker run -p 3000:3000 zuscoffee-frontend
```

---

## ☸️ Kubernetes Deployment

Manifests are located in:

```text
CICD/k8s/
```

### Deploy Resources

```bash
kubectl apply -f CICD/k8s/backend-deployment.yaml
kubectl apply -f CICD/k8s/frontend-deployment.yaml
kubectl apply -f CICD/k8s/ingress.yaml
```

### Validate Deployment

```bash
kubectl get pods
kubectl get svc
kubectl get ingress
```

---

## 📦 Environment Variables

### Backend

```text
LOG_LEVEL
API_PORT
```

### Frontend (React)

```text
VITE_API_BASE_URL
```

---

## 🛠️ Tech Stack

- **Frontend**: React, Vite, JavaScript, HTML, CSS
- **Backend**: Python REST API
- **Containers**: Docker
- **CI/CD**: GitHub Actions
- **Container Registry**: AWS ECR
- **Orchestration**: Kubernetes
- **Ingress**: NGINX / ALB

---

## 📌 Best Practices Demonstrated

- Containerized microservices
- Environment-based configuration
- Infrastructure as Code (Kubernetes YAML)
- Automated CI/CD pipelines
- Scalable frontend-backend separation

---

## 📌 Future Enhancements

- Authentication & Authorization
- Observability (Prometheus + Grafana)
- Horizontal Pod Autoscaling (HPA)
- Helm-based deployments
- Persistent chat history storage

---

## 👨‍💻 Author

**Uthayasurian Salavamani**  
DevOps / Cloud / Full-Stack Engineer

---

## 📄 License

This project is licensed for educational and demonstration purposes.

---

⭐ If you find this project useful, consider giving it a star!

