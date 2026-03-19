# Multiplayer Feature Checklist — FAF Lobby Audit → WOPC Launcher

## Approach
FAF's lobby.lua is ~290KB of battle-tested multiplayer code. We don't need everything — WOPC's
design deliberately bypasses the in-game lobby UI and handles coordination in the Python launcher.
This checklist maps every FAF lobby feature to a WOPC status and priority.

Legend: ✅ Done | 🔧 Partial | ❌ Missing | ⏭ Not Needed

---

## 1. CORE LOBBY INFRASTRUCTURE

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| TCP lobby server/client | UDP+GPGNet | ✅ lobby.py | — | Different transport, same purpose |
| JSON-line protocol | Binary GPGNet | ✅ lobby.py | — | Simpler, works for our scale |
| Heartbeat / disconnect detection | ✅ | ✅ 5s/15s | — | |
| Max 16 players | ✅ | ✅ | — | |
| NAT traversal | ✅ natTraversalProvider | ❌ | P3 | LAN-first; internet play needs this later |
| Protocol versioning | ✅ | ✅ protocol_version=1 | — | |

## 2. PLAYER / SLOT MANAGEMENT

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Player data structure (name, faction, team, color, slot) | ✅ playerdata.lua | ✅ lobby.py _RemotePlayer | — | Added team + color fields |
| Open/Close slot states | ✅ | ❌ | P2 | Host can lock out slots |
| Move player to different slot | ✅ MovePlayerToEmptySlot | ❌ | P2 | Drag-and-drop slot rearrangement |
| Swap players between slots | ✅ SwapPlayers | ❌ | P2 | |
| Kick player | ✅ EjectPeer | ✅ kick_player() | — | Host kicks with reason, client gets on_kicked callback |
| Player slot sequential assignment | ✅ | ✅ | — | |
| FindSlotForID / FindNameForID | ✅ | ✅ (server-side) | — | |

## 3. OBSERVER / SPECTATOR SUPPORT

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Observer slots (separate from player) | ✅ | ❌ | P2 | Nice for friends who want to watch |
| Convert player ↔ observer | ✅ | ❌ | P2 | |
| AllowObservers game option | ✅ | ❌ | P2 | |
| Observer list with ratings/ping | ✅ | ❌ | P3 | |
| Kick all observers | ✅ | ❌ | P3 | |

## 4. GAME OPTIONS

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Victory condition selector | ✅ 5 options | ✅ 4 options in GUI | — | Demoralization/Supremacy/Assassination/Sandbox + correct engine mapping |
| Unit cap selector | ✅ 125-1500 | ✅ 500-4000 in GUI | — | 5 options in dropdown |
| Game speed option | ✅ normal/fast/adjustable | ❌ | P2 | |
| Share on death | ✅ 6 modes | ✅ 2 modes in GUI | — | FullShare / ShareUntilDeath |
| Fog of war | ✅ none/explored | ❌ | P2 | |
| Cheats toggle | ✅ | ❌ | P2 | |
| No rush timer | ✅ 0-60 min | ❌ | P2 | |
| Civilian alliance | ✅ enemy/neutral/removed | ❌ | P3 | |
| Prebuilt units | ✅ | ❌ | P3 | |
| Timeouts | ✅ | ❌ | P3 | |
| Minimap toggle | ✅ | ✅ | — | Already in launcher |
| Game options sync to all peers | ✅ broadcast | ✅ _broadcast_game_state | — | Host changes reach joiners live |
| Per-map custom options | ✅ scenario.options | ❌ | P2 | Maps can define their own options |

## 5. AI CONFIGURATION

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| AI personality selector | ✅ 14 types | ✅ 7 types | — | Have the core set |
| AI faction selector | ✅ | ✅ | — | |
| AI team assignment | ✅ | 🔧 static | **P1** | Need dynamic team selector per AI |
| AI build/cheat multipliers | ✅ 1.0-5.9 | ❌ | P2 | AIOpts: BuildMult, CheatMult |
| AI expansion limits | ✅ 0-8/unlimited | ❌ | P2 | Land/Naval expansions |
| AI omni cheat | ✅ | ❌ | P3 | |
| AI rating calculation | ✅ | ❌ | P3 | |
| Custom AI loading from mods | ✅ CustomAIs_v2 | ⏭ | — | LOUD handles this |

## 6. FACTION & COLOR MANAGEMENT

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Faction selector (UEF/Aeon/Cybran/Sera/Random) | ✅ | ✅ | — | |
| Random faction resolution at launch | ✅ | ✅ multilobby.lua | — | |
| Player color selector | ✅ full palette | ✅ color dropdown per slot | — | 8 SCFA colors, wired to game_config |
| Army color (separate from player color) | ✅ | ❌ | P3 | |
| IsColorFree validation | ✅ | ✅ _validate_before_launch | — | Blocks launch on duplicate colors |
| Faction sync to all peers | ✅ | ✅ via game state broadcast | — | Included in full state sync |

## 7. TEAM & ALLIANCE MANAGEMENT

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Manual team assignment per slot | ✅ teams 1-8 | ✅ dropdown 1-4 per slot | — | Human + AI slots both have team selector |
| Auto-team strategies (TopVsBottom, LeftVsRight, etc.) | ✅ 9 modes | ❌ | P2 | |
| Team lock (prevent changes after set) | ✅ | ❌ | P3 | |
| Team rating display | ✅ TrueSkill | ❌ | P3 | |
| Auto-balance algorithms | ✅ 4 algorithms | ❌ | P3 | |

## 8. READY & LAUNCH MECHANICS

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Player ready toggle | ✅ | ✅ | — | |
| Ready indicator per player | ✅ | ✅ (✓ or —) | — | |
| All-must-ready before launch | ✅ GetPlayersNotReady | ✅ _validate_before_launch | — | Lists not-ready players |
| Launch validation (connections, teams, options) | ✅ TryLaunch | ✅ _validate_before_launch | — | Checks map, ready state, WOPC deploy |
| Auto-convert victory to sandbox for 1-team | ✅ | ❌ | P2 | |
| Asset prefetch before launch | ✅ Prefetch() | ❌ | P2 | |

## 9. MAP SELECTION

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Map browser with preview | ✅ gameselect.lua | ✅ (in launcher) | — | |
| Map sync — broadcast to all peers | ✅ | ✅ via game state broadcast | — | Map name+folder in GameState |
| Map missing detection | ✅ ClientsMissingMap | ✅ _on_game_state_received | — | Warns joiner if map not found locally |
| Random map option | ✅ Official/All | ❌ | P3 | |
| Adaptive map support (spawn mex) | ✅ | ⏭ | — | LOUD/FAF handles at engine level |
| Map position markers on preview | ✅ | ❌ | P2 | Show spawn points on minimap |

## 10. MOD / CONTENT PACK MANAGEMENT

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Mod selection UI | ✅ ModsManager | ✅ (content packs toggle) | — | |
| Mod sync across peers | ✅ broadcast | ❌ | **P1** | All players need same mods |
| Mod blacklist enforcement | ✅ | ⏭ | — | Not needed for WOPC |
| Mod dependency resolution | ✅ | ⏭ | — | LOUD handles this |
| Manifest-based file validation | N/A | ✅ manifest_builder.py | — | Better than FAF's approach |
| Pre-launch mod hash check | N/A | ❌ | **P1** | Have the tool, need to wire it in |

## 11. CHAT & COMMUNICATION

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Lobby text chat | ✅ chatarea.lua | ✅ Chat msg type + GUI input | — | Host broadcasts, client relays, chat bar in GUI |
| System messages (join/leave/kick) | ✅ | 🔧 log textbox only | — | Have events, need chat format |
| Whisper / private message | ✅ /whisper | ❌ | P3 | |
| Color-coded messages by player | ✅ | ❌ | P2 | |

## 12. CONNECTION & NETWORK

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Peer-to-peer connection tracking | ✅ connectedTo[] | ✅ (server tracks) | — | |
| Connection established events | ✅ | ✅ callbacks | — | |
| Ping monitoring per peer | ✅ lobby-ping.lua | ❌ | P2 | Show latency in player list |
| Connection matrix (all-to-all) | ✅ | ❌ | P3 | |
| Proxy detection | ✅ ConnectedWithProxy | ❌ | P3 | |
| EveryoneHasEstablishedConnections check | ✅ | ❌ | **P1** | Pre-launch network validation |

## 13. LIVE STATE SYNC (Host → Joiners)

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Broadcast game options changes | ✅ | ✅ _broadcast_game_state | — | Triggers on option change |
| Broadcast map changes | ✅ | ✅ _broadcast_game_state | — | Triggers on map select |
| Broadcast AI slot changes | ✅ | ✅ _broadcast_game_state | — | Triggers on slot add/remove |
| Broadcast team changes | ✅ | ✅ TeamChange msg | — | Client→server→broadcast |
| Broadcast player color changes | ✅ | ✅ ColorChange msg | — | Client→server→broadcast |
| Broadcast mod/pack changes | ✅ | ✅ content_packs in GameState | — | Joiner warned about mismatched packs |
| Full state snapshot on join | ✅ | ✅ game_state_provider | — | Full state sent via GameState msg on connect |

## 14. HOST ADMIN

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Kick player | ✅ EjectPeer | ✅ kick_player() | — | With kick button in GUI |
| Force player not-ready | ✅ SetPlayerNotReady | ❌ | P2 | |
| Close/open slots | ✅ | ❌ | P2 | |
| Kick all observers | ✅ | ❌ | P3 | |

## 15. UNIT RESTRICTIONS

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Unit restriction presets | ✅ restrictedUnitsData | ❌ | P2 | No T3, No Experimentals, etc. |
| Custom unit restriction UI | ✅ restrictedUnitsDlg | ❌ | P3 | |
| Restriction sync to peers | ✅ | ❌ | P2 | |

## 16. PRESETS & PERSISTENCE

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Save/load game presets | ✅ presets.lua | ❌ | P2 | "Save this setup for next game night" |
| Last-used settings persistence | ✅ Prefs | ✅ prefs.py | — | |
| Rehost with same settings | ✅ | ❌ | P2 | |

## 17. CPU & PERFORMANCE

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| CPU benchmark scoring | ✅ | ❌ | P3 | |
| Performance display per player | ✅ | ❌ | P3 | |

## 18. LOBBY PASSWORD / AUTHENTICATION

| Feature | FAF | WOPC | Priority | Notes |
|---------|-----|------|----------|-------|
| Lobby password | FAF uses matchmaker | ❌ | P2 | Prevent randoms from joining |
| Player identity verification | FAF accounts | ❌ | P3 | Steam integration later |

---

## PRIORITY SUMMARY

### P1 — Must Have (Next Sprint)
These are the features that make multiplayer actually usable for game night:

1. ~~**Live state sync** — Host broadcasts ALL config changes to joiners in real-time~~ ✅ DONE
   - ✅ Game options, map, AI slots, teams, colors broadcast on every change
   - ✅ Full state snapshot sent to new joiners on connect
   - ✅ Content packs included in state, joiner warned about mismatches
2. ~~**Player color selector** — Pick colors, prevent duplicates~~ ✅ DONE
3. ~~**Team assignment UI** — Dropdown per player/AI slot~~ ✅ DONE (was already built)
4. ~~**Game options panel** — Victory condition, unit cap, share on death~~ ✅ DONE (was already built)
5. ~~**All-must-ready enforcement** — Host can't launch until everyone is ready~~ ✅ DONE
6. ~~**Pre-launch validation** — Check connections, check map availability, check mod sync~~ ✅ DONE
7. ~~**Kick player** — Host can remove someone from lobby~~ ✅ DONE
8. ~~**Lobby chat** — Text chat between players while configuring~~ ✅ DONE
9. ~~**Map sync** — Detect + auto-download missing maps from host~~ ✅ DONE
10. **Mod/manifest validation** — Verify all players have matching files before launch ❌ (partial — content pack warnings exist)

### P2 — Should Have (Following Sprint)
11. Observer/spectator support
12. Game speed, fog of war, cheats, no-rush options
13. AI build/cheat multipliers
14. Auto-team strategies
15. Open/close slots, move/swap players
16. Map spawn position preview
17. Save/load game presets
18. Ping display per player
19. Unit restriction presets
20. Lobby password
21. Color-coded chat messages

### P3 — Nice to Have (Backlog)
22. NAT traversal for internet play
23. CPU benchmark
24. Connection matrix
25. TrueSkill ratings and balance
26. Army color (separate from player color)
27. Whisper/PM in chat
28. Steam friends integration

---

## IMPLEMENTATION APPROACH

### What We Leverage From FAF
- **multilobby.lua** already handles P2P game launch with full gameInfo
- **quickstart.lua** already reads config with all fields (teams, colors, options)
- **game_config.py** already serializes the full game state to Lua
- **manifest_builder.py** already generates file hashes for sync validation
- **lobby.py** protocol is extensible — add new message types without breaking existing

### What We Build New
- **State sync protocol** — New message types: `GameState`, `OptionChange`, `MapChange`, `SlotChange`, `Chat`, `Kick`
- **Game options GUI panel** — Victory, unit cap, share mode at minimum
- **Color picker widget** — Color dots or swatches per player slot
- **Team selector widget** — Dropdown per slot (Team 1-8 or FFA)
- **Chat widget** — Text input + scrolling message area in launcher
- **Pre-launch validator** — Check all connections, map presence, mod hashes
- **Kick mechanism** — Server sends disconnect + reason, client handles gracefully

### Architecture Principle
Keep the launcher as the single source of truth for game configuration.
The Lua side (quickstart + multilobby) just reads what the launcher writes.
All multiplayer coordination happens over TCP in Python, not in Lua.
