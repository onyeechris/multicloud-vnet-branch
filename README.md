# MultiCloud Azure Networking & Compute API

FastAPI + Pulumi Automation API service that provisions Azure networking and compute: resource groups, VNets, NSGs, route tables, NAT gateways, key pairs and virtual machines.

Each resource type (for example a VPC, a subnet or a VM) is managed as its **own Pulumi stack**, created, updated and destroyed through REST endpoints. The service drives Pulumi through its Automation API, so no `pulumi up` is ever run by hand.

> This is one of four related services. See [Related repositories](#related-repositories).

## Contents

- [How it works](#how-it-works) · [Authentication](#authentication) · [Quick start](#quick-start) · [Configuration](#configuration)
- [API reference](#api-reference) · [Typical workflow](#typical-workflow) · [Docker](#docker) · [Project layout](#project-layout)
- [Security notes](#security-notes) · [Troubleshooting](#troubleshooting)

## How it works

```
client --HTTPS + JWT--> FastAPI --> Pulumi Automation API --> Azure resources
                                          |
                                          +--> stack state in an Azure Blob Storage container
```

- **Resources covered:** Resource Group, VNet, Subnet, NSG, Route Table, Route, NAT Gateway (with Standard Public IP), Key Pair (private key kept in Key Vault), Virtual Machine, curated VM image list.
- **One stack per resource.** You choose the stack name. Dependent resources reference earlier stacks by name, and the service resolves their outputs for you.
- **POST** creates a stack and returns 409 if it already exists. If creation fails part-way, the half-built stack is destroyed so the name can be reused. **PATCH** changes only the fields you send. **DELETE** destroys the stack's resources and removes its state.
- The account name comes from `AZURE_STORAGE_ACCOUNT`, not from the backend URL. The service principal also needs Key Vault data-plane access (`Key Vault Secrets User`) to download generated private keys.
- The active location is held in process memory and chosen with `POST /location/{location}`.

## Authentication

Every endpoint except the health checks requires a JWT bearer token:

```
Authorization: Bearer <token>
```

The service **only validates** tokens. It does not issue them, so they come from whatever identity service you run. Requirements:

| Item | Value |
|---|---|
| Algorithm | `HS256` |
| Signing key | the `jwt_secret_key` environment variable, shared with the issuer |
| Required claims | `sub` (an integer user id) and `role` |

A missing, malformed, wrongly signed or incomplete token gets `401`. If `jwt_secret_key` is not set, protected routes return `500` instead of silently allowing access.

Mint a token for local testing:

```bash
python -c "from jose import jwt; print(jwt.encode({'sub': '1', 'role': 'admin'}, 'your-jwt-secret', algorithm='HS256'))"
export TOKEN=<paste the output>
```

Auth is applied where routers are mounted in `app/main.py` (`dependencies=[Depends(get_current_user)]`), so any new router added there is protected automatically. The `role` claim is read but not yet used for authorization, so every valid token has full access.

## Quick start

Prerequisites: Python 3.12+, the [Pulumi CLI](https://www.pulumi.com/docs/install/), and Azure credentials with permission to create the resources above.

```bash
git clone <this repo> && cd <this repo>
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit the values
uvicorn main:app --reload
```

- Interactive docs: http://localhost:8000/docs (use **Authorize** to paste your token)
- Health check: `curl http://localhost:8000/health`

The first time you use the service, create the state container (an Azure Blob Storage container) and put its URL in `PULUMI_BACKEND_URL`. The app refuses to start if neither `PULUMI_BACKEND_URL` nor `PULUMI_ACCESS_TOKEN` is set, or if `PULUMI_CONFIG_PASSPHRASE` is missing.

## Configuration

All settings are environment variables, loaded from `.env`. Never commit `.env`.

| Variable | Required | Purpose |
|---|---|---|
| `PULUMI_BACKEND_URL` | one of these two | State backend, e.g. `azblob://your-pulumi-state-container` |
| `PULUMI_ACCESS_TOKEN` | one of these two | Pulumi Cloud token, used if no backend URL is set |
| `PULUMI_CONFIG_PASSPHRASE` | yes | Encrypts secrets inside stack state. Set once and do not change it for existing stacks |
| `AZURE_STORAGE_ACCOUNT` / `AZURE_STORAGE_KEY` | yes | Storage account holding the Pulumi state container |
| `ARM_CLIENT_ID` / `ARM_CLIENT_SECRET` / `ARM_TENANT_ID` / `ARM_SUBSCRIPTION_ID` | yes | Service principal used to provision resources (Contributor role) |
| `jwt_secret_key` | yes | HS256 key used to validate API tokens. Use a long random value |
| `SLACK_WEBHOOK_URL` | no | Incoming webhook for deployment notifications |

## API reference

All paths below require the bearer token unless marked otherwise. Live, always-current documentation is served at `/docs` (Swagger) and `/redoc`.

| Method | Path | Description |
|---|---|---|
| POST / GET | `/location/{location}`, `/location` | Set / read the active Azure location |
| GET, POST | `/resource-group` | List / create a resource group |
| GET, DELETE | `/resource-group/{stack_name}` | Read / destroy (cascades to dependent stacks) |
| GET, POST | `/vnet` | List / create a VNet |
| GET, PATCH, DELETE | `/vnet/{stack_name}` | Read / update / destroy |
| GET, POST | `/subnet` | List / create one or many subnets in a VNet (optional NSG, route table, NAT gateway) |
| GET, PATCH, DELETE | `/subnet/{stack_name}` | Read / update / destroy |
| GET, POST | `/nsg` | List / create a network security group with rules |
| GET, PATCH, DELETE | `/nsg/{stack_name}` | Read / update / destroy |
| GET, POST | `/route-table` | List / create a route table |
| GET, PATCH, DELETE | `/route-table/{stack_name}` | Read / update / destroy |
| GET, POST | `/route` | List / create routes in a route table |
| GET, PATCH, DELETE | `/route/{stack_name}` | Read / update / destroy |
| GET, POST | `/nat-gateway` | List / create a NAT gateway |
| GET, DELETE | `/nat-gateway/{stack_name}` | Read / destroy (also removes its public IP) |
| GET, POST | `/key-pair` | List / create an SSH key pair stored in Key Vault |
| GET | `/key-pair/{stack_name}/download` | Download the private key as a PEM file |
| GET, DELETE | `/key-pair/{stack_name}` | Read / destroy (Key Vault and secret included) |
| GET, POST | `/virtual-machine` | List / provision a VM (password, raw SSH key or key-pair stack) |
| GET, PATCH, DELETE | `/virtual-machine/{stack_name}` | Read / update / destroy |
| GET | `/images` | Curated Azure Marketplace images |
| GET | `/`, `/health` | Root and liveness checks (no auth) |

Example:

```bash
curl http://localhost:8000/images -H "Authorization: Bearer $TOKEN"
```
> See `/docs` or `docs/QA_GUIDE.md` for the request model of each endpoint.

Errors follow FastAPI's `{"detail": ...}` shape. Typical codes: `401` bad token, `404` unknown stack, `409` stack already exists, `422` validation error, `502` the cloud provider rejected the request.

More detail: [`docs/QA_GUIDE.md`](docs/QA_GUIDE.md) (Step-by-step end-to-end test flow, QA checklist and troubleshooting).

## Typical workflow

Create resources in dependency order, since each step uses outputs from the one before:

```
1. POST /location/eastus
2. POST /resource-group
3. POST /vnet
4. POST /nsg, /route-table, /route, /nat-gateway   (optional)
5. POST /subnet
6. POST /key-pair                                   (only for SSH access)
7. POST /virtual-machine
```
Tear down in reverse order, or delete the resource group, which cascades.

A consistent stack naming pattern keeps things findable, e.g. `{env}-{resource}-{location}`.

## Docker

```bash
docker build -t multicloud-vnet .
docker run -p 8000:8000 --env-file .env multicloud-vnet
```

The image is based on `pulumi/pulumi-python-3.12` and listens on port 8000. `entrypoint.sh` sets public DNS resolvers and starts uvicorn with a long keep-alive timeout, because stack operations can take minutes.

The included workflow `.github/workflows/cicd.yaml` is an example that builds the image and pushes it to Amazon ECR. It runs only on manual dispatch and needs the repository secrets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` and `ECR_REPOSITORY`.

## Project layout

```
main.py                  entry point (uvicorn main:app)
Pulumi.yaml              Pulumi project definition
app/
  main.py                FastAPI app, CORS, auth wiring, backend checks
  routes/                one router per resource (HTTP layer)
  models/                Pydantic request and response models
  pulumi_programs/       Pulumi programs that define the cloud resources
  utils/
    auth.py              JWT bearer validation
    stack.py             create / update / destroy / list stacks
    location_state.py   active location state
    slack.py             optional notifications
docs/                    detailed guide
```

## Security notes

- Keep `jwt_secret_key`, cloud credentials and `PULUMI_CONFIG_PASSPHRASE` in a secret manager or in environment variables. Never put them in the repo, and rotate any that were ever committed.
- The service holds credentials that can create and destroy cloud infrastructure. Run it on a private network, put it behind TLS, and restrict who can obtain tokens.
- CORS currently allows only `http://localhost:3000`. Change `allow_origins` in `app/main.py` for your front end.
- Private keys returned by `/key-pair/{stack}/download` are sensitive. Treat that endpoint accordingly.
- Authorization is all-or-nothing today. Enforce the `role` claim if you need least-privilege access.

## Troubleshooting

- **App exits at startup:** a required variable (`PULUMI_BACKEND_URL` or `PULUMI_ACCESS_TOKEN`, and `PULUMI_CONFIG_PASSPHRASE`) is missing.
- **401 on every call:** the token is signed with a different key than `jwt_secret_key`, or lacks `sub` / `role`.
- **500 "Auth is not configured":** `jwt_secret_key` is not set in the service's environment.
- **A request hangs for minutes:** stack operations are synchronous and cloud provisioning is slow. This is expected for NAT gateways, VMs and similar resources.

## Related repositories

[multicloud-vpc-feat-branch](https://github.com/onyeechris/multicloud-vpc-feat-branch) (AWS networking), [multicloud-eks-ec2-branch](https://github.com/onyeechris/multicloud-eks-ec2-branch) (AWS compute), [multicloud-global-lb-branch](https://github.com/onyeechris/multicloud-global-lb-branch) (AWS-Azure VPN and load balancer).
