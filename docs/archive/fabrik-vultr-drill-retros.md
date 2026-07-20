# fabrik-vultr drill retrospectives (archived 2026-07-20)

> Excised from docs/reference/fabrik-vultr.md — dated drill measurement history (changelog-in-doc); the living quick reference stays in reference/.

## Live-run measurements (vps4 drill, 2026-06-08)

End-to-end provision → destroy of a real billed test spoke (`fabrik vultr provision vps4 -y` → `fabrik vultr destroy vps4 --reverse-fleet-add -y`). Drove out 4 real bugs in the process — see "What broke + what we fixed" below.

| Phase | Wall-clock | Cost |
| :--- | :--- | :--- |
| Vultr create → instance active + IP assigned | 60–70s | — |
| sshd ready after `wait_for_active` returns | 10–25s (post-fix; hung indefinitely pre-fix) | — |
| `bootstrap-vps.sh` end-to-end (15 steps: SSH harden, UFW+fail2ban, Docker, Wireguard, mesh peer reg, DNS, monitoring, Traefik, sysadmin pack, aro-wake) | ~4m 36s | — |
| `destroy --reverse-fleet-add` (gatus → prom → backrest → DNS → wg0 → instance) | ~24s | — |
| **Round-trip total** (provision + destroy, no debugging) | **~5–6 min** | **~$0.06** (vc2-2c-4gb @ $24/mo × 10/(30×24×60)) |

Fleet-add **verified live** after provision:

- ✅ Mesh: vps1 ↔ vps4 over wg0, `ping 10.99.0.4` = 1.25ms
- ✅ DNS: `vps4.ocoron.com` + `*.vps4.ocoron.com` → 45.77.68.63 (via Cloudflare auth NS)
- ✅ Loki: host label `vps4` present, promtail shipping logs from vps4
- ✅ Traefik: container up, gzip middleware published
- ✅ aro-wake systemd unit installed
- ⚠️ Prometheus aro-wake job: vps4 NOT added at the time of this drill (14 → 14 targets) — **this gap is now CLOSED**: `provision` auto-registers the target + Gatus endpoint via `_register_observability` (see "What this does not close").

## What broke + what we fixed (drill #2 — 2026-06-08)

The drill caught 4 real bugs that the unit tests had not surfaced. All four were fixed in the same session and the live drill validated the fixes:

1. **`fabrik vultr provision` had no `-y/--yes` flag**, so `click.confirm("Proceed?")` read from `/dev/tty` and hung when piped. Added `-y` flag with explicit "automation use only" doc string.
2. **DNS driver defaulted to the dead `coolify` docker network**, breaking `--reverse-fleet-add` DNS unwind in a fresh operator environment that hadn't set the env override. Changed default to `fabrik` (the post-Coolify network). +3 unit tests in [`tests/drivers/test_dns_client.py`](../../tests/drivers/test_dns_client.py).
3. **`provision` had no sshd-ready poll** between `wait_for_active` (Vultr-API "active") and the bootstrap call. There's a 10–30s gap where Vultr reports active but cloud-init hasn't bound sshd — bootstrap-vps.sh's BatchMode preflight failed on the first try. Added `_wait_for_ssh()` polling up to 120s. +1 regression test.
4. **`bootstrap-vps.sh` step_02 aborted on `sudo ufw enable`**: kernel reloads the netfilter ruleset and the active SSH session drops with rc=255 (benign — port 22 is allowed and the next session connects fine), but `set -euo pipefail` killed the whole bootstrap. Added `|| true` + a 2s settle + a fresh-session re-probe via the verify block. Result: step_02 completed cleanly on the next run.

Also surfaced (NOT yet fixed — recorded for follow-up):

- **`bootstrap-vps.sh` step_04 silently removes ufw** on Ubuntu 24.04 because `iptables-persistent` conflicts with ufw at the firewall-management layer. step_15's aro-wake UFW rules then fail (`sudo: ufw: command not found`). vps2/vps3 don't hit this because they were bootstrapped pre-conflict.
- **`reverse_fleet_destroy` wg0 peer removal used invalid `wg set wg0 peer-remove-by-ip <ip>` syntax** (no such subcommand). Silently failed under `|| true` and reported "ok" — leaving a stale peer behind on vps1's wg0 after destroy. Verified live on vps4: peer still present after `destroy --reverse-fleet-add` succeeded. Fixed: look up the pubkey by allowed-ip match, then `wg set wg0 peer <pubkey> remove`.
- **`reverse_fleet_destroy` DNS step returns false-negative** when site-provisioner replies 500 for "record not found" — DNS records are actually removed, but `_try` records `error`. Cosmetic; cleanup is correct.
