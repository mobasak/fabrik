# WSL network heartbeat

A user systemd timer inside WSL proves WSL's own network to the operator's Windows NAT watchdog, so the
watchdog no longer launches `wsl.exe` to probe it (W-960d68a8).

## Why

The Windows task `WSL-NatWatchdog` (`C:\Users\user\hotel-wifi\wsl-nat-watchdog.ps1`, D-773) used to
check WSL's network by running `wsl.exe -d Ubuntu-24.04 -u ozgur -e curl … msftconnecttest` every
interval. Measured on 2026-10-29 (W-97557e65, the measurements are in commit 97066cd1e's message): about one run in seven, the session's relay `/init`
never ran curl, and the orphaned root relay kept three hv_sock channels open to the host forever:
641 channels from about 210 relays. Each channel pins an unmovable 512 KB ring. That fragmentation is
why a new `wsl.exe` session eventually cannot get its 512 KB ring and hangs with no prompt
(W-1d9ba411).

## What runs

- `scripts/sysadmin/wsl_net_heartbeat.sh` runs every 60 s, from `wsl-net-heartbeat.timer`. It runs
  `curl -q -sSf -m 5 -o /dev/null http://www.msftconnecttest.com/connecttest.txt`, the same success
  rule as the old probe (any HTTP status below 400; `-q` ignores a user's `~/.curlrc`), then sorts
  curl's exit code three ways:
  1. **0** (the probe fetched): touches both `C:\Users\user\hotel-wifi\wsl-net-ran` and `wsl-net-ok`.
  2. **a network failure** (curl exit 5, 6, 7, 22, 28, 35, 52, 55 or 56): touches only `wsl-net-ran`,
     writes curl's reason to the journal, and exits 0. An outage is not a fault, so the unit is not
     marked failed every minute of one.
  3. **anything else** (a malformed URL, curl missing, an option error): a local fault that an adapter
     restart cannot cure. Neither file moves and the run exits 1, so the watchdog reads the heartbeat
     as broken, never as "no network".
- A failed write exits nonzero too.
- `/mnt/c` is a 9p mount, not the NAT network, so `wsl-net-ran` keeps changing while the NAT is dead.

Check it: `systemctl --user list-timers wsl-net-heartbeat.timer` and
`journalctl --user -u wsl-net-heartbeat.service -n 20`.

## Install (from the main checkout, after merge)

```bash
bash /opt/fabrik/scripts/sysadmin/install_wsl_net_heartbeat_timer.sh
```

The installer refuses unless linger is on, the script exists in the main checkout, and
`systemd-analyze --user verify` is silent. It deletes nothing.

## Hand-off order

1. Install the timer (above).
2. From PowerShell, read both files' `LastWriteTime` twice, about two minutes apart:
   `Get-Item C:\Users\user\hotel-wifi\wsl-net-ran, C:\Users\user\hotel-wifi\wsl-net-ok | Select Name, LastWriteTime`.
   Both must move. This confirms Windows sees the WSL writes.
3. Only then edit the watchdog (below), and restart its task so the edit takes effect:
   `Stop-ScheduledTask -TaskName WSL-NatWatchdog; Start-ScheduledTask -TaskName WSL-NatWatchdog`.
   The task is one long-running loop started at logon, so a file edit does nothing until it restarts.

## The watchdog edit (the operator's file)

The watchdog reads whether each file's `LastWriteTime` CHANGED since its previous check, never the
file's age. That works whichever clock stamps a 9p write, the WSL clock or the Windows one, and a WSL
clock can lag Windows after sleep or resume.

- `wsl-net-ran` unchanged on two checks in a row: the heartbeat is broken. The watchdog toasts once
  and never restarts the adapter.
- `wsl-net-ran` changed but `wsl-net-ok` unchanged: WSL has no network. The watchdog counts a fail,
  as before.
- A missing file counts as unchanged.

The heartbeat's longest gap is 60 s, plus 5 s timer accuracy, plus 5 s for curl, plus the write. It
must stay below `$Interval` (120 s), or a live WSL can read as unchanged.

Replace `WslInternet` (lines 22-26) with:

```powershell
$RanFile = "$PSScriptRoot\wsl-net-ran"
$OkFile  = "$PSScriptRoot\wsl-net-ok"
function Stamp($f) { if (Test-Path $f) { (Get-Item $f).LastWriteTimeUtc.Ticks } else { $null } }
function SeedHeartbeat { $script:LastRan = Stamp $RanFile; $script:LastOk = Stamp $OkFile }
function WslHeartbeat {
    # 'ok' | 'no-network' | 'broken': a CHANGE since the previous check, never an age
    $ran = Stamp $RanFile; $ok = Stamp $OkFile
    if ($null -eq $ran -or $ran -eq $script:LastRan) { $state = 'broken' }
    elseif ($null -ne $ok -and $ok -ne $script:LastOk) { $state = 'ok' }
    else { $state = 'no-network' }
    $script:LastRan = $ran; $script:LastOk = $ok
    $state
}
```

Replace the start of the loop (lines 36-40) with:

```powershell
$fails = 0; $tries = 0; $lastAct = [datetime]::MinValue; $wasDown = $false; $broken = 0
Log "watchdog started (pid $PID)"
SeedHeartbeat; Start-Sleep $Interval
while ($true) {
    if (-not (WslRunning)) { $fails = 0; $broken = 0; SeedHeartbeat; Start-Sleep $Interval; continue }
    $hb = WslHeartbeat
    if ($hb -eq 'broken') {
        $broken++; $fails = 0
        if ($broken -eq 2) { Log 'WSL heartbeat not updating - systemctl --user status wsl-net-heartbeat.timer'; Toast 'WSL heartbeat stopped' 'The WSL heartbeat is not updating. The NAT watchdog is paused.' }
        Start-Sleep $Interval; continue
    }
    $broken = 0
    if ($hb -eq 'ok') {
```

The rest of the loop stays as it is: the `elseif (HostInternet)` branch handles `no-network`.

**An option this change does not build.** Before `RestartNat`, the watchdog could run the old
`wsl.exe … curl` probe once to confirm the outage. That would leak at most one relay per suspected
outage, in exchange for fewer adapter restarts on a false reading. It is the operator's choice.

## Reclaiming the relays already leaked

Only root can end the existing orphaned relays. The safe way is `wsl --shutdown` at a quiet moment,
which ends every WSL session.
