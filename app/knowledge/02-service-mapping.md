# 02 Cross-Provider Service Mapping

Purpose: select comparable services across providers, apply consistent selection logic, and review designs against well-architected pillars. Consolidated from the AWS, Azure, Google Cloud, Oracle AI, senior cloud architect, senior solution architect and CTO advisor skills.

**Read this first.** Providers rename, merge and retire services frequently. The names below reflect the builder's knowledge as of mid-2026 and have not been re-checked against current provider documentation. Any name marked (v) is one the builder is less certain is current. When a proposal depends on a specific service, mark it "verify current name or availability". Never assume a service is available in a Malaysian region.

## 1. Service equivalence table

Columns "Sovereign / local" and "On-premises / private" describe the capability required or common open-source and commercial options, not specific vendors. Open-source licensing terms change; verify licences before proposing.

### Compute

| Capability | AWS | Azure | Google Cloud | Oracle (OCI) | Sovereign / local | On-premises / private |
|---|---|---|---|---|---|---|
| Virtual machines | EC2 | Virtual Machines, VM Scale Sets | Compute Engine | Compute | IaaS VMs in a Malaysian facility | VMware, KVM, OpenStack |
| Managed Kubernetes | EKS | AKS | GKE (Autopilot, Standard) | Container Engine for Kubernetes (OKE) | Managed Kubernetes | Red Hat OpenShift, Rancher, upstream Kubernetes |
| Serverless containers | ECS on Fargate, App Runner (v) | Container Apps | Cloud Run | Container Instances | Varies; often unavailable | Knative on Kubernetes |
| Functions | Lambda | Functions | Cloud Run functions (formerly Cloud Functions) (v) | Functions | Varies | Knative, OpenFaaS |
| Batch and HPC | AWS Batch, ParallelCluster | Batch, CycleCloud (v) | Batch | HPC shapes, cluster networking (v) | HPC capacity in-country | Slurm |
| GPU for AI | EC2 GPU instances | GPU VM series | GPU VMs, TPUs (Google only) | GPU bare metal and VM shapes | In-country GPU capacity (key differentiator to check) | On-premises GPU servers |
| Hybrid / provider hardware on-site | Outposts (v) | Azure Local (formerly Azure Stack HCI) (v) | Google Distributed Cloud, incl. air-gapped (v) | Cloud@Customer, Dedicated Region (v) | — | — |

### Storage and databases

| Capability | AWS | Azure | Google Cloud | Oracle (OCI) | Sovereign / local | On-premises / private |
|---|---|---|---|---|---|---|
| Object storage | S3 | Blob Storage | Cloud Storage | Object Storage | S3-compatible object storage | MinIO, Ceph |
| File storage | EFS, FSx | Azure Files, NetApp Files | Filestore | File Storage | NFS service | NFS, Ceph |
| Relational (managed) | RDS, Aurora | Azure SQL Database, Database for PostgreSQL / MySQL Flexible Server | Cloud SQL, AlloyDB | Autonomous Database, MySQL HeatWave | Managed PostgreSQL / MySQL | PostgreSQL, MySQL, Oracle Database |
| Globally distributed SQL | Aurora DSQL (v) | Cosmos DB for PostgreSQL (v) | Spanner | Globally distributed Autonomous Database (v) | Rare | CockroachDB, YugabyteDB |
| NoSQL / document / wide-column | DynamoDB, DocumentDB | Cosmos DB | Firestore, Bigtable | NoSQL Database | Varies | MongoDB, Cassandra |
| Cache | ElastiCache | Azure Cache for Redis / Azure Managed Redis (v) | Memorystore | OCI Cache (v) | Managed cache | Redis, Valkey |
| Data warehouse / lakehouse | Redshift, Athena, Lake Formation | Microsoft Fabric, Synapse Analytics | BigQuery, BigLake | Autonomous Data Warehouse, AI Data Platform (v) | Varies | Trino, ClickHouse, Spark with Iceberg or Delta |
| Vector search | OpenSearch, Aurora / RDS with pgvector, S3 Vectors (v) | AI Search, Cosmos DB vector, Azure SQL vector (v) | Vertex AI Vector Search, AlloyDB / Cloud SQL with pgvector | Oracle Database AI Vector Search (23ai / 26ai) (v) | PostgreSQL with pgvector | pgvector, Milvus, Qdrant |

### Data integration and governance

| Capability | AWS | Azure | Google Cloud | Oracle (OCI) | Sovereign / local | On-premises / private |
|---|---|---|---|---|---|---|
| Streaming / messaging | Kinesis, MSK, SQS, SNS, EventBridge | Event Hubs, Service Bus, Event Grid | Pub/Sub | Streaming, Queue (v) | Managed Kafka | Apache Kafka, RabbitMQ |
| ETL / data pipelines | Glue, Step Functions | Data Factory, Fabric Data Factory | Dataflow, Dataproc, Cloud Composer | Data Integration, Data Flow, GoldenGate | Varies | Apache Airflow, Spark, NiFi |
| Data catalogue and governance | Glue Data Catalog, Lake Formation, DataZone (v) | Microsoft Purview | Dataplex | Data Catalog (v) | Varies | OpenMetadata, DataHub |

### AI

| Capability | AWS | Azure | Google Cloud | Oracle (OCI) | Sovereign / local | On-premises / private |
|---|---|---|---|---|---|---|
| ML platform | SageMaker AI | Azure Machine Learning | Vertex AI | Data Science | Varies | MLflow, Kubeflow, Ray |
| Managed foundation models | Bedrock | Azure OpenAI / models in Azure AI Foundry (v) | Gemini and Model Garden via Vertex AI | Generative AI service | In-country model hosting (check) | Self-hosted open-weight models |
| Agent building | Bedrock Agents, AgentCore (v) | Azure AI Foundry Agent Service (v) | Vertex AI Agent Builder / Agent Engine (v) | Generative AI Agents (v) | Varies | LangGraph, open-source agent frameworks |
| Enterprise search / RAG | Kendra, Bedrock Knowledge Bases | Azure AI Search | Vertex AI Search | Generative AI Agents with RAG (v) | Varies | OpenSearch, Elasticsearch |
| Model serving (self-managed) | SageMaker endpoints, EKS | Azure ML endpoints, AKS | Vertex AI endpoints, GKE | Data Science deployments, NVIDIA NIM on OCI (v) | GPU Kubernetes | vLLM, Hugging Face TGI, NVIDIA NIM, Triton |
| Natural language to SQL | Varies (v) | Varies (v) | Varies (v) | Select AI in Autonomous Database (v) | — | Open-source text-to-SQL |

### Networking

| Capability | AWS | Azure | Google Cloud | Oracle (OCI) | Sovereign / local | On-premises / private |
|---|---|---|---|---|---|---|
| Virtual network | VPC (regional) | VNet (regional) | VPC (global) | VCN | Tenant network | VLANs, SDN |
| Private access to managed services | PrivateLink, VPC endpoints | Private Endpoint / Private Link | Private Service Connect | Private endpoints, Service Gateway | Private interconnect | — |
| Dedicated link to on-premises | Direct Connect | ExpressRoute | Cloud Interconnect | FastConnect | Direct cross-connect in data centre | — |
| Site-to-site VPN | Site-to-Site VPN | VPN Gateway | Cloud VPN | Site-to-Site VPN | VPN | VPN appliances |
| Edge, load balancing, WAF | CloudFront, ALB / NLB, AWS WAF, Shield | Front Door, Application Gateway, Azure WAF, DDoS Protection | Cloud Load Balancing, Cloud CDN, Cloud Armor | Load Balancer, WAF | Local CDN / WAF | F5, NGINX, HAProxy |
| API management | API Gateway | API Management | Apigee, API Gateway | API Gateway | Varies | Kong, open-source gateways |
| Hub-and-spoke / transit | Transit Gateway, Cloud WAN | Hub-and-spoke VNets, Virtual WAN | Network Connectivity Center, Shared VPC | Dynamic Routing Gateway | — | — |

### Identity, security and operations

| Capability | AWS | Azure | Google Cloud | Oracle (OCI) | Sovereign / local | On-premises / private |
|---|---|---|---|---|---|---|
| Workforce identity / SSO | IAM Identity Center | Microsoft Entra ID | Cloud Identity | IAM Identity Domains | Integrate with agency IdP | Keycloak, Active Directory |
| Citizen / customer identity | Cognito | Entra External ID (v) | Identity Platform | IAM Identity Domains (v) | National digital identity integration (layer 3) | Keycloak |
| Workload identity (no keys) | IAM roles, IRSA / EKS Pod Identity | Managed Identity, AKS Workload Identity | Service accounts, Workload Identity Federation | Instance principals, dynamic groups | Varies | SPIFFE / SPIRE |
| Keys and secrets | KMS, CloudHSM, Secrets Manager | Key Vault, Managed HSM | Cloud KMS, Cloud HSM, Secret Manager | Vault | In-country KMS / HSM | HashiCorp Vault (check licence), HSMs |
| Security posture and threat detection | Security Hub, GuardDuty | Defender for Cloud, Microsoft Sentinel | Security Command Center, Google Security Operations | Cloud Guard | Local SOC | SIEM (e.g. Wazuh, Splunk) |
| Observability | CloudWatch, X-Ray | Azure Monitor, Application Insights, Log Analytics | Cloud Monitoring, Cloud Logging, Cloud Trace | Monitoring, Logging, APM | Varies | Prometheus, Grafana, OpenTelemetry, OpenSearch |
| Infrastructure as code | CloudFormation, CDK, Terraform | Bicep, ARM, Terraform | Terraform, Infrastructure Manager | Resource Manager (Terraform) | Terraform | Terraform / OpenTofu, Ansible |
| Landing zone and governance | Organizations, Control Tower, SCPs | Management groups, Azure Policy, Azure landing zones | Resource hierarchy, Organization Policy | Compartments, tenancy policies, landing zone | Varies | — |

## 2. Selection logic (provider-neutral)

### Compute

```
Stateless HTTP / API service?
├── Containerised, want minimal operations, can scale to zero → serverless containers
├── Event-driven, short-running → functions
├── Need full control (sidecars, custom runtimes, GPUs, many services) → managed Kubernetes
└── Legacy or stateful application → virtual machines
Batch or data processing?
├── Finite container jobs → serverless jobs or batch service
└── Large data transforms → managed Spark / Beam
AI inference?
├── Managed model is acceptable (data may leave the tenancy boundary to the provider's model service) → managed foundation models
├── Data or model must stay in a controlled environment → self-hosted serving on GPU Kubernetes
└── Batch inference → batch prediction service or Kubernetes jobs
```

### Data stores

```
Relational, OLTP → managed PostgreSQL / MySQL / SQL Server; global strong consistency → distributed SQL
Document or key-value at scale → managed NoSQL
Cache → managed Redis-compatible cache
Files, images, documents, data lake → object storage, tiered by access frequency
Analytics → data warehouse or lakehouse
Vectors → co-locate with an existing database (pgvector, database vector types) unless scale or latency needs a dedicated vector store
```

### Identity

- Workloads calling cloud services: use workload identity (managed identities, service identities, instance principals). Avoid long-lived keys.
- External systems and CI/CD: federation (OIDC) over static keys.
- Users: integrate with the agency's existing identity provider via OIDC or SAML. Public-facing services: consider national digital identity integration (layer 3).
- Grant least privilege at the narrowest scope. Avoid broad built-in roles such as owner or editor in production.

### Networking defaults for government workloads

- No public endpoints on databases, caches or storage. Use private endpoints / private service access.
- Hub-and-spoke with central egress inspection for multi-workload or multi-agency estates.
- WAF and DDoS protection on every public entry point.
- Dedicated interconnect for steady, high-volume hybrid traffic; VPN for low volume or as backup.

### Hybrid AI pattern (as in the reference diagram)

Self-hosted inference and sensitive data stay in a controlled cluster (on-premises or sovereign facility), while selected requests go to a hyperscaler's managed model through a gated "hybrid API call". Required elements: an identity provider and API gateway at the entry point; a responsible AI service screening prompts and responses; an ingestion pipeline (shard and chunk, create embeddings, store in a vector-capable database); logging, monitoring and analytics; and an explicit statement of which data may cross to the hyperscaler.

## 3. Well-architected review pillars

AWS, Azure and Google Cloud each publish a well-architected framework; the pillar names differ slightly between them (verify current pillar lists). Use these six combined pillars for every review:

| Pillar | Questions to answer in every proposal |
|---|---|
| Operational excellence | Is everything deployed as code? Are there separate environments? Are there SLO-based alerts and runbooks? |
| Security, privacy and compliance | Least-privilege identity? No public data endpoints? Encryption at rest and in transit with customer-managed keys where required? Data residency met? Audit logging? |
| Reliability | Multi-zone for production? Tested backups? Stated RTO and RPO, and a disaster recovery design that meets them? |
| Performance efficiency | Right compute type for the workload? Autoscaling? Caching where reads dominate? |
| Cost optimisation | Right-sized? Commitment discounts considered? Non-production shut down out of hours? Storage tiering? Egress minimised? |
| Sustainability | Utilisation high? Region or facility energy profile considered (links to layer 1)? |

Common findings to check for: single-zone production databases; backups never restored in a test; long-lived keys in code; broad owner or editor roles; storage buckets open to the public; click-ops changes in production; no staging environment; no cost alerts.

## 4. Cost driver catalogue

Use this list to populate the cost driver table (file 04). Do not attach prices.

| Category | Typical drivers and units |
|---|---|
| Compute | vCPU-hours, memory GB-hours, node count, instance hours by environment |
| GPU | GPU type, GPU-hours, reserved versus on-demand capacity |
| Serverless | requests per month, execution duration, memory size |
| Managed models | input and output tokens per month, provisioned throughput units |
| Storage | GB-months by tier, snapshots, backup retention |
| Databases | instance size and hours, storage, I/O, replicas, high availability |
| Data movement | egress GB to the internet and between regions or providers, interconnect ports and hours |
| Networking | load balancers, NAT gateways, WAF rules and requests, private endpoints |
| Observability | log ingestion GB, retention days, metrics, traces |
| Security | key operations, HSMs, threat detection by resource count |
| Licences | database, operating system, Kubernetes platform, third-party software |
| Support | provider support tier |
| Services | design, build, migration, managed operations, training (person-days) |

Main cost levers to mention in the narrative: right-sizing, commitment discounts (reserved capacity, savings plans, committed-use discounts), autoscaling and scale-to-zero, spot or pre-emptible capacity for interruptible work, storage tiering, reducing egress, and log retention policies.
