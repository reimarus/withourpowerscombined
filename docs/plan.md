# Current Plan

> This is a living document. It should reflect the active implementation plan at all times.

## Lifecycle

1. **When a new plan is created** in `.claude/plans/`, copy the key details here so any session (human or AI) can see what's in progress at a glance.
2. **While executing**, update the status of each step as it completes.
3. **When the final step is committed**, clear this file and replace with a brief summary of what was completed, then mark it as "No active plan."

---

## Active Plan: Unified Multiplayer UX — Game Browser + Lobby Room

**Source:** `.claude/plans/calm-doodling-honey.md`
**Branch:** TBD (next feature branch off main)
**Goal:** Replace archaic SOLO/HOST/JOIN + IP entry with modern SOLO/MULTIPLAYER flow: LAN game browser + cohesive lobby room.

### Architecture Note

**Our launcher IS the lobby.** All launch modes use `/wopcquickstart`. The FAF in-game lobby UI is NEVER shown. All multiplayer coordination (player list, game options, map selection, chat, ready state, file transfer) happens in the Python launcher over TCP. Players go directly from our launcher into the match.

### Key Changes

1. LAN discovery via UDP beacons (`launcher/discovery.py`)
2. Game browser screen — see and join LAN games with one click
3. Lobby room screen — map, players, options, chat in one unified view
4. Simplified mode selector: SOLO / MULTIPLAYER (replaces SOLO/HOST/JOIN)
5. No IP/port entry visible by default (Direct Connect collapsed as advanced fallback)

### Status

- [ ] `launcher/discovery.py` — BeaconBroadcaster + BeaconListener
- [ ] `tests/test_discovery.py` — socket tests
- [ ] `launcher/gui/app.py` — screen switching, browser screen, lobby room screen
- [ ] `launcher/prefs.py` — update launch_mode values
- [ ] Verification and testing
