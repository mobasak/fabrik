# Research ledger — /hibernate full guarantee (W-6e656dac), 2026-10-21

Six `fabrik-researcher` seats, two waves, every returned fact filed whole before the synthesis in
`docs/superpowers/specs/2026-10-21-hibernate-full-guarantee-design.md` (§ External dependencies and § Chosen approach).
Engines: exa web_fetch (raw, may be crawl cache), firecrawl_scrape maxAge 0 (live; ran out of credits mid-wave),
WebSearch, WebFetch (an answer about a page, never quoted). brave-search failed as an arm (422 SUBSCRIPTION_TOKEN_INVALID).

## Wave 1a — U1 Claude Code session resume

| id | source | fact | url | disposition |
|---|---|---|---|---|
| cc-1 | sessions page (exa) | `--resume <id or name>` resumes that session directly from any directory; `--continue` the newest in the cwd; `-p --continue` includes `-p`/SDK sessions | https://code.claude.com/docs/en/sessions | USED → § External dependencies, Claude Code row; § Chosen approach L4 |
| cc-2 | sessions page (exa) | resume restores messages, tool calls and results, the model, `--agent` and the permission mode; not `--mcp-config`, `--settings`, `--plugin-dir`, `--fallback-model`, `--add-dir`; background Bash and Monitor tasks are not restored | https://code.claude.com/docs/en/sessions | USED → § Chosen approach L4 (the self-watch must be re-armed after a resume) |
| cc-3 | sessions page (exa) | "Interrupted tool calls: a tool that was still running when the previous process ended ... doesn't finish or get rerun when you resume ... unless `CLAUDE_CODE_RESUME_INTERRUPTED_TURN` is set" | https://code.claude.com/docs/en/sessions | USED → § Chosen approach L4 |
| cc-4 | cli-reference (firecrawl) | `--fork-session` with `--resume`/`--continue` creates a new session id | https://code.claude.com/docs/en/cli-reference | REJECTED — read whole: forking would split one agent into two transcripts, the opposite of a resume |
| cc-5 | sessions page (exa) | transcripts are JSONL at `~/.claude/projects/<project>/<session-id>.jsonl`; `cleanupPeriodDays` default 30 | https://code.claude.com/docs/en/sessions | USED → § What exists today (the hub prunes after 3 days, D-736) |
| cc-6 | errors page (WebFetch) | transient failures retry up to 10 times with exponential backoff before an error; a failure partway through a response is not always retried | https://code.claude.com/docs/en/errors | USED → § Chosen approach L1 |
| cc-7 | env-vars (WebFetch + firecrawl) | `CLAUDE_CODE_RETRY_WATCHDOG=1` retries 429/529 indefinitely and on v2.1.199+ raises other transient retries to 300 (~3 h), removing the cap of 15 | https://code.claude.com/docs/en/env-vars | USED → § Chosen approach L1 |
| cc-8 | errors page (WebFetch) | a connection broken by the computer sleeping is detected and labelled "Connection lost while your computer was asleep" | https://code.claude.com/docs/en/errors | USED → § Why this exists |
| cc-9 | headless (WebFetch) | SIGTERM on a `-p` run kills the Bash process tree, records it killed, runs SessionEnd, exits 143 | https://code.claude.com/docs/en/headless | USED → § Rejected alternatives (killing workers at the deadline) |
| cc-10 | cross-session messaging (WebFetch + firecrawl) | each session binds a per-session Unix inbox socket; an idle session starts a new turn with a message; a busy one reads it between tool calls; delivery governed by `crossSessionInbound` | https://code.claude.com/docs/en/cross-session-messaging | USED → § Rejected alternatives (socket wake instead of the self-watch) |
| cc-11 | sessions page (exa) | "A prompt you pass on the command line, as in `claude --resume <id> "check the tests too"`, goes to the session as its next turn first" — in the section on resuming a still-running BACKGROUND session (spec review pass 1, S3) | https://code.claude.com/docs/en/sessions | REJECTED — read whole: the sentence governs a running background session that `claude attach` opens, not an interactive relaunch; cc-16 is the interactive contract |
| cc-12 | hooks (firecrawl) | SessionStart `source` is startup, resume, clear, compact or fork; resume carries `seconds_since_last_response` on v2.1.251+ | https://code.claude.com/docs/en/hooks | USED → § Chosen approach L4 |
| cc-13 | hooks (WebFetch) | Notification types `quota_auto_resume_fired`/`_stale`/`_disabled` exist | https://code.claude.com/docs/en/hooks | REJECTED — read whole: names a quota auto-resume feature whose docs were not read; it resumes after a quota wait, not after a host sleep |
| cc-14 | sessions page (exa) | a background subagent that ended with the previous process shows in the resumed transcript as a note that it did not finish; no turn starts from it | https://code.claude.com/docs/en/sessions | USED → § Chosen approach L2 (abandoned seats) |
| cc-16 | cli-reference (WebFetch, spec review pass 1) | the commands table: `claude -r "<session>" "query"` — "Resume session by ID or name", example `claude -r "auth-refactor" "Finish this PR"` | https://code.claude.com/docs/en/cli-reference | USED → § Chosen approach L4; § External dependencies |
| cc-17 | sessions page (exa, spec review pass 1) | terminal resume does not restore `bypassPermissions`: "The permission mode a new session would start in" | https://code.claude.com/docs/en/sessions | REJECTED — read whole: this box's default mode is `auto` (settings `permissions.defaultMode`), so a resumed builder starts in the same mode as a fresh one |
| cc-18 | env-vars (WebFetch, spec review pass 1) | the watchdog requires v2.1.186+; on v2.1.199+ other transient errors retry 300 times (~3 h); a 429 reporting a spend limit or exhausted usage credits fails at once (v2.1.239+) | https://code.claude.com/docs/en/env-vars | USED → § Chosen approach L1 |
| cc-15 | sub-agents (WebFetch) | subagent transcripts persist under `<session>/subagents/agent-<id>.jsonl`; a subagent can be resumed by resuming the session and messaging it; Explore and Plan are one-shot | https://code.claude.com/docs/en/sub-agents | USED → § Chosen approach L2 (abandoned seats) |

## Wave 1a — U2 Windows hibernation and the WSL2 guest

| id | source | fact | url | disposition |
|---|---|---|---|---|
| wsl-1 | microsoft/WSL #5324 (firecrawl) | Microsoft member: "We made a previous change to send clock sync packets when the system resumes from sleep" — the guest is alive at resume | https://github.com/microsoft/WSL/issues/5324 | USED → § External dependencies, WSL row |
| wsl-2 | hv_utils patch (firecrawl) | "Hyper-V hosts can omit the _SYNC flag ... the guest may fail to update its time-of-day to account for the period when it was suspended" | https://lore.kernel.org/linux-hyperv/20231127213524.52783-1-pmartincic@linux.microsoft.com/T/ | USED → § Open unknowns U1 (wall clock may lag) |
| wsl-3 | #10006 (firecrawl) | the clock-drift megathread is Closed; a user reports the fix on WSL 2.1.4.0 / kernel 5.15.146.1-2 | https://github.com/microsoft/WSL/issues/10006 | USED → § Open unknowns U1 |
| wsl-4 | LKML RFC (exa) | BOOTTIME − MONOTONIC "did not work well on VM environment since most VMs are pausing the VM guests" | https://lore.kernel.org/lkml/ | DUPLICATE of r-1 |
| wsl-5 | WebSearch snippets | NAT networking can stall after resume; DNS fails first | https://learn.microsoft.com/en-us/answers/questions/1609423 | USED → § Chosen approach L3 (network gate before the wake) |
| wsl-6 | bounded search (WebSearch, 1 query) | no source shows a sleep or resume notification reaching the WSL guest | https://learn.microsoft.com/en-us/windows/wsl/ | USED → § Rejected alternatives (pre-sleep hooks) |
| wsl-7 | PBT_APMSUSPEND (exa) | "The system allows approximately two seconds for an application to handle this notification" | https://learn.microsoft.com/en-us/windows/win32/power/pbt-apmsuspend | USED → § Rejected alternatives (Windows-side pre-sleep hook) |
| wsl-8 | forum (exa) | Kernel-Power 506 marks Modern Standby entry; a local action ran seconds after standby, a network action only after wake | https://learn.microsoft.com/en-us/answers/ | DUPLICATE of wsl-7 |
| wsl-9 | wsl-config (firecrawl) | `[wsl2] vmIdleTimeout` default 60000 ms; `[general] instanceIdleTimeout` default 15000, -1 disables | https://learn.microsoft.com/en-us/windows/wsl/wsl-config | USED → § Open unknowns U4 |
| wsl-10 | #13291 (exa) | Microsoft: "You also need to set: [general] InstanceIdleTimeout=-1 For the distribution itself to keep running" | https://github.com/microsoft/WSL/issues/13291 | USED → § Open unknowns U4 |

## Wave 1a — U3 cloud VM hibernation and Linux pre-sleep hooks

| id | source | fact | url | disposition |
|---|---|---|---|---|
| vm-1 | EC2 overview (firecrawl) | "Amazon EC2 signals the operating system to perform hibernation (suspend-to-disk). The hibernation freezes all of the processes, saves the contents of the RAM to the EBS root volume" | https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-hibernate-overview.html | USED → § Chosen approach L6 |
| vm-2 | EC2 (firecrawl) | trigger `aws ec2 stop-instances --hibernate`; max 60 days; Linux RAM < 150 GiB; public IPv4 changes on start; a failed hibernate falls back to a normal shutdown | https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/hibernating-instances.md | USED → § Chosen approach L6 |
| vm-3 | EC2 prerequisites (exa) | hibernation cannot be enabled on an existing instance; root volume encrypted | https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/hibernating-prerequisites.html | USED → § Lifecycle (cloud adoption) |
| vm-4 | GCE (exa) | in-guest `systemctl suspend` is ignored; suspend max 60 days; memory > 208 GB not allowed | https://docs.cloud.google.com/compute/docs/instances/suspend-resume-instance | USED → § Chosen approach L6 |
| vm-5 | Azure (exa) | "Applications and processes that were previously running in your VM resume from the state prior to hibernation"; sizes up to 64 GB | https://learn.microsoft.com/en-us/azure/virtual-machines/hibernate-resume | USED → § Chosen approach L6 |
| vm-6 | systemd-inhibit(1) (exa) | a delay lock "can only delay the requested operations for a limited time"; only for sleep and shutdown | https://www.freedesktop.org/software/systemd/man/latest/systemd-inhibit.html | USED → § Rejected alternatives (delay inhibitor) |
| vm-7 | logind.conf(5) (firecrawl) | InhibitDelayMaxSec "Defaults to 5" | https://www.freedesktop.org/software/systemd/man/latest/logind.conf.html | USED → § Rejected alternatives (delay inhibitor) |
| vm-8 | systemd-suspend.service(8) (exa) | system-sleep executables run with `pre`/`post`; `user.slice` is frozen while they run | https://www.freedesktop.org/software/systemd/man/latest/systemd-suspend.service.html | USED → § Rejected alternatives (system-sleep hook) |
| vm-9 | inhibit wiki (exa) | PrepareForSleep "will only be sent out for suspend/resume cycles done via logind" | https://www.freedesktop.org/wiki/Software/systemd/inhibit/ | USED → § Rejected alternatives (delay inhibitor) |
| vm-10 | Azure (exa) | "If you are using any UVM-enabled compute applications, we recommend idling the application before initiating hibernation" | https://learn.microsoft.com/en-us/azure/virtual-machines/hibernate-resume | USED → § Chosen approach L6 (drain first, then the API call) |

## Wave 1c — D graceful drain with a deadline

| id | source | fact | url | disposition |
|---|---|---|---|---|
| d-1 | K8s lifecycle hooks (exa, search) | "The Pod's termination grace period countdown begins before the `PreStop` hook is executed" | https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/ | USED → § Chosen approach L2 (the deadline counts from the mark) |
| d-2 | K8s (exa) | long preStop work makes sense "such as when saving state prior to stopping a Container" | https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/ | USED → § Chosen approach L2 |
| d-3 | 12-Factor IX (exa) | "For a worker process, graceful shutdown is achieved by returning the current job to the work queue" and jobs reentrant or idempotent | https://12factor.net/disposability | USED → § Chosen approach L2 (abandoned seat → RESUME note) |
| d-4 | Sidekiq Deployment (exa) | TSTP as early as possible, TERM as late as possible; "TSTP tells Sidekiq to stop pulling new work and finish all current work" | https://github.com/sidekiq/sidekiq/wiki/Deployment | USED → § Chosen approach L2 (two-phase deadline) |
| d-5 | Sidekiq (exa) | "If any jobs are still running when the timeout is up, Sidekiq will push those jobs back to Redis" | https://github.com/sidekiq/sidekiq/wiki/Deployment | USED → § Chosen approach L2 |
| d-6 | Celery workers (exa) | soft shutdown is "a time limited warm shutdown, initiated just before the cold shutdown"; executing tasks are lost unless `acks_late` | https://docs.celeryq.dev/en/stable/userguide/workers.html | USED → § Chosen approach L2 |
| d-7 | Temporal long-running activity (exa, search) | "The heartbeat details are persisted and available to retry attempts, enabling resumption from the last checkpoint" | https://docs.temporal.io/design-patterns/long-running-activity.md | USED → § Chosen approach L1 (step-boundary checkpoint) |
| d-8 | LangGraph persistence (exa, search) | in-memory checkpointers lose every checkpoint on restart | https://docs.langchain.com/oss/python/langgraph/persistence.md | USED → § Chosen approach L1 (checkpoints on disk) |
| d-9 | Sidekiq API (exa) | `ProcessSet` busy counts update every 5 s; "It is not millisecond-precise" | https://github.com/sidekiq/sidekiq/wiki/API | USED → § Chosen approach L2 (status reads twice) |
| d-10 | (none) | no source gives a soft/hard deadline ratio | https://github.com/sidekiq/sidekiq/wiki/Deployment | USED → § Decisions taken (T-3 is the operator's number) |

## Wave 1c — R auto-resume after suspend

| id | source | fact | url | disposition |
|---|---|---|---|---|
| r-1 | systemd.timer (exa) | `OnClockChange=` fires when CLOCK_REALTIME jumps relative to CLOCK_MONOTONIC | https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html | USED → § Rejected alternatives (timer trigger); the tick's wall-gap detector stays |
| r-2 | Electron powerMonitor (exa) | GUI apps use the OS 'resume' event | https://www.electronjs.org/docs/latest/api/power-monitor | REJECTED — read whole: no such event reaches a WSL guest (wsl-6), so the GUI-app pattern does not apply here |
| r-3 | AWS Architecture Blog (exa, search) | jittered backoff "should be considered a standard approach for remote clients"; Full Jitter beats Equal | https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/ | USED → § Chosen approach L3 (the self-watch's storm jitter stays) |
| r-4 | (none) | no source documents an "N consecutive probe successes" gate | https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/ | USED → § Decisions taken (MESH_UP_STREAK=3 stays a box choice, D-897) |
| r-5 | tmux-resurrect (exa, search) | "Only a conservative list of programs is restored by default" | https://github.com/tmux-plugins/tmux-resurrect | USED → § Rejected alternatives (tmux-resurrect) |
| r-6 | tmux-continuum (exa) | saves every 15 min; restore only on tmux server start; autosave breaks when a theme overwrites `status-right` | https://github.com/tmux-plugins/tmux-continuum | USED → § Rejected alternatives (tmux-resurrect) |
| r-7 | loginctl (exa) | with linger "a user manager is spawned for the user at boot" | https://www.freedesktop.org/software/systemd/man/latest/loginctl.html | USED → § Chosen approach L4 (precondition) |
| r-8 | Anthropic engineering (exa, search) | "each new session begins with no memory of what came before"; the fix is a progress file plus git history read first | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents | USED → § Chosen approach L4 (seed first, transcript second, session-recall third) |
| r-9 | Anthropic engineering (exa) | compaction "doesn't always pass perfectly clear instructions to the next agent" | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents | USED → § Chosen approach L4 |

## Wave 1c — M memory control

| id | source | fact | url | disposition |
|---|---|---|---|---|
| m-1 | cgroup-v2 (exa highlights, search) | memory.high throttles and "never invokes the OOM killer"; memory.max is the hard limit and OOM-kills inside the cgroup | https://docs.kernel.org/admin-guide/cgroup-v2.html | USED → § Chosen approach L5 |
| m-2 | cgroup-v2 (exa) | "Over-committing on high limit ... and letting global memory pressure to distribute memory according to usage is a viable strategy" | https://docs.kernel.org/admin-guide/cgroup-v2.html | USED → § Chosen approach L5 (no per-agent cap) |
| m-3 | resource-control(5) (exa) | "It is recommended to use MemoryHigh= as the main control mechanism and use MemoryMax= as the last line of defense" | https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html | USED → § Chosen approach L5 |
| m-4 | systemd-oomd(8) (exa) | oomd SIGKILLs a whole descendant cgroup on PSI pressure; programs should be managed by the user manager | https://www.freedesktop.org/software/systemd/man/latest/systemd-oomd.service.html | USED → § Rejected alternatives (oomd: not installed on this box) |
| m-5 | ubuntu-devel (exa, search) | Ubuntu's false kills came from the SwapUsedLimit rule with ManagedOOMSwap=kill on the root slice | https://lists.ubuntu.com/archives/ubuntu-devel/2022-June/ | USED → § Rejected alternatives (oomd swap rule with swap 7/8 GB full) |
| m-6 | psi(7) kernel doc (exa, search) | "some 150000 1000000" adds a 150 ms threshold in a 1 s window; unprivileged windows are multiples of 2 s | https://docs.kernel.org/accounting/psi.html | USED → § Chosen approach L5 (admission band) |
| m-7 | systemd.io PRESSURE (exa) | the default memory-pressure threshold is 200 ms per 2 s window | https://systemd.io/PRESSURE/ | USED → § Chosen approach L5 (admission band) |
| m-8 | kubelet eviction (exa highlights) | default hard eviction `memory.available<100Mi` | https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/ | REJECTED — read whole: a node-eviction floor for pods, far below what a 28 GB box with 10 GB jobs needs as a start gate |
| m-9 | proc_pid_oom_score_adj(5) (exa) | oom_score_adj from -1000 to +1000 is added to the badness score | https://man7.org/linux/man-pages/man5/proc_pid_oom_score_adj.5.html | USED → § Chosen approach L5 (kill order) |
| m-10 | resource-control(5) (exa) | `ManagedOOMPreference=avoid` makes oomd pick the cgroup only when nothing else is left | https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html | REJECTED — read whole: an oomd-only knob, and oomd is not installed here (m-4) |
| m-11 | wsl-config (exa + WebFetch) | `memory` default 50% of Windows RAM; `swap` 25%; `autoMemoryReclaim` default dropCache, values disabled/gradual/dropCache | https://learn.microsoft.com/en-us/windows/wsl/wsl-config | USED → § Open unknowns U5 (a .wslconfig change is the operator's) |
