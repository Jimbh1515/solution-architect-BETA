# 05 Multi-Cloud Diagrams: Spec Format and Renderer

Purpose: how to turn the recommended architecture into four diagrams (provider-neutral, AWS, Azure, Google Cloud), each as an editable draw.io page and a PNG with official icons.

## 1. Commands

Run from the workspace root. Always use these exact commands; do not write diagram XML by hand.

```bash
# show every component kind and the service it becomes on each cloud
python .agents/skills/sa-proposal/scripts/render_multicloud.py --list-kinds

# render all four views
python .agents/skills/sa-proposal/scripts/render_multicloud.py proposals/<slug>/spec.json --out proposals/<slug>/diagrams

# wide designs read better left to right
python .agents/skills/sa-proposal/scripts/render_multicloud.py proposals/<slug>/spec.json --out proposals/<slug>/diagrams --rankdir LR
```

Outputs in `--out`:

| File | What it is |
|---|---|
| `generic.png`, `aws.png`, `azure.png`, `gcp.png` | Preview images with official icons (Python `diagrams` package icon set) |
| `generic.drawio`, `aws.drawio`, `azure.drawio`, `gcp.drawio` | Editable draw.io files using draw.io's built-in AWS, Azure, Google Cloud, Kubernetes and network icon libraries |
| `multicloud.drawio` | All four views as pages in one draw.io file |
| `service_mapping.md` | Table: each component and the service used on each cloud |
| `render_report.md` | Service names flagged "(v)" for verification, plus standing checks |
| `*.dot` | Graphviz source (for troubleshooting only) |

If the script stops with "spec is invalid", fix every listed problem in `spec.json` and run it again. If it reports that Graphviz or the `diagrams` package is missing, tell the user and point them to the README setup steps; do not try to work around it by hand-drawing.

After rendering, open each PNG and check it before writing Section 5. Look for: every component present, labels readable, the provider zone titled with the right cloud, and boundary-crossing flows labelled with their data class.

## 2. Spec format (`spec.json`)

```json
{
  "title": "Short diagram title",
  "containers": [
    {"id": "env", "label": "Agency environment", "type": "environment"},
    {"id": "serving", "label": "Serving subsystem", "type": "subsystem", "parent": "env"},
    {"id": "k8s", "label": "Self-managed Kubernetes cluster", "type": "platform", "parent": "serving"},
    {"id": "cloud", "label": "Hyperscaler", "type": "provider_zone", "zone_suffix": "managed model only"}
  ],
  "components": [
    {"id": "users", "kind": "users", "label": "Application users", "placement": "external"},
    {"id": "inf", "kind": "model_serving", "label": "Inference server", "placement": "onprem", "container": "k8s", "tech": "vLLM, open-weight model"},
    {"id": "llm", "kind": "managed_llm", "label": "Managed model", "placement": "cloud", "container": "cloud"}
  ],
  "flows": [
    {"id": "e1", "from": "users", "to": "inf", "label": "Request", "type": "request"},
    {"id": "e2", "from": "inf", "to": "llm", "label": "Hybrid API call", "type": "data", "crosses_boundary": true, "data_class": "approved data only"}
  ]
}
```

Field reference:

| Object | Field | Required | Values / meaning |
|---|---|---|---|
| container | `id`, `label` | yes | Unique ID; display title |
| container | `type` | yes | `environment`, `subsystem`, `platform`, `provider_zone`, `onprem_site` |
| container | `parent` | no | ID of the enclosing container |
| container | `zone_suffix` | no | Provider zones only: text appended to the cloud name (e.g. "managed model only") |
| component | `id`, `label` | yes | Unique ID; short display name |
| component | `kind` | yes | One of the kinds below |
| component | `placement` | yes | `cloud`, `onprem`, `sovereign`, `external` |
| component | `container` | no | ID of the box it sits in; omit for components outside all boxes |
| component | `tech` | no | Example technology, shown for on-premises, sovereign and external components |
| component | `service_override` | no | e.g. `{"aws": "Amazon Aurora PostgreSQL"}` to change the service name shown on one cloud |
| flow | `id`, `from`, `to` | yes | Component IDs |
| flow | `type` | no | `request` (default), `data`, `telemetry` |
| flow | `label` | no | Short text on the arrow |
| flow | `crosses_boundary`, `data_class` | when crossing | Both required when data crosses a provider or national boundary |

## 3. Component kinds

Service names marked "(v)" are ones the builder was less certain are current; they appear in `render_report.md` and must go into Section 9 of the package. None of these names guarantees availability in a Malaysian region.

| Kind | Use for | AWS | Azure | Google Cloud | Generic (on-premises / sovereign) |
|---|---|---|---|---|---|
| `users` | People who use the system | Users | Users | Users | Users |
| `external_source` | Data source outside the client (other agencies, public data, partners) | External source | External source | External source | External source |
| `internal_source` | Existing client system or data store feeding the solution | Internal source | Internal source | Internal source | Internal source |
| `identity` | Identity provider and single sign-on | AWS IAM Identity Center / Amazon Cognito | Microsoft Entra ID | Cloud Identity / Identity Platform | Agency identity provider (e.g. Keycloak) |
| `api_gateway` | API gateway / API management | Amazon API Gateway | Azure API Management | Apigee | API gateway (e.g. Kong) |
| `waf` | Web application firewall and DDoS protection | AWS WAF | Azure Front Door with WAF | Cloud Armor | Web application firewall |
| `load_balancer` | Load balancer | Elastic Load Balancing | Azure Application Gateway | Cloud Load Balancing | Load balancer (e.g. HAProxy) |
| `k8s` | Kubernetes cluster | Amazon EKS | Azure Kubernetes Service (AKS) | Google Kubernetes Engine (GKE) | Kubernetes (e.g. OpenShift, Rancher) |
| `serverless_container` | Serverless container runtime | AWS Fargate | Azure Container Apps | Cloud Run | Container runtime (e.g. Knative) |
| `functions` | Event-driven functions | AWS Lambda | Azure Functions | Cloud Run functions (v) | Functions runtime (e.g. OpenFaaS) |
| `vm` | Virtual machines | Amazon EC2 | Azure Virtual Machines | Compute Engine | Virtual machines (e.g. VMware, KVM) |
| `workload` | Application component running on a platform (front end, API, agent service) | Containerised service | Containerised service | Containerised service | Containerised service |
| `managed_llm` | Managed foundation model service | Amazon Bedrock | Azure OpenAI in Azure AI Foundry (v) | Gemini via Vertex AI | Self-hosted open-weight model |
| `ml_platform` | Machine learning platform | Amazon SageMaker AI | Azure Machine Learning | Vertex AI | ML platform (e.g. MLflow, Kubeflow) |
| `model_serving` | Self-managed model inference server | Model serving on Amazon EKS / SageMaker endpoints | Model serving on AKS / Azure ML endpoints | Model serving on GKE / Vertex AI endpoints | Inference server (e.g. vLLM, Hugging Face TGI) |
| `responsible_ai` | Prompt and response screening / content safety | Amazon Bedrock Guardrails | Azure AI Content Safety | Model Armor (v) | Responsible AI service (e.g. guardrail models) |
| `batch_job` | Batch or data-processing job (e.g. embedding generation) | AWS Batch | Azure Batch | Cloud Run jobs / Batch (v) | Batch job (e.g. Ray) |
| `object_storage` | Object storage / data lake | Amazon S3 | Azure Blob Storage | Cloud Storage | Object storage (e.g. MinIO, Ceph) |
| `file_storage` | Shared file storage | Amazon EFS | Azure Files | Filestore | NFS storage |
| `relational_db` | Relational database | Amazon RDS / Aurora | Azure Database for PostgreSQL | Cloud SQL | PostgreSQL |
| `vector_db` | Vector store for embeddings | Aurora PostgreSQL with pgvector | Azure Database for PostgreSQL with pgvector | AlloyDB with pgvector | PostgreSQL with pgvector |
| `nosql_db` | NoSQL / document database | Amazon DynamoDB | Azure Cosmos DB | Firestore | Document database (e.g. MongoDB) |
| `cache` | In-memory cache | Amazon ElastiCache | Azure Managed Redis (v) | Memorystore | Cache (e.g. Redis, Valkey) |
| `search` | Search / retrieval service | Amazon OpenSearch Service | Azure AI Search | Vertex AI Search | Search engine (e.g. OpenSearch) |
| `data_warehouse` | Data warehouse / lakehouse | Amazon Redshift | Azure Synapse Analytics / Microsoft Fabric (v) | BigQuery | Lakehouse (e.g. Trino with Iceberg) |
| `streaming` | Event streaming / messaging | Amazon Kinesis / MSK | Azure Event Hubs | Pub/Sub | Event streaming (e.g. Kafka) |
| `etl` | Data integration / pipelines | AWS Glue | Azure Data Factory | Dataflow | Pipelines (e.g. Airflow, Spark) |
| `data_catalog` | Data catalogue and governance | AWS Lake Formation / Amazon DataZone (v) | Microsoft Purview | Dataplex Universal Catalog (v) | Data catalogue (e.g. OpenMetadata) |
| `logging` | Centralised logging | Amazon CloudWatch Logs | Azure Monitor Log Analytics | Cloud Logging | Logging (e.g. OpenSearch, Loki) |
| `monitoring` | Metrics and monitoring | Amazon CloudWatch | Azure Monitor | Cloud Monitoring | Monitoring (e.g. Prometheus, Grafana) |
| `analytics_bi` | Dashboards / business intelligence | Amazon QuickSight / Quick Suite (v) | Power BI (v) | Looker | Dashboards (e.g. Grafana, Superset) |
| `kms` | Key management and secrets | AWS KMS / Secrets Manager | Azure Key Vault | Cloud KMS / Secret Manager | Key management / HSM (e.g. Vault) |
| `vpc` | Virtual network | Amazon VPC | Azure Virtual Network | VPC network | Private network |
| `interconnect` | Dedicated private link between on-premises and cloud | AWS Direct Connect | Azure ExpressRoute | Cloud Interconnect | Private circuit / cross-connect |
| `vpn` | Site-to-site VPN | AWS Site-to-Site VPN | Azure VPN Gateway | Cloud VPN | VPN |

## 4. Choosing between the three cloud views

The three cloud pages show the *same recommended design* on each provider, for comparison. They do not replace the options analysis in Section 4: if the recommendation is the Malaysian sovereign option or a hybrid, the cloud pages show only the parts placed in the cloud on each provider. Say this in Section 5.

## 5. Icon provenance and terms

- draw.io styles were copied verbatim from draw.io's own sidebar definitions (commit recorded in `icon_map.json`), and every icon was test-rendered in draw.io's own engine before release.
- PNG icons come from the open-source Python `diagrams` package.
- AWS, Microsoft and Google publish usage terms for their architecture icons. Using them in architecture diagrams is their intended purpose, but check each provider's current icon terms before publishing diagrams outside a proposal.
