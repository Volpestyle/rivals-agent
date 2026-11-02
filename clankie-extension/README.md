# Clankie's Rivals game extension

**The bridge is disabled.** [VUH-1325](https://linear.app/vuhlp/issue/VUH-1325)
tracks re-enabling it. Before any sitting, verify the launcher's explicit
cooldown argument; every sitting records its kit patch and cooldown regime.
The commands below describe the interface, not authorization to run, and replay
checks do not establish live input safety.

This folder is the Clankie-facing half of the bridge. Clankie's `rivals` tool
starts, observes, steers, shares, and stops a Spider-Man practice-range sitting;
the session server in this repository (`agent/server.py`, [docs/clankie.md](../docs/clankie.md))
supplies the tactical policy and fast pad loop. It moved here from Clankie's core
on 2026-10-17 ([VUH-2419](https://linear.app/vuhlp/issue/VUH-2419); Clankie ADR 0175
and ADR 0234). It implements Clankie's public game-extension module contract
(`@clankie/extension`, `src/game.ts`) and imports only types from it:
Clankie hands it the durable play ledger, the shared lifecycle wrapper, its own
broker credentials, a private state directory and the Go Live port.

| File | Holds |
|---|---|
| `src/index.ts` | The module's exports: `gameExtensionApis`, `gameExtension`, `projectGameExtension` |
| `src/service.ts` | The sitting: play lease, persisted receipt, exact-stop lifecycle, recovery, the `rivals` tool and `POST /v1/rivals` |
| `src/client.ts`, `src/protocol.ts` | The session-server HTTP client and its command/status schemas |
| `skill/SKILL.md` | Clankie's gameplay skill for the `rivals` tool |
| `test/extension.test.ts` | Fault injection against a real Clankie core (ledger, registry, loader, lease router) |

## Install into Clankie

On Clankie's machine, with a Rivals Agent checkout beside a Clankie checkout
(`~/dev/rivals-agent` and `~/dev/clankie`):

```sh
cd ~/dev/rivals-agent/clankie-extension && pnpm install
clankie games extensions add ~/dev/rivals-agent/clankie-extension/src/index.ts url=http://127.0.0.1:4330
clankie restart
clankie games extensions        # lists rivals once it has loaded
```

`add` takes the absolute module path (the shell expands `~`) and writes
`gameplay.extensions` in Clankie's settings; `/games extensions add ...` does the
same in the TUI. Run it again to change `url`; `clankie games extensions remove
PATH` uninstalls. Both apply on restart. A module that fails to load is logged
as `game_extension.module_unavailable` and skipped. Clankie needs no core change
to install, re-enable or remove it.

The session server's bearer goes in Clankie's credential broker under
`rivals-agent`: in the console, `/auth`, then **Add / update API key**, **Other…**,
and the id `rivals-agent`. The extension can read only broker names in its own
`rivals` namespace. Never put the token in a URL, option or settings file.

To give Clankie the gameplay skill, link `skill/` as a machine-wide skill, for
example `~/.agents/skills/rivals`, through the dotfiles that own those links.
The tool's own description carries the essential rules without it.

Clankie's `rivals` tool and `POST /v1/rivals` (owner-authenticated, with the
conversation in `x-clankie-conversation-id`) accept the same commands:
`status`, `start` (`requestId`, `objective: {mode, note}`, `maxSeconds`),
`objective`, `observe`, `share` (optional `guildId` + `channelId`) and `stop`.
`observe` returns a PNG the captain sees as an image. `share` returns a
session-scoped, read-only watch URL; a browser must be able to reach that URL's
host (a loopback forward is local to the Mac). The optional Discord destination
uses the active user-session body's Go Live publisher and its channel allowlist;
an official bot body cannot publish Go Live. If the owner declines the Go Live port,
sharing still returns the watch URL with `publishing: "unavailable"`. Stopping
the sitting invalidates
the watch feed. Sharing carries video, not game audio.

## Set up the session server

In the `rivals-agent` checkout, create a control token once:

```sh
uv run python -m agent.server --token-file data/clankie-token --init-token
```

The token file is private and gitignored. Store the same token in Clankie's
broker as above.

Run the server **inside the Windows interactive desktop**, with the existing
Rivals live dependencies installed, when that desktop is available:

```sh
python -m agent.server --host 127.0.0.1 --token-file data/clankie-token --cooldowns normal
```

Use an SSH forward from Clankie's Mac to that loopback port, or bind the server
to the PC's private network address and restrict its firewall to the Mac. Use
HTTPS on an untrusted network. The host option is deployment configuration, not
model input. Starting the server does not open the game or send input. The game
must already be focused in the practice range; coordinate ownership with any
other process driving the desktop before starting a sitting.

The server requires `--cooldowns off|normal`, without a default. The Windows
launcher requires the equivalent `-Cooldowns`. Match the verified game setting:
No Ability Cooldown ON means `off`; OFF means `normal`. This declares the regime;
it does not change the game. Each sitting records it and the patch read from the
Rivals kit in `game/meta.json` and `session.json`. An unreadable kit patch refuses
the start. The disabled PC deployment needs the reviewed files and an explicit
cooldown argument before an authorized restart.

## Ownership and cleanup

Starts capture the authenticated conversation and reserve the same durable
`play` lease used by Pokémon and Minecraft. A repeated start from the same
owner/request reads the original sitting; it never dispatches another
controller. Other conversations cannot steer or stop it.

A stop requests native cleanup. Only the original native session ID, request ID,
start time and execution mode with `phase: stopped`, no error and post-cleanup
`endedAt` release ownership. Failed/denied cleanup, a lost HTTP reply, a missing
record or a replacement sitting keep the lease and registration uncertain.
Restart recovery uses the persisted original origin and receipt (in Clankie's
state root under `game-extensions/rivals/session.json`) through Clankie's
owner-authorized `clankie body request` recovery path; changing `url` cannot
redirect cleanup to another controller. Status and extension discovery are
read-only and never start a controller. An uncertain claim can require an
operator to restore access to the original server; a new server is not proof.

`starting` and `stopping` are pending states. Inspect `status` for `running`,
`stopped`, or `failed`. A supplied note is recorded, but the current policy only
acts on the three modes: `autonomous`, `combat`, and `disengage`. It reports
`noteApplied: false`; don't describe a prose instruction as learned or executed.
Session summaries and notes live under `data/clankie/<session>/session.json` in
Rivals Agent; its normal synchronized recording is under that session's `game/`.

## Verify

```sh
pnpm typecheck                      # resolves @clankie/extension from ../../clankie
CLANKIE_ROOT=~/dev/clankie pnpm test   # Node 24+, a Clankie checkout with pnpm install done
```

For a recorded-game run, start the server on the Mac instead of the live one:

```sh
uv run --group perception python -m agent.server --token-file data/clankie-token \
  --dry data/l1/tagrun0 --cooldowns off
```

The same commands exercise real perception and controller logic against recorded
footage with a fake pad. Status explicitly says `execution: replay`. This proves
the integration without claiming that inputs changed the recorded game.
