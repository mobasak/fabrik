# Vast.ai — full reference for Fabrik

**Last verified:** 2026-06-16 against [docs.vast.ai/llms.txt](https://docs.vast.ai/llms.txt) (246 indexed pages) + `vastai` CLI v0.3+.
**Why this file exists:** Vast.ai is the third provider in Fabrik's GPU surface. The driver lives at [`src/fabrik/drivers/vast_provider.py`](../../src/fabrik/drivers/vast_provider.py); the orchestrator's [`selection_advice()`](../../src/fabrik/orchestrator/gpu_rent.py) routes checkpoint-tolerant + spot-OK workloads here. This file is the source of truth for what Vast can/can't do, what every CLI flag/API field means, and which Fabrik surfaces map to which Vast primitive. Re-verify the **Pricing** + **Serverless** sections quarterly.

---

## TL;DR for Fabrik

| Question | Answer |
|---|---|
| When does `fabrik gpu rent --provider vast` win? | Two cases: (1) **spot-priced training** — interruptible bidding is 50%+ cheaper than on-demand if you can checkpoint, (2) **GPU types unavailable elsewhere** — Vast.ai has a long tail (RTX 3090, RTX 4090, A6000, MI300) that RunPod/Modal don't carry. |
| When does RunPod still win? | When you need an SLA / verified host / no preemption surprises. Vast is a marketplace; quality varies wildly by host. |
| Auth | `VAST_API_KEY` in `/opt/fabrik/.env.sysadmin`. Already set 2026-06-16. |
| Pricing model | **Marketplace** — hosts set their own prices. No fixed rate card. Search via `vastai search offers` for live rates. |
| **Serverless** | Yes! Vast Serverless is autoscaled endpoints with PyWorker. **No platform fee** — you only pay for the underlying worker instances. |
| What Vast does NOT do (vs RunPod/Modal) | No "Secure Cloud" SLA — even verified machines can have drift. No memory snapshots / FlashBoot. No native cron / scheduled functions. No managed Postgres / Redis (it's pure compute). |
| Minimum top-up | $5 (verified 2026-06-16) — plenty for smoke tests; each create→destroy cycle costs <$0.01. |
| `gpu_ram` gotcha | CLI accepts GB; REST API expects MB. CLI auto-converts. **Driver hides this.** |

---

## 1. Mental model — Vast vs RunPod / Modal

Vast.ai is a **GPU marketplace**, not a managed cloud. Hosts (datacenters, gaming-PC owners, sometimes individuals) list capacity; renters bid for it. This is structurally different from RunPod's "Secure Cloud" SLA and Modal's serverless abstraction.

| Concept | RunPod | Modal | Vast.ai | How `vast_provider.py` handles it |
|---|---|---|---|---|
| Unit of work | Pod | Function | **Instance** (Docker container on a rented machine) | `create_pod()` does a 2-phase request: `PUT /asks/` searches offers, then `PUT /asks/<offer_id>/` claims one |
| Pricing | Fixed hourly (Secure) | Per-second flat rate | **Per-second**, host-set, market-driven | `estimate_cost()` uses approx floor prices (`HOURLY_USD_BY_PROVIDER["vast"]`); actual cost retrieved from instance metadata at destroy time |
| Reliability tiers | Secure / Community | Single tier | **Verified / Unverified / Datacenter**, plus a per-machine **reliability score** (0.0–1.0) | Driver defaults search to `verified=true reliability>0.95` for safety |
| Spot/preempt | N/A on Secure | Default for all functions (`nonpreemptible=True` to opt out, 3×, CPU-only) | **Interruptible** mode = bid against on-demand; gets paused when outbid | Driver uses on-demand by default; `--interruptible` flag opts in |
| Serverless | Endpoints (pinned via env) | App + `@modal.asgi_app` + `modal deploy` | **Endpoints + WorkerGroups + PyWorker** (closest analog to RunPod) | Phase 2 stubs only — Phase 3 will wire `create_endpoint()` against `POST /api/v0/endptjobs/` |
| SSH access | Built-in | Via Sandbox.exec() | **First-class** — direct (faster, requires open ports) or proxied | Driver creates pods with `--ssh --direct`, returns `ssh-url <instance_id>` for connect |
| Persistence | Network volumes | Volumes (v2) | **Container disk** (lost on destroy) OR **Volume** (host-bound, survives destroy but not machine migration) | Driver tracks both via `container_disk_gb` + `volume_gb` kwargs |
| Identity tag for reaper safety | `env`-injected `FABRIK_SESSION_ID` | `secrets=` + image env | `--env` flag at create | Driver injects `FABRIK_SESSION_ID` via `--env '-e FABRIK_SESSION_ID=<id>'` — same C4 tag-safety invariant |

**Implication:** Vast is the **most variable** of the three providers. Always set `verified=true` + `reliability>0.95` in search params for production workloads. For checkpoint-tolerant training, drop those filters to get 50%+ cheaper spot prices.

---

## 2. Auth + CLI setup

### 2.1 Install + authenticate

```bash
# Install
.venv/bin/pip install vastai

# Set API key (already wired into .env.sysadmin for Fabrik)
.venv/bin/vastai set api-key $VAST_API_KEY
# → saved to ~/.config/vastai/vast_api_key
```

The CLI reads from `~/.config/vastai/vast_api_key` by default; all commands accept `--api-key KEY` to override. Fabrik's driver passes the key explicitly so it never depends on the CLI's local config.

### 2.2 Register SSH key (one-time)

```bash
# Auto-generate + register (backs up existing as .backup_<ts>):
vastai create ssh-key --api-key $VAST_API_KEY

# OR add an existing key:
cat ~/.ssh/id_ed25519.pub                   # copy this
# Then paste into https://cloud.vast.ai/manage-keys/
```

**Critical:** "Adding a key to your account keys only applies to **new instances**." Existing instances retain their original keys. For Fabrik's create→work→destroy lifecycle this doesn't matter, but if you're SSHing into a long-lived rental, the key must be registered before create.

### 2.3 CLI cheat-sheet

```bash
# Account
vastai show user
vastai show api-keys
vastai show invoices
vastai show ssh-keys
vastai create ssh-key

# Search offers (see §5 for full query syntax)
vastai search offers 'reliability>0.99 num_gpus=1 gpu_name=RTX_4090 rented=False'
vastai search offers 'gpu_name=H100_SXM5 dph_total<3' -o 'dph_total'
vastai search offers '...' --type=bid              # interruptible/spot prices
vastai search offers '...' --raw                   # JSON output

# Instances
vastai create instance <offer_id> --image pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime --disk 40 --ssh --direct
vastai show instances
vastai show instance <id>
vastai label instance <id> "training-run-42"
vastai logs <id>
vastai ssh-url <id>                                # → ssh://root@host:port
vastai stop instance <id>
vastai start instance <id>                         # restart a stopped one
vastai reboot instance <id>
vastai destroy instance <id>
vastai destroy instances <id1> <id2> <id3>         # bulk
vastai change-bid <id> <new_bid>                   # re-bid interruptible

# File copy (uses SCP under the hood)
vastai copy <src> <id>:/path/to/dst
vastai copy <id>:/path/to/src ./local-dst
vastai cloud-copy --src s3://bucket/x --instance <id>:/path

# Templates
vastai search templates
vastai create template --image ... --disk ... --onstart-cmd '...'
vastai delete template <hash>

# Volumes (persistent, machine-bound)
vastai create volume <offer_id> --volume-size 100
vastai list volumes
vastai clone-volume <id>
vastai delete volume <id>

# Serverless
vastai create endpoint --endpoint_name "llama-prod" --max_workers 20 --target_util 0.9
vastai create workergroup --endpoint_id <id> --template_hash <hash> --search_params 'gpu_ram>=24'
vastai show endpoints
vastai update endpoint <id> --max_workers 50
vastai get-endpt-logs <id>
vastai delete endpoint <id>
vastai delete workergroup <id>
vastai route <endpoint_name> <cost>                # manually invoke routing

# Defaults / config
vastai set api-key <key>
vastai show defaults
vastai show user
```

**Global flags** (work on every subcommand): `--url URL`, `--retry N`, `--raw` (JSON output), `--explain` (dump API calls), `--api-key KEY`.

---

## 3. Concepts — marketplace vocabulary

### 3.1 Host vs Renter vs Machine vs Offer

- **Host**: someone with a GPU machine listed for rent. Range: single gaming PCs → Tier-4 datacenters.
- **Renter**: you. Most of the docs are written for this perspective.
- **Machine**: one physical host system. Can publish multiple **offers** (different slices of GPUs / storage / bandwidth).
- **Offer**: a specific configuration ready to rent. Shown as a row in [cloud.vast.ai/create](https://cloud.vast.ai/create/). Includes GPU model + count, CPU, RAM, disk, bandwidth, price, max duration, location, DLPerf score, reliability score.
- **Instance**: what you get when you accept an offer. A running, isolated container (or VM) with exclusive GPU access. Bills per second while running + storage per second while existing.

### 3.2 Scores

| Score | Range | Meaning |
|---|---|---|
| **DLPerf** | unitless | Vast-defined benchmark approximating deep-learning throughput. Use for apples-to-apples GPU comparison (not raw TFLOPs). |
| **DLPerf/$** | unitless | DLPerf per dollar — the price-performance metric. Sort by this for cheapest-effective compute. |
| **Reliability** | 0.0–1.0 | Historical uptime + health. **New machines start at 0.60** and climb. Set `reliability>0.95` for production. |

### 3.3 Verification tiers

| Tier | Search field | Meaning |
|---|---|---|
| **Verified** | `verified=true` | Host's hardware specs have been Vast-checked. Default for production. |
| **Unverified** | `verified=false` | Cheaper but specs not validated. OK for fault-tolerant work. |
| **Datacenter** | `datacenter=true` | Subset of verified — Tier-3/4 facilities with proper power, cooling, networking. |

### 3.4 Rental contract types (NOT the same as instance kinds)

| Type | Priority | Pricing | Use |
|---|---|---|---|
| **On-demand** | High | Fixed (host-set) | Production, time-sensitive |
| **Reserved** | High | On-demand + pre-pay discount (up to 50%) | Long-term commitment |
| **Interruptible** | Low | Bidding; lowest cost (50%+ cheaper) | Fault-tolerant batch, checkpoint-resumable training |

**Once an instance is rented, type cannot be changed** (except on-demand → reserved via pre-pay).

---

## 4. Search offers — the query language

The marketplace is the system. Every workflow starts with `vastai search offers`.

### 4.1 Query syntax

```
query      = comparison comparison...
comparison = field op value
op         = one of: <, <=, ==, !=, >=, >, in, notin
value      = <bool, int, float, string> | 'any' | [v0, v1, ...]
```

- Quote `>` and `<` on the shell: `'reliability>0.99'`
- String values: **replace spaces with underscores**. `gpu_name=RTX_3090` not `gpu_name=RTX 3090`. (In list-form values you CAN use quoted spaces: `gpu_name in ["RTX 4090", "RTX 3090"]`.)
- Default query (used unless `-n` / `--no-default`): `external=false rentable=true verified=true`. Pass `-n` to query the full unverified pool.

### 4.2 Examples

```bash
# Reliable single RTX 3090, not currently rented
vastai search offers 'reliability > 0.98 num_gpus=1 gpu_name=RTX_3090 rented=False'

# Datacenter GPUs with min compute + TFLOPs
vastai search offers 'compute_cap > 610 total_flops > 5 datacenter=True'

# Reliable 4-GPU offers in Taiwan or Sweden
vastai search offers 'reliability>0.99 num_gpus=4 geolocation in [TW,SE]'

# RTX 3090 or 4090 NOT in China or Vietnam
vastai search offers 'reliability>0.99 gpu_name in ["RTX 4090", "RTX 3090"] geolocation notin [CN,VN]'

# Strict requirements for ML workload (CUDA, ports, NVIDIA driver)
vastai search offers 'disk_space>146 duration>24 gpu_ram>10 cuda_vers>=12.1 direct_port_count>=2 driver_version >= 535.86.05'

# 4+ GPUs incl. unverified, sort by num_gpus desc
vastai search offers 'reliability > 0.99 num_gpus>=4 verified=False rented=any' -o 'num_gpus-'

# Cheapest H100 SXM5 (sort by $/hr ascending)
vastai search offers 'gpu_name=H100_SXM5' -o 'dph_total'

# Best price-performance — sort by DLPerf per dollar
vastai search offers 'reliability>0.95' -o 'dlperf_usd-'

# Interruptible (spot) pricing
vastai search offers 'gpu_name=RTX_4090' --type=bid

# ARM64 hosts (rare)
vastai search offers 'cpu_arch=arm64'
```

### 4.3 Sort

`-o '<field>[,<field>...]'` — postfix `-` for descending. Default: `score-` (Vast's blended quality score, descending).

Useful sorts:
- `-o 'dph_total'` — cheapest first
- `-o 'dlperf_usd-'` — best price-performance first
- `-o 'reliability-'` — most reliable first
- `-o 'num_gpus-'` — biggest box first

### 4.4 Full field reference (use `vastai search offers --help` for live list)

| Field | Type | Description |
|---|---|---|
| `bw_nvlink` | float | NVLink bandwidth |
| `compute_cap` | int | CUDA compute capability × 100 (e.g. 700 = 7.0) |
| `cpu_arch` | string | `amd64` or `arm64` |
| `cpu_cores` | int | virtual CPUs |
| `cpu_cores_effective` | float | virtual CPUs actually allocated to you |
| `cpu_ghz` | float | CPU clock |
| `cpu_ram` | float | system RAM (GB) |
| `cuda_vers` | float | max supported CUDA version (driver-bound) |
| `datacenter` | bool | Tier-3/4 facilities only |
| `direct_port_count` | int | open ports on host router (needed for direct SSH) |
| `disk_bw` | float | disk read MB/s |
| `disk_space` | float | disk GB |
| `dlperf` | float | DLPerf score |
| `dlperf_usd` | float | DLPerf per dollar (sort key for value) |
| `dph` | float | $/hr base rental cost |
| `dph_total` | float | $/hr **including storage** at the search's `--storage` size |
| `driver_version` | string | "535.86.05"-style 3-digit string |
| `duration` | float | max rental duration in days |
| `external` | bool | include non-datacenter offers (default `false` excludes them) |
| `flops_usd` | float | TFLOPs per dollar |
| `geolocation` | string | 2-letter country code (`US`, `TW`, `DE`, `CN`...) |
| `gpu_arch` | string | `nvidia` / `amd` |
| `gpu_display_active` | bool | GPU has a display attached (= gaming PC) |
| `gpu_frac` | float | fraction of machine's GPUs in this offer |
| `gpu_max_power` | float | per-GPU watts |
| `gpu_max_temp` | float | GPU temp limit °C |
| `gpu_mem_bw` | float | GPU memory bandwidth GB/s |
| `gpu_name` | string | model (use underscores in equality, quoted in lists) |
| `gpu_ram` | float | per-GPU VRAM in GB (**API uses MB!** see §13) |
| `gpu_total_ram` | float | total VRAM across all GPUs in offer |
| `has_avx` | bool | CPU has AVX |
| `id` | int | unique offer ID — pass to `vastai create instance <id>` |
| `inet_down` | float | network down Mbps |
| `inet_down_cost` | float | $/GB inbound |
| `inet_up` | float | network up Mbps |
| `inet_up_cost` | float | $/GB outbound |
| `machine_id` | int | underlying machine ID |
| `min_bid` | float | current floor bid for interruptible |
| `num_gpus` | int | GPU count in this offer |
| `pci_gen` | float | PCIe generation |
| `pcie_bw` | float | PCIe bandwidth GB/s (CPU↔GPU) |
| `reliability` | float | 0.0–1.0 host reliability score |
| `rentable` | bool | currently rentable |
| `rented` | bool | currently rented (set `rented=False` to avoid conflicts with stopped instances) |
| `storage_cost` | float | $/GB/month for storage |
| `static_ip` | bool | host has stable IP |
| `total_flops` | float | TFLOPs aggregate across all GPUs |
| `ubuntu_version` | string | host OS version |
| `verified` | bool | Vast-validated hardware |
| `vms_enabled` | bool | machine supports VM instances (not Docker) |

---

## 5. Create instance — the rental call

After search, take the offer's `id` and pass it to `create instance`.

### 5.1 Minimum viable call

```bash
vastai create instance 12345678 \
    --image pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime \
    --disk 40
```

Returns `{"success": True, "new_contract": 7835610}` — the **`new_contract`** value IS the instance ID (per llms.txt: "POST `/api/v0/asks/{id}/` returns `new_contract` as the instance ID, not `id`"). Wire this into `gpu_state.json` as `instance_id`.

### 5.2 Full flag table

| Flag | Type | Default | Notes |
|---|---|---|---|
| **Positional** `ID` | int | — | Offer ID from search |
| `--image IMG` | string | — | Docker image. Required. |
| `--template_hash HASH` | string | — | Use a saved template instead of `--image` |
| `--disk GB` | float | 10 | Container disk size |
| `--label TEXT` | string | — | Human-readable instance label |
| `--ssh` | bool | false | Inject SSH server into container |
| `--direct` | bool | false | Use direct (host port-forwarded) SSH instead of proxied. Requires `direct_port_count >= 1` on the offer. |
| `--jupyter` | bool | false | Launch Jupyter instead of SSH |
| `--jupyter-lab` | bool | false | JupyterLab variant |
| `--jupyter-dir DIR` | string | image workdir | Jupyter root |
| `--onstart FILE` | string | — | Local file → uploaded as startup script |
| `--onstart-cmd "..."` | string | — | Inline startup command (max **4048 chars** per llms.txt — gzip+base64 longer scripts) |
| `--entrypoint CMD` | string | — | Override Docker ENTRYPOINT (args-launch mode) |
| `--args ...` | string | — | Args after entrypoint. **Must be last** — consumes all remaining tokens. |
| `--env "..."` | string | — | env + port mapping in one string: `-e KEY=val -e KEY2=val2 -p 8080:8080 -p 9090:9090/udp -h hostname` |
| `--login "-u USER -p PASS docker.io"` | string | — | Private registry login (single-quoted) |
| `--user USER` | string | — | Docker `--user` override (breaks many images — only use if certain) |
| `--lang-utf8` | bool | false | Install locales for buggy images |
| `--python-utf8` | bool | false | Force `PYTHONIOENCODING=C.UTF-8` |
| `--bid_price USD` | float | — | **PRESENCE makes it interruptible.** Per-machine bid in $/hr. |
| `--force` | bool | false | Skip sanity checks |
| `--cancel-unavail` | bool | false | Error out if scheduling fails (instead of stopped instance) |
| `--create-volume OFFER_ID` | int | — | Create new volume from offer + link to instance |
| `--link-volume VOL_ID` | int | — | Link existing volume to new instance |
| `--volume-size GB` | int | 15 | Volume size (with `--create-volume`) |
| `--mount-path PATH` | string | — | Where to mount the volume in-container (e.g. `/root/volume`) |
| `--volume-label NAME` | string | — | Name for new volume |

### 5.3 The four launch modes (mutually exclusive)

1. **SSH** (`--ssh [--direct]`) → image is wrapped with sshd + your registered key. Default for `gpu_rent.rent()`.
2. **Jupyter** (`--jupyter [--jupyter-lab] [--jupyter-dir]`) → image is wrapped with Jupyter; URL via dashboard or `ssh-url`.
3. **Entrypoint** (`--entrypoint CMD --args ...`) → image runs with no SSH/Jupyter injection. Use for batch jobs.
4. **Plain** (no `--ssh`, no `--jupyter`) → docker `CMD` runs as-is. Useful for one-shot containers.

### 5.4 Examples (from official docs)

```bash
# On-demand, PyTorch (cuDNN Devel) template, 64GB disk
vastai create instance 384826 --template_hash 661d064bbda1f2a133816b6d55da07c3 --disk 64

# On-demand, pytorch image, 40GB disk, open UDP 8081, direct SSH, hostname billybob, onstart
vastai create instance 6995713 --image pytorch/pytorch --disk 40 \
    --env '-p 8081:8081/udp -h billybob' --ssh --direct \
    --onstart-cmd "env | grep _ >> /etc/environment; echo 'starting up'"

# On-demand, private repo, Jupyter + direct, port mappings + env
vastai create instance 384827 \
    --image bobsrepo/pytorch:latest \
    --login '-u bob -p secret docker.io' \
    --jupyter --direct \
    --env '-e TZ=PDT -e XNAME=XX4 -p 22:22 -p 8080:8080' --disk 20

# Args-launch (no SSH/Jupyter) — bash command keeps container alive
vastai create instance 5801802 --image pytorch/pytorch --disk 40 \
    --onstart-cmd 'bash' --args -c 'echo hello; sleep infinity;'

# Interruptible (spot) with PyTorch template, bid $0.10/hr
vastai create instance 384826 --template_hash 661d064bbda1f2a133816b6d55da07c3 \
    --disk 64 --bid_price 0.1
```

---

## 6. Instance lifecycle + billing

### 6.1 States (per dashboard + docs)

| State | Meaning | Billed? |
|---|---|---|
| **Creating** | Vast initiating allocation | No |
| **Loading** | Downloading Docker image, starting container | **No** (per llms.txt — "Not charged during loading") |
| **Connecting** | Docker is up, Vast can't yet verify network | Yes |
| **Open / Connected / Running** | Operational | Yes — full rate |
| **Scheduling** | Trying to restart after stop; waiting for GPU availability | No (compute) — yes (storage) |
| **Inactive / Stopped** | Manually stopped; data preserved | **Storage only** (storage rate may be higher when stopped — verify per host) |
| **Offline** | Machine disconnected from Vast servers | No (compute) — yes (storage if your container exists) |
| **Exited / Unknown** | Container died | **Trap** per llms.txt: "if `actual_status` becomes `exited`, `unknown`, or `offline` it will never reach `running` — destroy and retry" |
| **Destroyed** | Resources released | Nothing |

### 6.2 Critical billing facts

- **Stopped instances continue accruing storage charges.** Destroy to stop the bill entirely.
- If host extends or expires your rental contract, instances may stop and data persists for **48h** — then deleted.
- Bandwidth (inet up + down) is per-GB, **host-set**. Some hosts include it free; some charge significantly. Check `inet_up_cost` + `inet_down_cost` on the offer before renting bandwidth-heavy workloads.
- Storage rate displayed via `storage_cost` in $/GB/month, applied per-second.

### 6.3 Poll-trap to embed in driver

Per the OpenAPI quirks doc, `wait_for_running()` should fail fast on these terminal states:

```python
TERMINAL_BAD = {"exited", "unknown", "offline"}

def wait_for_running(instance_id, timeout=300, interval=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        inst = get_instance(instance_id)
        status = inst.get("actual_status")
        if status == "running":
            return inst
        if status in TERMINAL_BAD:
            raise VastError(f"instance {instance_id} stuck in {status} — destroy and retry")
        time.sleep(interval)
    raise VastError(f"instance {instance_id} did not reach running within {timeout}s")
```

This is already implemented in `vast_provider.py::wait_for_running()`. Keep the terminal-set in sync if Vast adds new states.

---

## 7. SSH access

### 7.1 Direct vs Proxied

| Mode | Flag | Latency | Throughput | Constraints |
|---|---|---|---|---|
| **Direct** | `--ssh --direct` | low | high | Host must have `direct_port_count >= 1` and Vast assigns a forwarded port |
| **Proxied** | `--ssh` (no `--direct`) | higher | lower | Works on any host. Vast's proxy server in the path. |

Driver defaults: `--ssh --direct` when offer has `direct_port_count >= 1`, else fall back to proxied.

### 7.2 Connect

```bash
# Get the ssh URL (one line, port included):
vastai ssh-url 7835610
# → ssh://root@123.45.67.89:31337

# Connect:
ssh -p 31337 root@123.45.67.89

# File copy (use vastai copy which wraps scp):
vastai copy ./local.txt 7835610:/root/dest.txt
vastai copy 7835610:/root/src.txt ./local-dest.txt

# Direct SCP (note CAPITAL -P for port):
scp -P 31337 ./local.txt root@123.45.67.89:/root/dest.txt

# Port forward to a local Jupyter/UI:
ssh -p 31337 root@123.45.67.89 -L 8080:localhost:8080 -L 5000:localhost:5000
```

### 7.3 Key management

- Keys registered via `vastai create ssh-key` or via [cloud.vast.ai/manage-keys/](https://cloud.vast.ai/manage-keys/) apply ONLY to **new instances**.
- For an existing instance, use the instance-specific SSH key interface in the dashboard (or destroy + recreate).
- VM instances cannot have keys changed at all — recreate to swap.

---

## 8. Storage — container disk vs volumes

### 8.1 The two storage primitives

| Aspect | Container Disk (`--disk`) | Volume (`--create-volume` / `--link-volume`) |
|---|---|---|
| Location | Inside the running container | Host-mounted persistent storage |
| Survives stop? | Yes (billed continuously) | Yes (billed continuously) |
| Survives destroy? | **NO — wiped permanently** | YES — reattachable to a new instance |
| Survives machine outage? | N/A | NO — tied to a specific physical machine |
| Resizable? | No (fixed at create) | No (fixed at create) |
| Default size | 10 GB | 15 GB (with `--create-volume`) |
| Min size | 10 GB | varies by host |
| Max size | host capacity | host capacity |
| Cross-instance? | No | Yes (same machine only) |
| Use for | Build artifacts, cache, working data | Trained models, datasets, code repos, anything you'd hate to lose |

### 8.2 Volume create + link

```bash
# Search for offers that have volume-capable storage
vastai search offers 'disk_space>200 storage_cost<0.05'

# Create the volume against an offer ID:
vastai create volume 12345678 --volume-size 100 --volume-label "training-data"
# Returns volume_id

# Create instance AND new volume in one call:
vastai create instance 12345678 \
    --image pytorch/pytorch:2.4 --disk 40 --ssh --direct \
    --create-volume 12345678 --volume-size 100 \
    --mount-path /workspace

# OR link an existing volume:
vastai create instance 12345678 --image ... --disk 40 \
    --link-volume 87654321 --mount-path /workspace

# List + manage:
vastai list volumes
vastai clone-volume <id>
vastai delete volume <id>
```

### 8.3 Pricing
Storage billed at `storage_cost` $/GB/month, applied per-second (so a 100 GB volume at $0.05/GB/month = ~$0.000002/s = $0.07/day).

### 8.4 Driver model
`vast_provider.py::create_pod()` accepts `container_disk_gb=` (passed as `--disk`) and `volume_gb=` (currently maps to `--create-volume` against the same offer). For Fabrik's transient rentals, **container disk is sufficient** — volumes are an optimization for long-running training where you'd otherwise re-download model weights every restart.

---

## 9. Templates

A **template** is a saved `docker run` configuration: image, env, ports, onstart, disk default, provisioning script. Launch instances FROM templates so you don't repeat flags.

### 9.1 Vast-provided base images
- `vastai/base-image` — Ubuntu + CUDA + Caddy TLS + Instance Portal
- `vastai/pytorch` — PyTorch + CUDA + cuDNN + the above
- Both include faster cold boot (cached layers), built-in TLS, and the Instance Portal web auth

### 9.2 Public templates
```bash
vastai search templates                      # browse
vastai search templates 'pytorch'            # filter
```
Take the `template_hash` and pass to `create instance --template_hash <HASH>`.

### 9.3 Create your own
```bash
vastai create template \
    --name "fabrik-vllm-h100" \
    --image vllm/vllm-openai:latest \
    --disk 100 \
    --env '-p 8000:8000 -e VLLM_API_KEY=$VLLM_API_KEY' \
    --onstart-cmd 'vllm serve meta-llama/Llama-3.1-8B-Instruct'
# Returns: {"template_hash": "abc123...", "template_id": 12345}
```

Then:
```bash
vastai search offers '...' -o 'dph_total'    # find an offer
vastai create instance <offer_id> --template_hash abc123...
```

---

## 10. **Serverless** — the autoscaler

### 10.1 Mental model

Vast Serverless is Vast's managed layer on top of instances. You define an **endpoint** that autoscales a pool of **workers** to match incoming load. Same conceptual shape as RunPod Serverless or Modal Functions, but the workers are **regular Vast instances** under the hood — so you only pay for them, no platform markup.

```
                ┌──────────────────────────────────────────────┐
                │            Serverless Engine                 │
Client ─POST /route/─▶ (Vast-managed)  ─instance URL─▶ Worker  │
                │                                              │
                │       ┌─────────────┐                        │
                │       │  Endpoint   │ ◀ owns scaling policy  │
                │       └──┬───────┬──┘                        │
                │          │       │                           │
                │   ┌──────▼──┐ ┌──▼──────┐                    │
                │   │WorkerGrp│ │WorkerGrp│ ◀ defines WHAT runs│
                │   └────┬────┘ └─────────┘                    │
                │        │                                     │
                │   ┌────▼────┐ ┌─────────┐                    │
                │   │ Worker  │ │ Worker  │ ◀ actual Vast      │
                │   │(instance│ │(instance│   instances        │
                │   └─────────┘ └─────────┘                    │
                └──────────────────────────────────────────────┘
                                ▲
                                │ metrics (load, latency, queue depth)
                                │
                            PyWorker (runs on each worker)
```

### 10.2 Concepts

| Term | What it is | Lifetime |
|---|---|---|
| **Endpoint** | Top-level construct. Stable named entry point clients call. Owns the **scaling policy** (`max_workers`, `min_workers`, `target_util`, queue-time targets). | Persistent. |
| **Worker Group** | Belongs to an endpoint. Defines **what runs** on each worker: a template, hardware filters, search params, launch overrides. Most endpoints = 1 WG; multi-WG enables mixed-model serving or hardware A/B. | Persistent. |
| **Worker** | One GPU instance recruited by a WG. Created, activated, destroyed by the Serverless Engine based on measured load. | Ephemeral. |
| **PyWorker** | Small Python web server running INSIDE each worker. Proxies requests to the model server (vLLM, TGI, ComfyUI, etc), validates auth, reports load metrics back to the Engine. | Lives with the worker. |
| **Serverless Engine** | Vast-managed routing + scaling brain. | Always on (managed). |
| **Cold workers** | Provisioned-but-stopped workers ready to flip to active fast. Controls cold-start latency. | Held warm by `cold_workers` knob. |

### 10.3 Create an endpoint

```bash
vastai create endpoint \
    --endpoint_name "llama-prod" \
    --max_workers 20 \
    --target_util 0.9 \
    --cold_mult 2.5 \
    --cold_workers 5 \
    --max_queue_time 30.0 \
    --target_queue_time 10.0 \
    --inactivity_timeout 600
```

### 10.4 Endpoint knobs (all `vastai create endpoint` flags)

| Flag | Default | Meaning |
|---|---|---|
| `--endpoint_name TEXT` | (required) | Stable name. Multiple WGs can share an endpoint. |
| `--max_workers INT` | 20 | Hard cap on active workers. |
| `--target_util FRACTION` | 0.9 | Target capacity utilization. Engine recruits more workers when current util > this. |
| `--min_load PERF_UNITS` | 0.0 | Floor load (token/s for LLMs). Forces at least this much capacity even when idle. |
| `--min_cold_load PERF_UNITS` | 0.0 | Same as `--min_load` but counts cold workers. |
| `--cold_mult FLOAT` | 2.5 | Cold capacity target = `target_util × cold_mult` of hot. Higher = more cold workers held. |
| `--cold_workers INT` | 5 | Minimum cold workers when load is zero. |
| `--max_queue_time SEC` | 30.0 | Hard cap on per-worker queue time. Beyond → scale up. |
| `--target_queue_time SEC` | 10.0 | Engine's "comfort zone" for queue time. |
| `--inactivity_timeout SEC` | (off) | After this much zero-traffic time, scale to zero ACTIVE workers (cold workers persist). |

### 10.5 Create a worker group (defines what each worker runs)

```bash
vastai create workergroup \
    --endpoint_id 1234 \
    --template_hash 661d064bbda1f2a133816b6d55da07c3 \
    --test_workers 3 \
    --search_params 'gpu_ram>=23 num_gpus=1 gpu_name=RTX_4090 inet_down>200 direct_port_count>=2 disk_space>=64'
```

### 10.6 Worker group knobs

| Flag | Required? | Meaning |
|---|---|---|
| `--endpoint_id INT` or `--endpoint_name TEXT` | yes (one) | Which endpoint to attach to |
| `--template_hash HASH` | usually yes | Saved template; if used, `--search_params` can be auto-inferred from template's hardware reqs |
| `--template_id INT` | alt | Template ID instead of hash |
| `--search_params 'QUERY'` | yes if no template | Same syntax as `vastai search offers` (§5) — defines what hardware workers run on |
| `--launch_args 'ARGS'` | optional | Extra flags passed to `create instance` per worker. Example: `"--onstart onstart_wget.sh --env '-e KEY=val' --image foo --disk 64"` |
| `--gpu_ram FLOAT` | optional | GPU RAM estimate (helps autoscaler size workers; independent of search string) |
| `--test_workers INT` | default 3 | Workers to launch during WG init for benchmarking — the Engine measures these to set the perf baseline |
| `--cold_workers INT` | inherits endpoint | Per-WG override of cold pool size |
| `-n / --no-default` | flag | Skip default search params (`external=false rentable=true verified=true`) |

### 10.7 Routing — calling the endpoint from your client

```python
import os, requests, json

VAST_API_KEY = os.environ["VAST_API_KEY"]
ENDPOINT_NAME = "llama-prod"

# Step 1: Ask the engine for a worker
resp = requests.post(
    "https://run.vast.ai/route/",
    headers={"Authorization": f"Bearer {VAST_API_KEY}"},
    json={"endpoint": ENDPOINT_NAME, "cost": 256},  # cost = estimated perf units
).json()

if "url" not in resp:
    print("No workers available:", resp.get("status"))
else:
    worker_url = resp["url"]                        # http://1.2.3.4:8000
    auth_data = {
        "signature": resp["signature"],
        "cost": resp["cost"],
        "endpoint": resp["endpoint"],
        "reqnum": resp["reqnum"],
        "url": resp["url"],
        "request_idx": resp.get("__request_id"),
    }
    # Step 2: Call the worker with auth + payload
    result = requests.post(
        f"{worker_url}/generate",
        json={
            "auth_data": auth_data,
            "payload": {
                "inputs": "What is the answer to the universe?",
                "parameters": {"max_new_tokens": 256, "temperature": 0.7},
            },
        },
    ).json()
    print(result)
```

The `signature` is the engine's cryptographic proof that this client was routed legitimately — the PyWorker verifies it before forwarding to the model server.

### 10.8 PyWorker

The PyWorker is Vast's wrapper that lives inside each worker. Its job:

1. **Receive client request** (JSON with `auth_data` + `payload`)
2. **Verify auth signature** against the engine
3. **Forward payload** to the model server (vLLM `/generate`, TGI `/generate`, ComfyUI `/prompt`, etc.) on `localhost`
4. **Stream/format response** back to client
5. **Report metrics** (in-flight count, latency, queue depth) back to engine on a separate goroutine

#### Supported model servers (out of the box)
- **vLLM** (LLM throughput)
- **TGI** (Text Generation Inference)
- **ComfyUI** (image gen workflows)
- **hello-world** (template for custom)

#### Custom PyWorker
Fork `https://github.com/vast-ai/pyworker/`. The Engine handles auto-install during instance creation when your template includes a PyWorker script. You implement:
- `generate_payload()` — JSON shape your model server expects
- `format_response()` — JSON shape to return to client
- `metrics()` — what to report to the Engine

### 10.9 Pricing (the headline win)

> "Running a Vast Serverless endpoint doesn't incur extra cost, making it the cheapest and easiest way to manage your GPU fleet. **No tiers, no limits.**"

You pay for **the underlying worker instances** (per-second compute + storage + bandwidth), full stop. Compare to RunPod Serverless (per-execution charge + cold-start surcharge) and Modal (per-second + 1.5–1.75× region multiplier).

For Fabrik: when you need a managed-autoscale LLM endpoint and you're price-sensitive, **Vast Serverless is the cheapest path** if you accept marketplace variability. The driver's Phase 3 expansion will wire `fabrik gpu rent --provider vast --kind serverless` to spawn an endpoint + worker group on demand.

### 10.10 List + manage

```bash
vastai show endpoints
vastai show workergroups
vastai get-endpt-logs <endpoint_id>
vastai get-wrkgrp-logs <wg_id>

# Update knobs without recreating
vastai update endpoint <id> --max_workers 50 --target_util 0.85
vastai update workergroup <id> --cold_workers 10

# Lifecycle
vastai start deployment <id>                 # resume after stop
vastai stop deployment <id>                  # stop endpoint but keep config
vastai delete endpoint <id>                  # ALSO deletes attached worker groups
vastai delete workergroup <id>
```

---

## 11. REST API surface

### 11.1 Base URLs

| Service | URL | Used for |
|---|---|---|
| Console API | `https://console.vast.ai` | Management (instances, machines, templates, volumes, endpoints, billing) |
| Run | `https://run.vast.ai` | Serverless routing — `POST /route/` only |

### 11.2 Auth

All endpoints require:
```
Authorization: Bearer $VAST_API_KEY
```
Get keys at [cloud.vast.ai/manage-keys/](https://cloud.vast.ai/manage-keys/).

### 11.3 Endpoint inventory (from llms.txt + serverless OpenAPI)

#### Accounts
- `POST /api/v0/users/current/api-keys/` — create API key
- `GET /api/v0/users/current/api-keys/` — list keys
- `DELETE /api/v0/users/current/api-keys/<id>/` — delete key
- `POST /api/v0/users/current/ssh-keys/` — register SSH key
- `POST /api/v0/users/current/env-vars/` — create env var (encrypted, account-scoped — used for HF_TOKEN etc)
- `GET /api/v0/users/current/` / `PUT /api/v0/users/current/` — get/update user
- `POST /api/v0/subaccounts/` — create subaccount

#### Search
- `PUT /api/v0/bundles/` — **search offers** (yes, PUT, not GET — quirk)

#### Instances
- `PUT /api/v0/asks/<offer_id>/` — **create instance** (returns `{"new_contract": <id>}` per quirk)
- `GET /api/v0/instances/` — list user's instances
- `GET /api/v0/instances/<id>/` — get instance
- `PUT /api/v0/instances/<id>/` — manage (stop/start/label, body params decide action)
- `DELETE /api/v0/instances/<id>/` — destroy
- `POST /api/v0/instances/reboot/<id>/` — reboot
- `GET /api/v0/instances/logs/<id>/` — fetch logs

#### Volumes
- `PUT /api/v0/volumes/<offer_id>/` — create volume
- `GET /api/v0/volumes/` — list
- `DELETE /api/v0/volumes/<id>/` — delete

#### Templates
- `POST /api/v0/template/` — create
- `GET /api/v0/template/` — search
- `DELETE /api/v0/template/<id>/` — delete

#### Serverless
- `POST /api/v0/endptjobs/` — create endpoint
- `GET /api/v0/endptjobs/` — list endpoints
- `PUT /api/v0/endptjobs/<id>/` — update endpoint
- `DELETE /api/v0/endptjobs/<id>/` — delete endpoint (cascades to WGs)
- `POST /api/v0/autogroups/` — create workergroup
- `GET /api/v0/autogroups/` — list WGs
- `PUT /api/v0/autogroups/<id>/` — update WG
- `DELETE /api/v0/autogroups/<id>/` — delete WG
- `GET /api/v0/deployments/` — list deployments
- `POST /api/v0/deployments/<id>/start/` — start
- `POST /api/v0/deployments/<id>/stop/` — stop
- `GET /api/v0/endptjobs/<id>/logs/` — logs
- `GET /api/v0/autogroups/<id>/logs/` — WG logs
- `POST https://run.vast.ai/route/` — request worker assignment (note: different host)

#### Billing
- `GET /api/v0/invoices/` — list invoices
- `GET /api/v0/credit/` — current balance

### 11.4 Key API quirks (from Vast's own llms.txt)

> **Important.** These are non-obvious things that bite. The driver handles them; cite this section when writing tests.

1. **`gpu_ram` units differ:** CLI = GB; REST API = MB. CLI auto-converts. If you call the REST API directly: multiply by 1024.
2. **SSH keys must be registered BEFORE create:** VM instances can never recover from a wrong key; Docker instances can add post-create via the instance-SSH UI but not via API.
3. **`onstart` field has a 4048-char limit** — gzip + base64 for longer scripts.
4. **`POST /api/v0/asks/{id}/` returns `new_contract` as the instance ID**, NOT `id`. This is the most common API-integration bug.
5. **Poll trap:** if `actual_status` becomes `exited`, `unknown`, or `offline`, it will NEVER reach `running` — destroy and retry. The driver's `wait_for_running` checks for these explicitly.
6. **Search uses PUT, not GET** — the body carries the query.

---

## 12. Pricing — marketplace + spot mechanics

### 12.1 Headline rule
**There is no rate card.** Prices are host-set, dynamic, and surfaced live via `vastai search offers`. The driver's `HOURLY_USD_BY_PROVIDER["vast"]` floor estimates (verified 2026-06-16) are conservative — actual rates are usually lower.

### 12.2 Floor prices (approximate, on-demand verified, 2026-06-16)

| `gpu_name` | $/hr (floor) | Notes |
|---|---|---|
| RTX 3090 | $0.15–0.25 | Best $/DLPerf on Vast |
| RTX 4090 | $0.40–0.60 | Fabrik's `pod-rtx-4090` maps here |
| RTX A6000 | $0.50–0.70 | Good 48GB workstation card |
| A100 40GB SXM4 | $0.80–1.20 | |
| A100 80GB SXM4 | $1.20–1.60 | |
| H100 PCIe | $1.60–2.10 | |
| H100 SXM5 | $1.80–2.30 | |
| H200 | $2.50–3.50 | |
| L40S | $0.50–0.90 | |

**Interruptible (spot) prices are typically 50% lower.** Bid `--bid_price 0.10` against a $0.20/hr on-demand RTX 4090 and you might get it.

### 12.3 Cost components
- **GPU compute** — per-second, while running
- **Storage** — per-second, while instance exists (running OR stopped). $/GB/month via `storage_cost`.
- **Bandwidth** — per-byte. Inbound + outbound. Highly host-variable. See `inet_up_cost` / `inet_down_cost` per offer. **Set a cap with `disk_space>X inet_up_cost<0.05` style filters.**
- **Reserved discount** — up to 50% off on-demand with pre-pay
- **Interruptible bid** — 50%+ cheaper than on-demand if you can absorb preemption

### 12.4 Top-up + free tier
- **Minimum top-up: $5** (verified 2026-06-16). Pay via credit card.
- **No persistent free tier.** Occasional promo credits.
- For Fabrik smoke tests: $5 buys 10–25 hours of GPU time depending on tier. Plenty.

### 12.5 Serverless pricing rule (repeat from §10.9, for skimmers)
> "Running a Vast Serverless endpoint doesn't incur extra cost." You pay only the underlying worker instance rates. **No platform fee.**

---

## 13. How Fabrik uses Vast

### 13.1 Driver: `src/fabrik/drivers/vast_provider.py`
- `VastClient.__init__`: reads `VAST_API_KEY` from env / `.env.sysadmin`.
- `create_pod(gpu_type_id, image_name, ...)`: 2-phase — `_request("PUT", "/bundles/", body={"q": search_query})` to find an offer matching the requested GPU + filters, then `_request("PUT", f"/asks/{offer_id}/", body={...})` to claim it. Returns `{"id": new_contract, ...}` — handles the `new_contract` quirk (§11.4).
- `wait_for_running()`: polls `GET /instances/<id>/`, checks `actual_status` against `{"running"}` vs terminal-bad set `{"exited", "unknown", "offline"}` (§6.3 poll-trap).
- `destroy_pod()`: `DELETE /instances/<id>/`.
- `list_pods()`: `GET /instances/`, filters by `FABRIK_SESSION_ID` env tag (C4 invariant — never touches foreign instances).
- `billing_pods()`: scrapes per-instance hourly rate from `/instances/<id>/` response + multiplies by wall-clock; Vast has no separate billing API per llms.txt.
- Serverless methods (`create_endpoint`, `run_endpoint_sync`, `destroy_endpoint`): **Phase 3 work** — currently raise `NotImplementedError`.

### 13.2 GPU type translation
`VAST_GPU_NAMES` in [`vast_provider.py`](../../src/fabrik/drivers/vast_provider.py):
```python
VAST_GPU_NAMES = {
    "pod-h100": "H100_SXM5",
    "pod-h100-pcie": "H100_PCIE",
    "pod-h200": "H200",
    "pod-a100": "A100_SXM4",
    "pod-a100-sxm": "A100_SXM4",
    "pod-l40s": "L40S",
    "pod-rtx-4090": "RTX_4090",
    # "serverless" is NOT in this map — Vast serverless is Phase 3
}
```

### 13.3 When the orchestrator routes here
`selection_advice(kind, hours, utilization_rate, needs_checkpointing, needs_serverless)` in [`gpu_rent.py`](../../src/fabrik/orchestrator/gpu_rent.py):
- `needs_checkpointing=True` + spot-OK → **recommend Vast** (interruptible) for the cost win
- Vast is also the fallback when RunPod doesn't carry the GPU (e.g. RTX 3090, A6000)
- `needs_serverless=True` → **does NOT route to Vast yet** (Phase 3) — currently → RunPod

### 13.4 Phase 3 expansion (not yet implemented)
- `create_endpoint()` against `POST /api/v0/endptjobs/` with auto-managed WorkerGroup
- Custom Fabrik PyWorker fork in `fabrik-lib/vast-pyworker/` reusable module
- `fabrik gpu rent --provider vast --kind serverless --workergroup-template <hash>` end-to-end
- Cost telemetry: hook into endpoint logs API to track per-request cost vs RunPod / Modal serverless

---

## 14. Common pitfalls + workarounds

| Symptom | Cause | Fix |
|---|---|---|
| `create instance` returns success but instance never reaches `running` | Poll trap (status went `exited` / `unknown` / `offline`) | Destroy + retry on a different offer. Driver's `wait_for_running` raises immediately. |
| Instance billed while stopped | Storage charges continue when stopped | Destroy completely to stop bill. |
| Instance vanished after 48h | Rental contract expired and host didn't extend | Set rental duration filter (`duration > N`) in search; for long jobs use Reserved. |
| SSH key not accepted | Key wasn't registered BEFORE create | Register via `vastai create ssh-key`, then create fresh instance. Existing instances need per-instance SSH UI. |
| `gpu_ram` mismatch between docs/SDK | CLI uses GB, REST API uses MB | Driver auto-handles. If hand-rolling REST: × 1024. |
| Worker stays in "Loading" forever | Image too large, host bandwidth-throttled, OR HF_TOKEN missing for gated model | Set `HF_TOKEN` via account env var (per [serverless quickstart](https://docs.vast.ai/guides/serverless/quickstart)). Check `inet_down` on offer ≥ 200 Mbps. |
| Wildly variable per-host pricing | Marketplace dynamics | Filter `verified=true reliability>0.95` for stability; use `dlperf_usd` sort for best price-perf. |
| Bid won but instance preempted within minutes | Interruptible — outbid by on-demand or higher bidder | Re-bid higher with `vastai change-bid <id> <new>` OR checkpoint frequently. |
| Serverless endpoint scales to zero but cold-start is 30+s | `cold_workers` set too low, or image too large | Raise `--cold_workers 10`, use smaller image, bake model into image |
| `route` returns no URL | All workers loading / no spare capacity | Engine auto-recruits more; raise `--max_workers` and `--cold_mult` |

---

## 15. Reference links

- [Vast Docs Home](https://docs.vast.ai/)
- [llms.txt](https://docs.vast.ai/llms.txt) — full doc index for crawl-discoverability
- [API Reference](https://docs.vast.ai/api-reference/introduction)
- [CLI Hello World](https://docs.vast.ai/cli/hello-world)
- [Serverless Quickstart](https://docs.vast.ai/guides/serverless/quickstart)
- [PyWorker repo](https://github.com/vast-ai/pyworker)
- [Vast CLI repo](https://github.com/vast-ai/vast-cli)
- [Pricing dashboard (live)](https://cloud.vast.ai/create/)
- [API keys management](https://cloud.vast.ai/manage-keys/)
- [Console](https://cloud.vast.ai/)

---

## §A — Full doc index snapshot (verified 2026-06-16)

Categories present in llms.txt (246 total pages):

- **api-reference/** — REST API per-endpoint docs (`accounts`, `billing`, `instances`, `machines`, `search`, `serverless`, `team`, `templates`, `volumes`)
- **cli/** — CLI authentication, permissions, rate limits, templates intro, hello-world
- **cli/reference/** — one page per subcommand (~80 pages: every flag table)
- **guides/** — concepts, get-started (quickstart, agents), instances (choosing, connect, storage, virtual-machines), serverless (quickstart, overview), templates (introduction)
- **host/** — host-side (machine operators) — out of scope for Fabrik
- **examples/** — vLLM, ComfyUI, Stable Diffusion, agent frameworks
- **openapi.yaml** — full OpenAPI spec for Console API
- **two-factor-authentication-endpoints** — 2FA flow

When this doc falls behind, curl `docs.vast.ai/llms.txt` and re-grep for new paths. The doc URLs follow `https://docs.vast.ai/<category>/<page>.md` and serve clean markdown (much better than the HTML render — use the `.md` extension directly).
