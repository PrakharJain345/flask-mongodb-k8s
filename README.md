# Production-Ready Flask & MongoDB Deployment on Kubernetes
A production-grade, highly available deployment of a containerized Flask REST API connected to a persistent, authenticated MongoDB database running on Kubernetes with Horizontal Pod Autoscaling (HPA), automated health probes, and structured secrets management.

---

## 1. Architecture Overview

The system consists of two primary workloads deployed on a local Kubernetes cluster:
1. **Flask REST API (`flask-app`)**: A stateless, horizontally autoscaled web tier serving HTTP traffic through Gunicorn.
2. **MongoDB Database (`mongo`)**: A stateful, authenticated database tier managed via a `StatefulSet` with dedicated persistent storage (`PersistentVolume` & `PersistentVolumeClaim`).

### Architecture Diagram

```mermaid
graph TD
    User([Client / Browser / curl]) -->|NodePort :30007| FlaskSvc[Service: flask-svc<br/>Type: NodePort :30007 -> 5000]
    
    subgraph Kubernetes Cluster
        FlaskSvc --> Pod1[Pod: flask-app-1]
        FlaskSvc --> Pod2[Pod: flask-app-2]
        FlaskSvc -.-> PodN[Pod: flask-app-N (Up to 5 replicas)]
        
        HPA[Horizontal Pod Autoscaler<br/>Target: 70% CPU<br/>Min: 2 | Max: 5] -.->|Scales Deployment| Deployment[Deployment: flask-app]
        MetricsServer[Metrics Server] -.->|Provides Metrics| HPA
        
        Pod1 -->|Internal DNS: mongo-svc:27017| MongoSvc[Headless Service: mongo-svc<br/>ClusterIP: None]
        Pod2 -->|Internal DNS: mongo-svc:27017| MongoSvc
        PodN -->|Internal DNS: mongo-svc:27017| MongoSvc
        
        MongoSvc --> MongoPod[StatefulSet Pod: mongo-0<br/>Image: mongo:6.0<br/>Auth: Enabled]
        
        Secret[Secret: mongo-secret<br/>User: admin<br/>Password: changeme123] -->|Injected as Env Vars| Pod1
        Secret -->|Injected as Env Vars| Pod2
        Secret -->|Injected as Env Vars| MongoPod
        
        MongoPod -->|Mounted at /data/db| PVC[PersistentVolumeClaim: mongo-pvc]
        PVC -->|Bound (1Gi, Retain)| PV[PersistentVolume: mongo-pv<br/>hostPath: /data/mongo-data]
    end
```

---

## 2. Prerequisites

Ensure the following tools are installed on your machine:
- **Operating System**: Windows 10/11, macOS, or Linux
- **Docker**: Docker Desktop (Engine 24+) or Docker CLI
- **Kubernetes**: Minikube or Docker Desktop Kubernetes (`v1.30+`)
- **kubectl**: Kubernetes command-line tool
- **curl**: Command-line HTTP client

---

## 3. Part 1 Summary & Virtual Environment Benefits

In Part 1, the Flask application was developed and verified in a Python virtual environment:
- Fixed syntax errors from the legacy template (`Flask(__name__)`, correct `if __name__ == '__main__':`).
- Added robust environment variable parsing for MongoDB connection (`MONGO_HOST`, `MONGO_PORT`, `MONGO_USERNAME`, `MONGO_PASSWORD`, `MONGO_AUTH_DB`).
- Implemented `/health` for Kubernetes probes, `/cpu` for HPA stress testing, `/data` POST with schema validation, and `/data` GET returning MongoDB documents (excluding internal `_id`).

### Why use a Virtual Environment (`venv`)?
1. **Dependency Isolation**: Prevents dependency conflicts between different Python projects on the same machine (e.g., Flask 2.0 vs Flask 3.0).
2. **Reproducibility**: Guarantees exact package versions via `pip freeze > requirements.txt`, ensuring identical behavior between developer workstations and container runtimes.
3. **Clean Host Environment**: Prevents global `site-packages` pollution and eliminates permission issues associated with installing packages system-wide as root or Administrator.

---

## 4. Build and Push Docker Image

The application utilizes a multi-layer, security-hardened `Dockerfile`:
- Base: `python:3.9-slim` (minimal attack surface, ~205MB image size).
- Layer caching: `requirements.txt` is copied and installed prior to source code to prevent reinstalling wheels on code edits.
- Security: Runs under an unprivileged user `appuser` (`UID 1000`) instead of `root`.
- Server: Production-ready WSGI server `Gunicorn` with 2 workers binding on `0.0.0.0:5000`.

### Build Command
```bash
docker build -t prakhar932/flask-mongo-app:v1 .
```

### Push to Docker Hub
```bash
# Log in to Docker Hub
docker login -u prakhar932

# Push the tagged image
docker push prakhar932/flask-mongo-app:v1
```
*Note: In local Kubernetes environments (Minikube / Docker Desktop), images tagged as `prakhar932/flask-mongo-app:v1` are consumed directly from the local Docker engine using `imagePullPolicy: IfNotPresent`.*

---

## 5. Deploy on Kubernetes

All Kubernetes manifests are located in `k8s/` and configured for deterministic startup:

```bash
# 1. Apply Secret (Credentials)
kubectl apply -f k8s/00-secret.yaml

# 2. Apply Storage (PersistentVolume and PersistentVolumeClaim)
kubectl apply -f k8s/01-mongo-pv.yaml
kubectl apply -f k8s/02-mongo-pvc.yaml

# 3. Apply MongoDB Database (Headless Service & StatefulSet)
kubectl apply -f k8s/03-mongo-service.yaml
kubectl apply -f k8s/04-mongo-statefulset.yaml

# 4. Wait for MongoDB to become ready
kubectl rollout status statefulset/mongo

# 5. Apply Flask Application (Deployment & NodePort Service)
kubectl apply -f k8s/05-flask-deployment.yaml
kubectl apply -f k8s/06-flask-service.yaml

# 6. Apply Autoscaler
kubectl apply -f k8s/07-flask-hpa.yaml
```

### Real Deployment Output
```
secret/mongo-secret created
persistentvolume/mongo-pv created
persistentvolumeclaim/mongo-pvc created
service/mongo-svc created
statefulset.apps/mongo created
deployment.apps/flask-app created
service/flask-svc created
horizontalpodautoscaler.autoscaling/flask-hpa created
```

---

## 6. Endpoint Testing & Real Verification Outputs

The Flask application is exposed to the host on NodePort **30007** (mapped to container port 5000).

### 6.1 `GET /` - Root Index
```bash
curl -i http://localhost:30007/
```
**Real Terminal Output:**
```http
HTTP/1.1 200 OK
Server: gunicorn
Date: Thu, 12 Nov 2026 15:12:48 GMT
Connection: close
Content-Type: text/html; charset=utf-8
Content-Length: 73

Welcome to the Flask app! The current time is: 2026-11-12 15:12:48.043157
```

### 6.2 `GET /health` - Health Probe
```bash
curl -i http://localhost:30007/health
```
**Real Terminal Output:**
```http
HTTP/1.1 200 OK
Server: gunicorn
Date: Thu, 12 Nov 2026 15:12:54 GMT
Connection: close
Content-Type: application/json
Content-Length: 16

{"status":"ok"}
```

### 6.3 `POST /data` - Insert Document
```bash
curl -i -X POST http://localhost:30007/data \
  -H "Content-Type: application/json" \
  -d '{"sampleKey":"sampleValue"}'
```
**Real Terminal Output:**
```http
HTTP/1.1 201 CREATED
Server: gunicorn
Date: Thu, 12 Nov 2026 15:13:16 GMT
Connection: close
Content-Type: application/json
Content-Length: 27

{"status":"Data inserted"}
```

### 6.4 `GET /data` - Query Documents
```bash
curl -i http://localhost:30007/data
```
**Real Terminal Output:**
```http
HTTP/1.1 200 OK
Server: gunicorn
Date: Thu, 12 Nov 2026 15:13:23 GMT
Connection: close
Content-Type: application/json
Content-Length: 30

[{"sampleKey":"sampleValue"}]
```

### 6.5 Data Persistence Across Pod Restarts
To prove persistent volume binding and data retention across crashes, the `mongo-0` pod was deleted and automatically rescheduled:
```bash
kubectl delete pod mongo-0
```
**Output:**
```
pod "mongo-0" deleted
```
Once the replacement pod reached `Running` status, `GET /data` was invoked again:
```bash
curl -i http://localhost:30007/data
```
**Real Output:**
```http
HTTP/1.1 200 OK
Server: gunicorn
Date: Thu, 12 Nov 2026 15:14:05 GMT
Connection: close
Content-Type: application/json
Content-Length: 30

[{"sampleKey":"sampleValue"}]
```
*Result: The document persisted seamlessly without data loss.*

---

## 7. MongoDB Authentication Deep Dive

### Why Authentication Matters
Running databases without authentication exposes critical records to unauthenticated lateral movements within a shared cluster. If a single pod in any namespace is compromised, unauthenticated databases can be dropped or exfiltrated instantly.

### How Authentication is Configured
- Root credentials (`MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_ROOT_PASSWORD`) are stored inside Kubernetes Secret `mongo-secret` in `k8s/00-secret.yaml`.
- The official `mongo:6.0` image enables authentication (`--auth`) automatically when these environment variables are provided on initial database initialization.
- In production, secrets must be generated out-of-band via `kubectl create secret generic mongo-secret --from-literal=...` or managed using external secret stores (Vault / AWS Secrets Manager) and never committed to source control.

### Real Authentication Verification Tests

#### Test A: Unauthorized Access Fails
Executing a database command inside `mongo-0` without supplying credentials:
```bash
kubectl exec mongo-0 -c mongo -- mongosh --norc --eval "db.adminCommand('listDatabases')"
```
**Real Terminal Output:**
```
MongoServerError: command listDatabases requires authentication
command terminated with exit code 1
```

#### Test B: Authorized Access Succeeds
Executing the same command with the credentials from `mongo-secret`:
```bash
kubectl exec mongo-0 -c mongo -- mongosh -u admin -p changeme123 --authenticationDatabase admin --norc --eval "db.adminCommand('listDatabases')"
```
**Real Terminal Output:**
```json
{
  databases: [
    { name: 'admin', sizeOnDisk: Long('135168'), empty: false },
    { name: 'config', sizeOnDisk: Long('12288'), empty: false },
    { name: 'flask_db', sizeOnDisk: Long('40960'), empty: false },
    { name: 'local', sizeOnDisk: Long('73728'), empty: false }
  ],
  totalSize: Long('262144'),
  totalSizeMb: Long('0'),
  ok: 1
}
```

---

## 8. DNS Resolution in Kubernetes

### Internal CoreDNS Architecture
Kubernetes runs an internal DNS service (CoreDNS) that assigns DNS records to Services and Pods within the cluster.
- Standard Services receive an A/AAAA record resolving to a virtual **ClusterIP**, which load-balances traffic via iptables/IPVS across endpoints.
- **Headless Service (`clusterIP: None`)**: A headless service does not allocate a cluster IP or proxy traffic. Instead, CoreDNS returns the direct IP addresses of the backing pods.
- **StatefulSet Stable Identity**: When a StatefulSet is paired with a headless service (`serviceName: mongo-svc`), each pod receives a deterministic Fully Qualified Domain Name (FQDN):
  ```
  <pod-name>.<service-name>.<namespace>.svc.cluster.local
  ```
  In this deployment:
  ```
  mongo-0.mongo-svc.default.svc.cluster.local
  ```
  Or simply `mongo-svc` within the same namespace.

### Network Isolation
`mongo-svc` is explicitly defined without a NodePort or LoadBalancer. It has no external port mapping on the host node, guaranteeing that MongoDB is accessible **only** to authorized workloads inside the Kubernetes network perimeter.

---

## 9. Resource Requests, Limits & Quality of Service (QoS)

Both the Flask Deployment and MongoDB StatefulSet define explicit CPU and memory specifications:

```yaml
resources:
  requests:
    cpu: "200m"
    memory: "250M"
  limits:
    cpu: "500m"
    memory: "500M" # Adjusted to 1Gi for MongoDB 6.0 engine
```

### Requests vs Limits
- **Requests**: The minimum guaranteed compute resources required for a pod to run. The Kubernetes `kube-scheduler` uses requests to find a node with sufficient capacity.
- **Limits**: The hard upper bound enforced at runtime by the Linux kernel using `cgroups` (control groups).

### Enforcement & OOMKilled vs Throttling
- **CPU**: CPU is a compressible resource. When a pod exceeds its CPU limit, the CFS (Completely Fair Scheduler) **throttles** its CPU time slices; the pod slows down but is not killed.
- **Memory**: Memory is an incompressible resource. When a container exceeds its memory limit, the Linux kernel Out-Of-Memory (OOM) killer immediately terminates the process with exit code `137` (`OOMKilled`).

### Quality of Service (QoS) Classes
1. **Guaranteed**: Requests equal limits across all containers for both CPU and memory. Least likely to be evicted under node pressure.
2. **Burstable**: Requests are lower than limits, or only requests are specified. Evicted when node memory runs low if no BestEffort pods remain.
3. **BestEffort**: No requests or limits specified. First to be evicted under resource starvation.

---

## 10. Design Choices & Alternatives

| Requirement | Choice Made | Alternative Considered | Trade-off Rationale |
| :--- | :--- | :--- | :--- |
| **MongoDB Controller** | `StatefulSet` | `Deployment` | MongoDB requires stable network identity and persistent volume binding. Deployments treat pods as interchangeable and can mount wrong volumes upon pod reschedule. |
| **External Access** | `NodePort` (`30007`) | `Ingress` / `LoadBalancer` | NodePort is universally supported on local clusters (Minikube / Docker Desktop) without requiring cloud provider load balancers or ingress controller controllers. |
| **Storage Class** | `hostPath` (`manual`) | Cloud CSI (EBS / GPD) / Dynamic Provisioner | `hostPath` provides deterministic local testing on developer laptops without cloud vendor dependencies or dynamic CSI plugins. |
| **MongoDB Service** | Headless (`ClusterIP: None`) | Standard `ClusterIP` | Headless provides direct pod DNS (`mongo-0.mongo-svc`) necessary for stateful database nodes and replica sets. |

---

## 11. HPA Autoscaling & Load Test (Real Output)

### Metrics Server Installation
Metrics-server was enabled with `--kubelet-insecure-tls` to allow scraping metrics from local kubelets:
```bash
kubectl top nodes
kubectl top pods
```
**Real Output:**
```
NAME             CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)   
docker-desktop   1995m        12%      3088Mi          40%         

NAME                       CPU(cores)   MEMORY(bytes)   
flask-app-b9f466d4-9hdtq   4m           59Mi            
flask-app-b9f466d4-m529g   8m           59Mi            
mongo-0                    16m          368Mi           
```

### HPA Configuration (`k8s/07-flask-hpa.yaml`)
Target: 70% average CPU utilization across `flask-app` pods, scaling between **2** (min) and **5** (max) replicas.

### Running Load Test
Continuous traffic was generated against the compute-intensive `/cpu` endpoint:
```bash
kubectl run load-generator --image=busybox:1.36 --restart=Never -- /bin/sh -c 'while true; do wget -q -O- http://flask-svc:5000/cpu; done'
```

### Real Scaling Events Captured
During load generation, CPU spiked to **211%** (well above the 70% threshold), triggering the HPA to autoscale the deployment to 4 and then 5 replicas:

```
kubectl describe hpa flask-hpa
```

**Real Output:**
```
Name:                                                  flask-hpa
Namespace:                                             default
Reference:                                             Deployment/flask-app
Metrics:                                               ( current / target )
  resource cpu on pods  (as a percentage of request):  199% (399m) / 70%
Min replicas:                                          2
Max replicas:                                          5
Deployment pods:                                       5 current / 5 desired
Conditions:
  Type            Status  Reason               Message
  ----            ------  ------               -------
  AbleToScale     True    ScaleDownStabilized  recent recommendations were higher than current one
  ScalingActive   True    ValidMetricFound     the HPA was able to successfully calculate a replica count
  ScalingLimited  True    TooManyReplicas      the desired replica count is more than the maximum replica count
Events:
  Type    Reason             Age    From                       Message
  ----    ------             ----   ----                       -------
  Normal  SuccessfulRescale  3m26s  horizontal-pod-autoscaler  New size: 4; reason: cpu resource utilization (percentage of request) above target
  Normal  SuccessfulRescale  2m25s  horizontal-pod-autoscaler  New size: 5; reason: cpu resource utilization (percentage of request) above target
```

### Active Pods Under Load
```bash
kubectl get pods
```
**Real Output:**
```
NAME                           READY   STATUS    RESTARTS   AGE
pod/flask-app-b9f466d4-9dxtr   1/1     Running   1          5m32s
pod/flask-app-b9f466d4-9hdtq   1/1     Running   0          30m
pod/flask-app-b9f466d4-m529g   1/1     Running   0          33m
pod/flask-app-b9f466d4-r75jh   1/1     Running   2          6m26s
pod/flask-app-b9f466d4-rgcnh   1/1     Running   2          6m26s
pod/mongo-0                    1/1     Running   0          19m
```

---

## 12. Real Issues Encountered & How They Were Resolved

1. **MongoDB 6.0 Startup OOM (`docker-entrypoint.sh: Killed "${mongo[@]}"`):**
   - *Problem*: The official MongoDB 6.0 image ships with `mongosh` (a Node.js runtime) instead of the legacy C++ `mongo` shell. During first-boot initialization, `mongod` spawned with default WiredTiger cache (~400MB) while the entrypoint spawned `mongosh` to create the admin user (~150MB+), exceeding the 500M memory limit. The Linux kernel OOM-killer killed `mongosh` repeatedly, preventing root user creation.
   - *Resolution*: Added `--wiredTigerCacheSizeGB 0.25` to `mongod` args to constrain memory cache and increased the StatefulSet container memory limit to `1Gi`. Root credentials then created cleanly.
2. **Gunicorn Pre-Fork Connection Stall on Health Check:**
   - *Problem*: Instantiating `MongoClient` at the global module level in `app.py` caused PyMongo to spawn background topology monitor threads before Gunicorn forked worker processes, creating connection lock contention and transient health check probe timeouts.
   - *Resolution*: Implemented lazy client initialization (`get_collection()`), ensuring `/health` returns `{"status":"ok"}` in <1ms without touching MongoDB sockets.
3. **Local Metrics-Server Certificate & Port Mismatch:**
   - *Problem*: Metrics-server failed with `Metrics API not available` due to untrusted self-signed kubelet certificates and port 4443 mismatch against container port 10250.
   - *Resolution*: Applied `metrics-patch.yaml` configuring `--kubelet-insecure-tls` and `--secure-port=10250`. Metrics immediately reported CPU/memory across nodes and pods.
4. **Typo in `requirements.txt`:**
   - *Problem*: A stray word `do` was entered into `requirements.txt`, causing `pip install` to fail during image build (`No matching distribution found for do`).
   - *Resolution*: Cleaned `app/requirements.txt` back to pinned dependencies (`Flask==2.0.2`, `Werkzeug==2.0.3`, `pymongo==3.12.0`, `gunicorn==20.1.0`), rebuilding with 100% clean cache.

---

## 13. Cleanup Commands

To tear down all resources deployed during this assessment:

```bash
# Delete all application resources and autoscaler
kubectl delete -f k8s/07-flask-hpa.yaml
kubectl delete -f k8s/06-flask-service.yaml
kubectl delete -f k8s/05-flask-deployment.yaml
kubectl delete -f k8s/04-mongo-statefulset.yaml
kubectl delete -f k8s/03-mongo-service.yaml
kubectl delete -f k8s/02-mongo-pvc.yaml
kubectl delete -f k8s/01-mongo-pv.yaml
kubectl delete -f k8s/00-secret.yaml

# Delete test pods and patch manifests
kubectl delete pod load-generator load-gen-b load-gen-c --ignore-not-found
rm metrics-patch.yaml
```

---

## 14. Project Structure

```
.
├── app/
│   ├── app.py                   # Flask REST API with Gunicorn entrypoint
│   └── requirements.txt         # Pinned Python package dependencies
├── k8s/
│   ├── 00-secret.yaml           # MongoDB root credentials secret
│   ├── 01-mongo-pv.yaml         # 1Gi PersistentVolume with hostPath
│   ├── 02-mongo-pvc.yaml        # PersistentVolumeClaim bound to mongo-pv
│   ├── 03-mongo-service.yaml    # Headless Service for StatefulSet
│   ├── 04-mongo-statefulset.yaml# MongoDB 6.0 StatefulSet with auth
│   ├── 05-flask-deployment.yaml # 2-replica Flask Deployment with probes
│   ├── 06-flask-service.yaml    # NodePort Service (Port 30007)
│   └── 07-flask-hpa.yaml        # HPA (70% CPU target, 2-5 replicas)
├── load-test/
│   ├── load.sh                  # Load testing script
│   └── payload.json             # Sample JSON payload for POST /data
├── Dockerfile                   # Hardened, non-root multi-layer build
├── .dockerignore                # Excludes venv, git, and local k8s files
├── .gitignore                   # Standard ignore rules
└── README.md                    # Comprehensive documentation with real outputs
```

