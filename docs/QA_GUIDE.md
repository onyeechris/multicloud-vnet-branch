# MultiCloud — Azure Networking Service (QA Guide)

> **Authentication:** every endpoint except `/` and `/health` requires `Authorization: Bearer <JWT>`. See the top-level README.

> **Note:** every request must carry `Authorization: Bearer <JWT>` (see the top-level README).
> **Scope:** Azure-only. Provisions **Resource Group → VNet → NSG → Key Pair → Virtual Machine** via the Pulumi Automation API, fronted by FastAPI.
> **Base URL:** `http://<host>:8000`
> **Swagger UI (live test):** `http://<host>:8000/docs`
> **ReDoc:** `http://<host>:8000/redoc`

This README is written for QA. It tells you exactly how to bring the service up, what every endpoint expects, the order to call them, and how to tear everything down cleanly after a test run.

---

## 1. What this branch builds

Every Azure resource is its own **Pulumi stack** identified by a name you supply (e.g. `qa-rg-001`). Stacks are linked by **name and IDs from previous outputs** — never by raw Azure resource IDs that you typed by hand.

The current resource coverage on this branch:

| Resource         | Endpoint prefix       | Depends on                                              |
| ---------------- | --------------------- | ------------------------------------------------------- |
| Location (state) | `/location`           | —                                                       |
| Resource Group   | `/resource-group`     | location                                                |
| VNet             | `/vnet`               | resource group                                          |
| NSG              | `/nsg`                | resource group                                          |
| Route Table      | `/route-table`        | resource group                                          |
| Route            | `/route`              | resource group, route table                             |
| NAT Gateway      | `/nat-gateway`        | resource group (auto-creates a Standard Public IP)      |
| Subnet           | `/subnet`             | resource group, vnet, [nsg], [route table], [nat gateway] |
| Key Pair         | `/key-pair`           | resource group (writes to Key Vault)                    |
| Virtual Machine  | `/virtual-machine`    | resource group, subnet, [nsg], [key pair]               |

> AWS-side resources (VPC, IGW, AWS Subnet, Route Table, NAT Gateway, AWS Route, Region) are **not part of this branch** and have been removed. If a request mentions them, the request belongs on a different branch.

---

## 2. Prerequisites

| Tool                | Version            |
| ------------------- | ------------------ |
| Python              | 3.10+              |
| Pulumi CLI          | latest             |
| Azure CLI (`az`)    | latest             |
| Docker (optional)   | latest             |
| `curl` / Postman    | for hitting the API |

You will need:

- An **Azure subscription** the service principal can write to.
- An **Azure Storage Account + Container** for Pulumi state (azblob backend).
- A **service principal** with `Contributor` rights on the subscription.

Create the service principal once:

```bash
az ad sp create-for-rbac --name "multicloud-demo" --role Contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>
```

Capture the returned `appId`, `password`, and `tenant`. These become `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`.

---

## 3. Environment configuration

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

Required variables:

| Variable                 | Purpose                                                              |
| ------------------------ | -------------------------------------------------------------------- |
| `PULUMI_BACKEND_URL`     | `azblob://<container-name>` — where stack state lives                 |
| `PULUMI_CONFIG_PASSPHRASE` | Encrypts secrets in state (can be empty string for QA)              |
| `AZURE_STORAGE_ACCOUNT`  | Storage account holding the Pulumi state container                   |
| `AZURE_STORAGE_KEY`      | Primary key for that storage account                                 |
| `ARM_CLIENT_ID`          | Service principal app ID                                             |
| `ARM_CLIENT_SECRET`      | Service principal secret                                             |
| `ARM_TENANT_ID`          | Azure tenant ID                                                      |
| `ARM_SUBSCRIPTION_ID`    | Target Azure subscription ID                                         |

Optional:

| Variable             | Purpose                          |
| -------------------- | -------------------------------- |
| `SLACK_WEBHOOK_URL`  | Slack notifications (silent if unset) |
| `PULUMI_ACCESS_TOKEN`| Use Pulumi Cloud instead of azblob backend |

> The `.env` file is gitignored. Never paste real credentials into a PR or screenshot.

---

## 4. Run the service

### Option A — local Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Option B — Docker

```bash
docker build -t multicloud-vnet:dev .
docker run --rm -p 8000:8000 --env-file .env multicloud-vnet:dev
```

### Smoke test

```bash
curl -s http://localhost:8000/health
# → {"status":"ok","service":"azure-networking"}
```

Open the Swagger UI at **http://localhost:8000/docs** to exercise every endpoint interactively.

---

## 5. Standard response shape

Every create/read/update endpoint returns:

```json
{
  "status": "created" | "updated" | "ok",
  "stack":  "<stack-name>",
  "outputs": { "...": "..." }
}
```

Delete returns:

```json
{ "status": "deleted", "stack": "<stack-name>" }
```

Errors return a FastAPI-shaped body:

```json
{ "detail": "<message>" }
```

Common status codes:

| Code | Meaning                                                           |
| ---- | ----------------------------------------------------------------- |
| 201  | Stack created                                                     |
| 200  | OK — read/update/location-set                                     |
| 400  | Bad input (validation, naming, CIDR, credentials)                  |
| 404  | Stack not found                                                   |
| 409  | Stack already exists (POST with a duplicate `stack` name)         |
| 422  | Missing dependency (e.g. no active location, no resource group)   |
| 500  | Unexpected provider error — check server logs                     |

---

## 6. End-to-end QA flow

The canonical happy path. Each step depends on the previous one's stack.

> All bodies below assume `Content-Type: application/json`. Replace stack names with anything unique to your test run (e.g. `qa-rg-001`, `qa-vnet-001`).

### Step 1 — Select an active location

The service holds an "active location" in process state so you don't have to repeat it on every request.

```bash
curl -X POST http://localhost:8000/location/eastus
```

Confirm:

```bash
curl http://localhost:8000/location
# → {"active_location":"eastus"}
```

Valid values: `eastus`, `eastus2`, `westus`, `westus2`, `centralus`, `northeurope`, `westeurope`, `uksouth`.

### Step 2 — Create a Resource Group

```bash
curl -X POST http://localhost:8000/resource-group \
  -H "Content-Type: application/json" \
  -d '{
    "stack": "qa-rg-001",
    "name":  "qa-rg-001",
    "tags":  {"Owner": "qa", "Env": "test"}
  }'
```

Returns `outputs.resource_group_id` and `outputs.name`. **Note the `name`** — every subsequent resource uses it as `resource_group_name`.

### Step 3 — Create a VNet

```bash
curl -X POST http://localhost:8000/vnet \
  -H "Content-Type: application/json" \
  -d '{
    "stack": "qa-vnet-001",
    "name":  "qa-vnet-001",
    "resource_group_name": "qa-rg-001",
    "address_spaces": ["10.10.0.0/16"],
    "dns_servers": [],
    "tags": {"Owner": "qa"}
  }'
```

**Capture `name`** (the base name, e.g. `qa-vnet-001`) — the Subnet step's `vnet_name` field takes this base name and appends `-vnet` automatically.

### Step 4 — Create an NSG (optional but recommended)

```bash
curl -X POST http://localhost:8000/nsg \
  -H "Content-Type: application/json" \
  -d '{
    "stack": "qa-nsg-001",
    "name":  "qa-nsg-001",
    "resource_group_name": "qa-rg-001",
    "security_rules": [
      {
        "name": "AllowSSH",
        "priority": 1000,
        "direction": "Inbound",
        "access": "Allow",
        "protocol": "Tcp",
        "source_address_prefix": "*",
        "source_port_range": "*",
        "destination_address_prefix": "*",
        "destination_port_range": "22"
      }
    ],
    "tags": {"Owner": "qa"}
  }'
```

Capture `outputs.nsg_id`.

### Step 5 — Create a Route Table (optional)

```bash
curl -X POST http://localhost:8000/route-table \
  -H "Content-Type: application/json" \
  -d '{
    "stack": "qa-rt-001",
    "name":  "qa-rt-001",
    "resource_group_name": "qa-rg-001",
    "disable_bgp_route_propagation": false,
    "tags": {"Owner": "qa"}
  }'
```

Capture `outputs.route_table_id` and `outputs.route_table_name`.

### Step 6 — Add Routes to the Route Table (optional)

A Route stack adds one or more routes to an existing Route Table. Reference the parent table either by name or by stack:

```bash
curl -X POST http://localhost:8000/route \
  -H "Content-Type: application/json" \
  -d '{
    "stack": "qa-route-001",
    "name":  "qa-route-001",
    "resource_group_name": "qa-rg-001",
    "route_table_stack": "qa-rt-001",
    "routes": [
      {
        "name": "default-internet",
        "address_prefix": "0.0.0.0/0",
        "next_hop_type": "Internet"
      },
      {
        "name": "to-nva",
        "address_prefix": "10.99.0.0/16",
        "next_hop_type": "VirtualAppliance",
        "next_hop_ip_address": "10.10.1.4"
      }
    ],
    "tags": {"Owner": "qa"}
  }'
```

Valid `next_hop_type` values: `Internet`, `VirtualAppliance`, `VirtualNetworkGateway`, `VnetLocal`, `None`. `next_hop_ip_address` is **required** when `next_hop_type` is `VirtualAppliance` and **rejected** otherwise.

### Step 7 — Create a NAT Gateway (optional)

Provisions a Standard Public IP **and** the NAT Gateway in one stack:

```bash
curl -X POST http://localhost:8000/nat-gateway \
  -H "Content-Type: application/json" \
  -d '{
    "stack": "qa-nat-001",
    "name":  "qa-nat-001",
    "resource_group_name": "qa-rg-001",
    "idle_timeout_in_minutes": 4,
    "zones": ["1"],
    "tags": {"Owner": "qa"}
  }'
```

`idle_timeout_in_minutes` must be 4–120. Omit `zones` for a regional (non-zonal) NAT Gateway. Capture `outputs.nat_gateway_id` and `outputs.public_ip_address`.

### Step 8 — Create a Subnet inside the VNet

Attach the optional NSG / Route Table / NAT Gateway here — pass the **stack name** (preferred) or the raw **resource ID**. Mixing both for the same resource returns `400`.

```bash
curl -X POST http://localhost:8000/subnet \
  -H "Content-Type: application/json" \
  -d '{
    "stack": "qa-subnet-001",
    "name":  "qa-subnet-001",
    "resource_group_name": "qa-rg-001",
    "vnet_name": "qa-vnet-001",
    "subnets": [
      {
        "name": "app",
        "address_prefix": "10.10.1.0/24",
        "nsg_stack":         "qa-nsg-001",
        "route_table_stack": "qa-rt-001",
        "nat_gateway_stack": "qa-nat-001"
      }
    ],
    "tags": {"Owner": "qa"}
  }'
```

Equivalent raw-ID form (any subset of these three fields is allowed, both forms can mix across different entries):

```json
{
  "name": "app",
  "address_prefix": "10.10.1.0/24",
  "nsg_id":         "<paste outputs.nsg_id>",
  "route_table_id": "<paste outputs.route_table_id>",
  "nat_gateway_id": "<paste outputs.nat_gateway_id>"
}
```

A single subnet stack can hold multiple subnets — add more entries to the `subnets` array. **Capture `outputs.subnet_ids[0]`** — the VM step needs it.

### Step 9 — Create a Key Pair (only if you want SSH access)

```bash
curl -X POST http://localhost:8000/key-pair \
  -H "Content-Type: application/json" \
  -d '{
    "stack": "qa-key-001",
    "name":  "qa-key-001",
    "resource_group_name": "qa-rg-001",
    "tags": {"Owner": "qa"}
  }'
```

The private key is stored in Azure Key Vault. Pull it down with:

```bash
curl -OJ http://localhost:8000/key-pair/qa-key-001/download
chmod 600 qa-key-001.pem
```

### Step 10 — Create the Virtual Machine

Pick **one** authentication method:

- `admin_password` (string), **or**
- `ssh_public_key` (raw OpenSSH public key string), **or**
- `key_pair_stack` (the key-pair stack you just created — the service resolves the public key automatically).

```bash
curl -X POST http://localhost:8000/virtual-machine \
  -H "Content-Type: application/json" \
  -d '{
    "stack": "qa-vm-001",
    "name":  "qa-vm-001",
    "resource_group_name": "qa-rg-001",
    "subnet_id": "<paste outputs.subnet_ids[0] from Subnet stack>",
    "vm_size": "Standard_B1s",
    "admin_username": "azureuser",
    "key_pair_stack": "qa-key-001",
    "create_public_ip": true,
    "nsg_stack": "qa-nsg-001",
    "image": {
      "publisher": "Canonical",
      "offer":     "0001-com-ubuntu-server-jammy",
      "sku":       "22_04-lts-gen2",
      "version":   "latest"
    },
    "tags": {"Owner": "qa"}
  }'
```

> NSG attachment: use **`nsg_stack`** (the stack name — recommended, the backend resolves the ID from outputs) **OR** **`nsg_id`** (raw Azure resource ID). Setting both returns `400`. Omit both to leave the NIC without an NSG.

The response includes `outputs.public_ip` (when `create_public_ip: true`) and `outputs.vm_id`. SSH in to verify:

```bash
ssh -i qa-key-001.pem azureuser@<public_ip>
```

---

## 7. Reading and listing stacks

| Action                  | Request                                |
| ----------------------- | -------------------------------------- |
| List all RGs            | `GET /resource-group`                  |
| Get one RG by stack     | `GET /resource-group/qa-rg-001`        |
| List all VNets          | `GET /vnet`                            |
| Get one VNet            | `GET /vnet/qa-vnet-001`                |
| List all Subnets        | `GET /subnet`                          |
| Get one Subnet          | `GET /subnet/qa-subnet-001`            |
| List Route Tables       | `GET /route-table`                     |
| List Routes             | `GET /route`                           |
| List NAT Gateways       | `GET /nat-gateway`                     |
| List NSGs / KeyPairs / VMs | `GET /nsg`, `/key-pair`, `/virtual-machine` |

Listings only include stacks whose outputs match the expected resource type, so `/vnet` won't accidentally list resource groups.

---

## 8. Updates (PUT vs PATCH)

- **`PUT /<resource>/{stack}`** — full replacement. Send the same body shape as `POST`. The `stack` field in the body must match the path.
- **`PATCH /<resource>/{stack}`** — partial update. Send only the fields you want to change.

> You **cannot rename a stack**. Trying to PUT/PATCH with a different `stack` value returns `400`.

---

## 9. Teardown (run this at the end of every test run)

Destroy in **reverse dependency order** so Azure doesn't complain about resources still in use.

```bash
curl -X DELETE http://localhost:8000/virtual-machine/qa-vm-001
curl -X DELETE http://localhost:8000/key-pair/qa-key-001
curl -X DELETE http://localhost:8000/subnet/qa-subnet-001
curl -X DELETE http://localhost:8000/nat-gateway/qa-nat-001
curl -X DELETE http://localhost:8000/route/qa-route-001
curl -X DELETE http://localhost:8000/route-table/qa-rt-001
curl -X DELETE http://localhost:8000/nsg/qa-nsg-001
curl -X DELETE http://localhost:8000/vnet/qa-vnet-001
curl -X DELETE http://localhost:8000/resource-group/qa-rg-001
```

Each call returns `{"status": "deleted", "stack": "<name>"}` and removes both the Azure resources and the Pulumi stack record from the azblob backend.

---

## 10. QA test checklist

Tick these off per test run. Anything failing is a bug — capture the response body and server log lines and file it.

**Setup**

- [ ] `GET /health` returns `{"status":"ok"}`
- [ ] `POST /location/{eastus}` returns the active location
- [ ] `GET /location` returns the same value

**Create flow (happy path)**

- [ ] `POST /resource-group` returns `201` and `outputs.resource_group_id`
- [ ] `POST /vnet` returns `201` and `outputs.vnet_id` + `outputs.vnet_name` are populated
- [ ] `POST /nsg` returns `201` and `outputs.nsg_id` is populated
- [ ] `POST /route-table` returns `201` and `outputs.route_table_id` + `outputs.route_table_name` are populated
- [ ] `POST /route` (against the route table stack via `route_table_stack`) returns `201` and `outputs.route_ids` is a non-empty list
- [ ] `POST /route` with `next_hop_type: "VirtualAppliance"` but no `next_hop_ip_address` returns `400`
- [ ] `POST /nat-gateway` returns `201` and `outputs.nat_gateway_id` + `outputs.public_ip_address` are populated
- [ ] `POST /subnet` referencing `nsg_stack` / `route_table_stack` / `nat_gateway_stack` returns `201` and `outputs.subnet_ids` is a non-empty list
- [ ] `POST /subnet` with both `nsg_id` and `nsg_stack` on the same entry returns `400`
- [ ] `POST /key-pair` returns `201` and `outputs.key_vault_uri` is populated
- [ ] `GET /key-pair/{stack}/download` streams a `.pem` file
- [ ] `POST /virtual-machine` returns `201` and `outputs.public_ip` is populated
- [ ] SSH into the VM using the downloaded key works

**Read flow**

- [ ] `GET /<resource>` lists only the matching resource type
- [ ] `GET /<resource>/{stack}` returns the same outputs as the create response

**Update flow**

- [ ] `PATCH /resource-group/{stack}` with only `tags` updates tags without re-creating the RG
- [ ] `PUT /vnet/{stack}` with a different `stack` value in the body returns `400`

**Error flow**

- [ ] `POST /resource-group` with a duplicate `stack` returns `409`
- [ ] `POST /vnet` before any `POST /location` (fresh process, no `location` field in body) returns `422`
- [ ] `POST /virtual-machine` with neither `admin_password`, `ssh_public_key`, nor `key_pair_stack` returns `400`
- [ ] `POST /virtual-machine` with **two** auth methods set returns `400`
- [ ] `GET /resource-group/does-not-exist` returns `404`

**Teardown**

- [ ] All `DELETE` calls succeed in reverse dependency order
- [ ] After teardown, `GET /<resource>` listings are empty (or no longer contain the test stacks)
- [ ] No leftover resources in the Azure portal for the test resource group

---

## 11. Troubleshooting

| Symptom                                                              | Likely cause                                                                            |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `RuntimeError: No Pulumi backend configured`                         | `.env` not loaded, or `PULUMI_BACKEND_URL` / `PULUMI_ACCESS_TOKEN` missing              |
| `RuntimeError: PULUMI_CONFIG_PASSPHRASE is not set`                  | Add `PULUMI_CONFIG_PASSPHRASE=""` to `.env` (empty value is fine)                       |
| `422 No location provided and no active location selected`           | Call `POST /location/{location}` first, or send `location` in the request body          |
| `409 Resource Group already exist`                                   | Stack name already in use — pick a fresh one or `DELETE` the old one                    |
| `400 Invalid Azure input: ...`                                       | CIDR, name, or location rejected by Azure — fix the field and retry                     |
| Pulumi hangs on `stack.up`                                           | Azure quota / propagation delay — give it 60s; check Azure Portal for in-flight ops     |
| `download` endpoint returns `502`                                    | Service principal lacks `Key Vault Secrets User` on the vault; re-run RBAC assignment   |

Server logs (uvicorn stdout) include the full Pulumi output for each request — when reporting a bug, paste the block between `Updating (...)` and `Resources:`.

---

## 12. Useful one-liners

```bash
# Tail the running container's logs
docker logs -f $(docker ps -q --filter ancestor=multicloud-vnet:dev)

# Quickly destroy every stack from a QA run (in dependency-safe order)
for entry in virtual-machine/qa-vm-001 key-pair/qa-key-001 \
             subnet/qa-subnet-001 nat-gateway/qa-nat-001 \
             route/qa-route-001 route-table/qa-rt-001 \
             nsg/qa-nsg-001 vnet/qa-vnet-001 resource-group/qa-rg-001; do
  curl -s -X DELETE "http://localhost:8000/$entry" -o /dev/null -w "$entry → %{http_code}\n"
done

# List every stack the backend knows about (any resource type)
curl -s http://localhost:8000/resource-group
curl -s http://localhost:8000/vnet
curl -s http://localhost:8000/subnet
curl -s http://localhost:8000/nsg
curl -s http://localhost:8000/route-table
curl -s http://localhost:8000/route
curl -s http://localhost:8000/nat-gateway
curl -s http://localhost:8000/key-pair
curl -s http://localhost:8000/virtual-machine
```
