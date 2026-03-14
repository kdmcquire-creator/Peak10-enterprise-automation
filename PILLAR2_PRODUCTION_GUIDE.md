# Pillar 2 — Executive Communications Intelligence
## Full Production Build Guide

**Scope**: Take the email intelligence system from business logic prototype to production, including merging document classification and SharePoint filing (formerly Pillar 3) into the email pipeline.

**End State**: Emails arrive in your Outlook inbox → automatically triaged by urgency and category → attachments classified and filed to governed SharePoint folders → invoices routed to Pillar 1 AP queue → receipts routed to Pillar 4 expense hub → AI-drafted replies queued for your review → all decisions logged and learnable.

---

## Table of Contents

1. [Pre-Flight: What You Need Before We Start](#pre-flight)
2. [Layer 1: Database — Cosmos DB Persistence](#layer-1)
3. [Layer 2: Azure OpenAI — Real AI Classification & Drafting](#layer-2)
4. [Layer 3: Microsoft Graph — Outlook Email Ingestion](#layer-3)
5. [Layer 4: Azure Document Intelligence — Text Extraction](#layer-4)
6. [Layer 5: Classification & Filing Merge from Pillar 3](#layer-5)
7. [Layer 6: Microsoft Graph — SharePoint File Operations](#layer-6)
8. [Layer 7: Draft Response Review Flow](#layer-7)
9. [Layer 8: Production Hardening](#layer-8)
10. [Validation Checklist](#validation)

---

<a name="pre-flight"></a>
## Pre-Flight: What You Need Before We Start

### Licenses & Subscriptions

| Requirement | Status | Action If Missing |
|---|---|---|
| **Azure Subscription** (Owner/Contributor) | Required | https://portal.azure.com |
| **Microsoft 365 Business Premium** | Required | Includes Outlook, SharePoint, Graph API access |
| **Azure OpenAI access** | Required | Check: Azure Portal → search "Azure OpenAI" → if "Request Access" appears, submit https://aka.ms/oai/access (1-5 business day wait) |
| **GitHub repo access** | Required | Admin on `kdmcquire-creator/Peak10-enterprise-automation` |

**Total Azure cost for this pillar (dev):** ~$30-80/mo depending on email volume.

| Service | Dev Cost | What It Does |
|---|---|---|
| Azure Function App (Consumption) | Free | Runs the email pipeline |
| Azure Cosmos DB (Serverless) | ~$5-15/mo | Stores triage results, documents, corrections |
| Azure OpenAI (GPT-4o) | ~$5-50/mo | Email triage, document classification, draft replies |
| Azure AI Document Intelligence | ~$1-10/mo | Extracts text from PDF/image attachments |
| Storage Account | ~$1/mo | Blob staging for attachments |
| Key Vault | ~$0.50/mo | Secrets management |
| Application Insights | Free | Monitoring (5GB/mo included) |

### Permissions Required

You need these roles on your accounts. If IT manages your tenant, send them this table.

| Permission | Platform | How to Check | Why |
|---|---|---|---|
| **Owner** or **Contributor** | Azure Subscription | Portal → Subscriptions → Access control (IAM) | Deploy all Azure resources |
| **Application Administrator** | Microsoft Entra ID | Portal → Entra ID → Roles and administrators | Create app registration for Graph API |
| **SharePoint Administrator** | M365 Admin Center | Admin Center → Roles | Grant Graph API permission to read/write SharePoint |
| **Exchange Administrator** | M365 Admin Center | Admin Center → Roles | Grant Graph API permission to read mailbox |
| **Power Platform Environment Maker** | Power Platform Admin Center | Admin Center → Environments | Only if using Power Automate (optional — we can use Graph webhooks instead) |
| **GitHub Repository Admin** | GitHub | Repo → Settings → Collaborators | Set repository secrets |

### Software to Install Locally

| Tool | Install | Verify |
|---|---|---|
| **Azure CLI 2.50+** | macOS: `brew install azure-cli` · Windows: `winget install Microsoft.AzureCLI` | `az --version` |
| **Azure Functions Core Tools v4** | macOS: `brew install azure-functions-core-tools@4` · Windows: `winget install Microsoft.Azure.FunctionsCoreTools` | `func --version` |
| **PowerShell 7+** | macOS: `brew install powershell` · Windows: built-in (`pwsh`) | `pwsh --version` |
| **PnP.PowerShell** | In PowerShell: `Install-Module PnP.PowerShell -Scope CurrentUser` | `Get-Module PnP.PowerShell -ListAvailable` |

**Shortcut**: Use Azure Cloud Shell (https://shell.azure.com) — has Azure CLI, PowerShell 7, and Python pre-installed. Only need `Install-Module PnP.PowerShell`.

### Pre-Flight Checklist

Run through this before we begin. Every box must be checked.

- [ ] Azure subscription active, you can log into https://portal.azure.com
- [ ] You have Owner or Contributor on the subscription
- [ ] Azure OpenAI access confirmed (you can see a "Create" button, not "Request Access")
- [ ] M365 tenant active with Outlook and SharePoint
- [ ] Azure CLI installed (`az --version` → 2.50+)
- [ ] Functions Core Tools installed (`func --version` → 4.x)
- [ ] PowerShell 7 + PnP.PowerShell installed
- [ ] GitHub repo admin access confirmed
- [ ] You know your SharePoint site URL (e.g., `https://peak10energy.sharepoint.com/sites/Operations`)
- [ ] You know which Outlook mailbox to monitor (e.g., `kmcquire@peak10energy.com`)

**Once all checked, tell Claude "Pre-flight complete" and provide:**
```
SharePoint Site URL:    ___________________________
Mailbox to monitor:     ___________________________
Azure Subscription ID:  ___________________________
```

---

<a name="layer-1"></a>
## Layer 1: Database — Cosmos DB Persistence

**Goal**: Replace all in-memory `dict` stores with durable Cosmos DB persistence so nothing is lost on Function App restart.

### Your Work (5 minutes)

Nothing. Claude handles this layer entirely.

### Claude's Work

| Task | Details |
|---|---|
| Add Cosmos DB to Bicep template | Serverless capacity mode, 3 containers: `emails`, `documents`, `corrections` |
| Build data access layer | Python SDK with async operations, connection via Key Vault reference |
| Migrate all in-memory stores | Replace `_document_store`, `_correction_store`, triage results with Cosmos operations |
| Partition key design | `emails` by message_id, `documents` by document_id, `corrections` by month |
| Add TTL policy | Auto-expire noise/spam triage results after 30 days |
| Write integration tests | Verify CRUD operations against Cosmos DB emulator |

### Deliverable

All API endpoints persist data to Cosmos DB. Function App restarts lose nothing.

---

<a name="layer-2"></a>
## Layer 2: Azure OpenAI — Real AI Classification & Drafting

**Goal**: Replace the pass-through `ai_response` parameter with actual Azure OpenAI SDK calls.

### Your Work (15 minutes)

1. **Deploy a GPT-4o model in Azure OpenAI**:
   - Azure Portal → your Azure OpenAI resource (deployed in prior Bicep step) → **Model deployments → Deploy model**
   - Select **gpt-4o**
   - Deployment name: **`gpt-4o-triage`** (remember this exact name)
   - Tokens per minute rate limit: **30K** (sufficient for email + document classification)
   - Click **Deploy**

2. **Store the API key in Key Vault**:
   - Azure Portal → your Azure OpenAI resource → **Keys and Endpoint**
   - Copy **Key 1** and the **Endpoint URL**
   - Azure Portal → your Key Vault → **Secrets → Generate/Import**
   - Create secret: Name = `azure-openai-key`, Value = Key 1
   - Click **Create**

3. **Give Claude these values**:
   ```
   OpenAI Endpoint:        ___________________________
   OpenAI Deployment Name: gpt-4o-triage
   ```

### Claude's Work

| Task | Details |
|---|---|
| Add `openai` SDK to requirements | `openai>=1.0` with Azure configuration |
| Build OpenAI client wrapper | Async client, Key Vault credential retrieval, retry with exponential backoff (3 attempts) |
| Wire triage pipeline | Rule-based first → if confidence < 0.85, call GPT-4o → merge results |
| Wire document classification | Same two-tier: rules first, AI fallback |
| Build draft reply generator | Prompt engineering for professional, brief, and warm tones |
| Add token budgeting | Cap input to 2000 tokens, track usage per request, log costs |
| Add content filtering | Validate OpenAI responses, reject hallucinated categories |
| Write tests | Mock OpenAI responses, verify fallback behavior, test cost tracking |

### Deliverable

Email triage and document classification call GPT-4o when rules aren't confident enough. Draft replies are generated automatically. All AI calls have retry logic and cost tracking.

---

<a name="layer-3"></a>
## Layer 3: Microsoft Graph — Outlook Email Ingestion

**Goal**: Automatically pull new emails from your Outlook inbox into the triage pipeline.

### Your Work (20 minutes)

1. **Create an App Registration for Graph API**:
   - Azure Portal → **Microsoft Entra ID → App registrations → New registration**
   - Name: **`peak10-email-pipeline`**
   - Supported account types: **Single tenant**
   - Redirect URI: Leave blank
   - Click **Register**
   - Copy and save:
     ```
     Application (client) ID:  ___________________________
     Directory (tenant) ID:    ___________________________
     ```

2. **Create a client secret**:
   - Go to **Certificates & secrets → New client secret**
   - Description: `graph-api`
   - Expires: **24 months**
   - Click **Add**
   - **Immediately copy the Value**:
     ```
     Client secret:            ___________________________
     ```

3. **Grant API permissions**:
   - Go to **API permissions → Add a permission → Microsoft Graph → Application permissions**
   - Add these permissions:
     - `Mail.Read` — Read emails from the monitored mailbox
     - `Mail.ReadWrite` — Move emails, mark as read
     - `Mail.Send` — Send approved draft replies
     - `Files.ReadWrite.All` — Upload/move files in SharePoint (used in Layer 6)
     - `Sites.ReadWrite.All` — Create folders, manage SharePoint metadata (used in Layer 6)
   - Click **Add permissions**
   - Click **Grant admin consent for [your tenant]** (requires Admin role)
   - Verify all permissions show green checkmarks under "Status"

4. **Store credentials in Key Vault**:
   - Azure Portal → your Key Vault → Secrets → create these:
     - `graph-client-id` → Value: Application (client) ID
     - `graph-client-secret` → Value: Client secret
     - `graph-tenant-id` → Value: Directory (tenant) ID
     - `graph-mailbox-address` → Value: The email address to monitor (e.g., `kmcquire@peak10energy.com`)

5. **Give Claude confirmation**:
   ```
   App Registration created: yes
   Admin consent granted:    yes
   Key Vault secrets stored: graph-client-id, graph-client-secret, graph-tenant-id, graph-mailbox-address
   ```

### Claude's Work

| Task | Details |
|---|---|
| Add `msgraph-sdk` to requirements | Microsoft Graph Python SDK |
| Build Graph auth client | Client credentials flow using Key Vault secrets |
| Build email ingestion service | Poll mailbox every 60 seconds (configurable), fetch new unread messages with attachments |
| Build attachment downloader | Download attachments to blob staging container |
| Wire into triage pipeline | New email → rule-based triage → AI triage if needed → persist to Cosmos DB |
| Build subscription webhook (upgrade) | Replace polling with Graph change notifications for near-real-time (webhook endpoint on the Function App) |
| Handle pagination | Large mailboxes, batch processing, delta queries |
| Mark processed emails | Move to processed folder or add category tag in Outlook |
| Write tests | Mock Graph responses, verify email parsing, test attachment handling |

### Deliverable

Emails are automatically pulled from your Outlook inbox, triaged, and persisted. Attachments are downloaded to blob storage for classification in Layer 5.

---

<a name="layer-4"></a>
## Layer 4: Azure Document Intelligence — Text Extraction

**Goal**: Extract readable text from PDF, Word, and image attachments so the classifier has content to work with.

### Your Work (5 minutes)

1. **Retrieve the Cognitive Services key**:
   - Azure Portal → your Document Intelligence resource → **Keys and Endpoint**
   - Copy **Key 1** and the **Endpoint**

2. **Store in Key Vault**:
   - Create secret: Name = `cognitive-services-key`, Value = Key 1

3. **Give Claude**:
   ```
   Document Intelligence Endpoint: ___________________________
   ```

### Claude's Work

| Task | Details |
|---|---|
| Add `azure-ai-documentintelligence` SDK | Azure SDK for text extraction |
| Build extraction service | Submit PDF/DOCX/images → get structured text + layout |
| Extract key-value pairs | Vendor name, dates, amounts, reference numbers from invoices/contracts |
| Wire into attachment pipeline | Attachment downloaded (Layer 3) → text extracted (this layer) → fed to classifier (Layer 5) |
| Handle unsupported formats | Gracefully skip .zip, .exe, etc. — log and move to staging/errors |
| Write tests | Mock Document Intelligence responses, verify text extraction, test error handling |

### Deliverable

Every attachment that enters the pipeline is OCR'd / text-extracted before classification. The classifier now has both filename AND content to work with.

---

<a name="layer-5"></a>
## Layer 5: Classification & Filing Merge from Pillar 3

**Goal**: Move document classification, auto-naming, and filing recommendation logic from the standalone Pillar 3 into the email pipeline.

### Your Work

Nothing. Claude handles this entirely.

### Claude's Work

| Task | Details |
|---|---|
| Merge `document_ai/classifier.py` into Pillar 2 | All 30+ filename rules, 10+ content rules, AI classification pipeline |
| Merge `document_ai/naming.py` | Standardized naming engine (YYYY-MM-DD_Type_Identifier.ext) |
| Merge `document_ai/models.py` | Document types, filing map, folder hierarchy definitions |
| Merge `document_ai/corrections.py` | Correction logging for learning loop |
| Integrate with Cosmos DB | Persist classified documents and corrections (from Layer 1) |
| Wire into email pipeline | Email attachment → text extracted (Layer 4) → classified → filing recommendation generated → stored |
| Add attachment routing logic | Invoice attachments → flag for Pillar 1, receipt attachments → flag for Pillar 4 |
| Update OpenAPI spec | Single unified spec for the merged pillar |
| Update tests | Merge Pillar 3's 68 tests into Pillar 2 test suite |

### Deliverable

The email pipeline now classifies every attachment, generates a standardized filename, and recommends a filing location — all in one pass. No separate Pillar 3 Function App needed for email-sourced documents.

---

<a name="layer-6"></a>
## Layer 6: Microsoft Graph — SharePoint File Operations

**Goal**: Actually move classified files from blob staging into the governed SharePoint folder hierarchy.

### Your Work (15 minutes)

1. **Provision the SharePoint folder hierarchy** (if not already done):
   ```powershell
   cd pillar3-document-ai/scripts
   ./provision_sharepoint.ps1 -SiteUrl "https://peak10energy.sharepoint.com/sites/Operations"
   ```
   - Authenticate when the browser window opens
   - Verify folders exist in SharePoint: `00_STAGING`, `01_CORPORATE`, `02_OPERATIONS`, `03_DEALS`, `04_GOVERNANCE`

2. **Get your SharePoint Site ID**:
   - Open a browser and go to:
     ```
     https://peak10energy.sharepoint.com/sites/Operations/_api/site/id
     ```
   - Copy the GUID value (e.g., `a1b2c3d4-...`)
   - Or Claude can look this up via Graph API using the credentials from Layer 3

3. **Give Claude**:
   ```
   SharePoint site provisioned: yes
   SharePoint Site URL:         https://peak10energy.sharepoint.com/sites/Operations
   SharePoint Site ID:          ___________________________ (if you looked it up)
   ```

### Claude's Work

| Task | Details |
|---|---|
| Build SharePoint Graph client | Upload files, create folders, set metadata via Microsoft Graph |
| Build filing execution service | Take filing recommendation → upload to recommended path with standardized name |
| Handle conflicts | Duplicate filenames, locked files, permission errors |
| Build auto-file for high confidence | If classification confidence ≥ 0.85, file automatically without review |
| Build staging queue for low confidence | If confidence < 0.85, park in `00_STAGING/Inbox` and flag for review |
| Set SharePoint metadata | Document type, original sender, received date, classification confidence |
| Wire into email pipeline | Email processed → attachments classified → high-confidence auto-filed, low-confidence staged |
| Write tests | Mock Graph file operations, verify path resolution, test conflict handling |

### Deliverable

Classified attachments are automatically filed to the correct SharePoint folder with standardized names. Low-confidence documents are staged for your manual review.

---

<a name="layer-7"></a>
## Layer 7: Draft Response Review Flow

**Goal**: AI-drafted email replies are stored and retrievable so you can review, edit, and send them.

### Your Work

Nothing. Claude handles this entirely.

### Claude's Work

| Task | Details |
|---|---|
| Build draft storage in Cosmos DB | Store drafts with status: `generated`, `reviewed`, `sent`, `discarded` |
| Build review API endpoints | `GET /api/drafts` — list pending drafts, `PUT /api/drafts/{id}` — edit, `POST /api/drafts/{id}/send` — send via Graph |
| Build send-via-Graph | Use Mail.Send permission to send from the monitored mailbox |
| Tone selection | Generate drafts in the user's preferred tone (professional default, brief, warm) |
| Thread awareness | Reply-to threading, preserve conversation context |
| Write tests | Verify draft lifecycle, test send integration, test tone variations |

### Deliverable

After triage, AI-drafted replies are stored and accessible via API. You can list, edit, and send them. (A review UI is a future layer — for now this works via API or a simple webhook to your phone.)

---

<a name="layer-8"></a>
## Layer 8: Production Hardening

**Goal**: Make the system reliable, observable, and secure.

### Your Work (20 minutes)

1. **Enable diagnostic logging** for the Function App:
   - Azure Portal → Function App → **Diagnostic settings → Add**
   - Check: FunctionAppLogs, AppServiceHTTPLogs
   - Send to: Application Insights (already deployed)

2. **Set up an alert for failures**:
   - Azure Portal → Application Insights → **Alerts → New alert rule**
   - Condition: `requests/failed` > 5 in 5 minutes
   - Action group: Email to your address
   - Severity: 2 (Warning)

3. **Review Key Vault access policies**:
   - Azure Portal → Key Vault → **Access control (IAM)**
   - Verify only the Function App managed identity and your admin account have access
   - Remove any stale entries

### Claude's Work

| Task | Details |
|---|---|
| Add retry logic everywhere | Exponential backoff for Graph, OpenAI, Document Intelligence, Cosmos DB |
| Build dead letter queue | Failed classifications → blob container `dead-letter` with error details |
| Add circuit breaker | If OpenAI fails 5x in a row, fall back to rule-based-only mode and alert |
| Rate limiting | Cap OpenAI calls to budget (configurable tokens/day) |
| Structured logging | Consistent JSON log format, correlation IDs across the pipeline |
| Health check upgrade | `/api/health` verifies all downstream dependencies (Cosmos, OpenAI, Graph, SharePoint) |
| Auth hardening | Validate Function key on all endpoints, add IP allowlisting option |
| Cost tracking | Log estimated OpenAI spend per email, daily summary |
| Write integration tests | End-to-end: mock email in → verify triage + classification + filing + draft |

### Deliverable

Production-grade reliability. Failures are retried, dead-lettered, and alerted on. Costs are tracked. The system degrades gracefully if any dependency is down.

---

<a name="validation"></a>
## Final Validation Checklist

Run through this after all 8 layers are complete:

### Automated Pipeline
- [ ] Send a test email with subject "Invoice #TEST-001" and a PDF attachment
- [ ] Verify: email is triaged as `vendor_ap` with urgency `STANDARD`
- [ ] Verify: PDF attachment is text-extracted, classified as `invoice`
- [ ] Verify: attachment is filed to `01_CORPORATE/Finance/AP/` with standardized name
- [ ] Verify: triage result persists in Cosmos DB (survives Function App restart)

### Deal Signal Detection
- [ ] Send email with subject "RE: Letter of Intent - Loving County" and body mentioning "data room access"
- [ ] Verify: triaged as `deal_related`, urgency `HIGH`
- [ ] Verify: deal signals detected: `loi_discussion`, `due_diligence`
- [ ] Verify: AI draft reply generated and stored

### Receipt Routing
- [ ] Send email with subject "Your Uber receipt" and a receipt PDF
- [ ] Verify: triaged as `receipt`, urgency `LOW`
- [ ] Verify: attachment classified as `receipt`
- [ ] Verify: routing includes `pillar4:/api/expenses/attach-receipt`

### Document Filing
- [ ] Send email with attached NDA PDF
- [ ] Verify: classified as `nda` with high confidence
- [ ] Verify: auto-filed to `01_CORPORATE/Legal/NDAs/` in SharePoint
- [ ] Verify: standardized filename follows `YYYY-MM-DD_NDA_<Counterparty>.pdf`

### Low Confidence Handling
- [ ] Send email with an ambiguously named attachment (e.g., `doc_12345.pdf`)
- [ ] Verify: Azure OpenAI is called for classification
- [ ] Verify: if still low confidence, parked in `00_STAGING/Inbox`

### Draft Review
- [ ] Verify: draft reply is listed at `GET /api/drafts`
- [ ] Edit draft via `PUT /api/drafts/{id}`
- [ ] Send via `POST /api/drafts/{id}/send`
- [ ] Verify: email sent from your mailbox with correct threading

### Failure Scenarios
- [ ] Temporarily revoke OpenAI key → verify system falls back to rule-based mode
- [ ] Send an unsupported attachment (.zip) → verify it lands in `00_STAGING/Errors`
- [ ] Verify Application Insights shows logs for all operations
- [ ] Verify alert fires on simulated failures

---

## Summary: Who Does What, When

| Layer | Your Time | Claude's Time | Dependencies |
|---|---|---|---|
| **Pre-Flight** | 30-60 min | — | Azure OpenAI access may take 1-5 days |
| **Layer 1: Cosmos DB** | 0 min | ~2 hours | Pre-flight complete |
| **Layer 2: Azure OpenAI** | 15 min | ~3 hours | OpenAI access approved, model deployed |
| **Layer 3: Outlook/Graph** | 20 min | ~4 hours | App registration created, permissions granted |
| **Layer 4: Doc Intelligence** | 5 min | ~2 hours | Key stored in Key Vault |
| **Layer 5: Classification merge** | 0 min | ~2 hours | Layers 2 + 4 complete |
| **Layer 6: SharePoint filing** | 15 min | ~3 hours | Folders provisioned, Layer 5 complete |
| **Layer 7: Draft review** | 0 min | ~2 hours | Layer 3 complete |
| **Layer 8: Hardening** | 20 min | ~3 hours | All layers complete |
| **Validation** | 30 min | — | Everything deployed |
| **Total** | **~2.5 hours** | **~21 hours** | |

### Recommended Sequence

Layers 1-2 have no portal dependencies on each other — Claude can build them in parallel while you set up the Graph app registration (Layer 3 prep). The critical path is:

```
You: Pre-Flight checklist
         ↓
Claude: Layer 1 (Cosmos DB) ←──── can start immediately
         ↓
You: Deploy OpenAI model (Layer 2 prep)
You: Create app registration + grant permissions (Layer 3 prep)
You: Store Cognitive Services key (Layer 4 prep)
         ↓
Claude: Layers 2, 3, 4 ←──── can parallelize once prep is done
         ↓
Claude: Layer 5 (merge) ←──── depends on 2 + 4
         ↓
You: Provision SharePoint folders (Layer 6 prep)
         ↓
Claude: Layers 6, 7 ←──── can parallelize
         ↓
Claude: Layer 8 (hardening)
         ↓
You + Claude: Validation
```

Your portal work clusters into two sessions:
- **Session 1** (~45 min): OpenAI model, app registration, permissions, Cognitive Services key
- **Session 2** (~30 min): SharePoint provisioning, diagnostic logging, alerts

Between those sessions, Claude is building.
