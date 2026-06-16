# AGENTS.md

## Overview: Multi-Agent Architecture for Atari SAP Discord Bot

This document outlines the decentralized, multi-agent architecture designed to power the **Atari SAP Discord Bot**. Rather than operating as a monolithic script, the system splits operations into distinct autonomous or semi-autonomous agents. This separation ensures that real-time Discord API handling is never blocked by synchronous tasks like file scraping, POKEY chip emulation, or audio transcoding.

---

## 1. Architectural Blueprint

```
       ┌────────────────────────────────────────────────────────┐
       │                     Discord Guild                      │
       └───────────────────────────┬────────────────────────────┘
                                   │ (Commands / Audio Stream)
                                   ▼
                   ┌───────────────────────────────┐
                   │     Discord Interface Agent   │
                   └───────────────┬───────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │ (Job Request)           │ (State Inquiries)       │ (Stream Data)
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  ASMA Catalog   │       │  Queue & State  │       │ Audio Processing│
│  & Search Agent │       │  Manager Agent  │       │ & Emulator Agent│
└────────┬────────┘       └─────────────────┘       └────────┬────────┘
         │                                                   │
         ▼ (Metadata)                                        ▼ (WAV/PCM)
   [ASMA Archive]                                      [ASAP / Audacious]
```

---

## 2. Agent Definitions and Responsibilities

### 🤖 1. Discord Interface Agent (The Front-End Controller)
*   **Primary Objective**: Act as the bridge between Discord users, voice channels, and the backend core.
*   **Key Responsibilities**:
    *   Listen for text commands (`!play`, `!stop`, `!skip`, `!subsong`, `!search`).
    *   Manage life cycles of Voice Connections (`VoiceClient`).
    *   Stream audio frames smoothly using FFmpeg backends into Discord’s Opus voice protocol.
    *   Emit real-time status updates (e.g., Rich Embeds displaying current track metadata).
*   **Tooling & Dependencies**: `discord.py`, `PyNaCl` (for encryption/Opus processing).

### 🔍 2. ASMA Catalog & Search Agent (The Data Specialist)
*   **Primary Objective**: Resolve user queries into explicit ASMA file pathways, parsing and validating `.sap` assets.
*   **Key Responsibilities**:
    *   Ingest and cache the **Atari SAP Music Archive (ASMA)** directory structural tree (from `https://asma.atari.org/`).
    *   Parse raw `.sap` text headers to extract track attributes: **AUTHOR**, **NAME**, **DATE**, and **SONGS** (discovering multi-subsong tracks).
    *   Validate URLs to prevent malicious script injection or non-archive network traffic.
*   **Tooling & Dependencies**: `requests`, `BeautifulSoup4`, `re` (Regular Expressions for SAP parsing).

### ⚙️ 3. Audio Processing & Emulator Agent (The Transcoding Engine)
*   **Primary Objective**: Convert 6502 machine code / POKEY chip definitions inside `.sap` files into raw high-fidelity audio data.
*   **Key Responsibilities**:
    *   **Headless Execution (Default)**: Invoke command-line compilation interfaces (`asapconv`) to seamlessly unpack SAP files to high-bitrate `.wav` formats.
    *   **System Loopback Execution (Optional Audacious Track)**: Interact with desktop instance audio pipelines using `audtool` IPC calls, capturing system output or virtual audio pipelines (e.g., VB-Audio Cable / PulseAudio Monitor Sinks).
    *   **Subsong Isolation**: Splice or pinpoint targeted track offsets when an Atari file contains multiple hidden pieces of music.
*   **Tooling & Dependencies**: `subprocess`, `ASAP (Another Slight Atari Player) CLI`, `audtool` (for Audacious setups), `FFmpeg`.

### 📊 4. Queue & State Manager Agent (The Memory Coordinator)
*   **Primary Objective**: Guard chronological tracking, server settings, and play structures across multiple Discord guilds simultaneously.
*   **Key Responsibilities**:
    *   Maintain multi-tenant isolation (Guild A's queue must never cross into Guild B's).
    *   Manage loop conditions (single track looping, playlist repeating, shuffling).
    *   Persist tracking logs for skipped or highly-rated tracks to generate automated playlists over time.
*   **Tooling & Dependencies**: `collections.deque`, Thread-safe primitives, local SQLite caching.

---

## 3. Inter-Agent Communication Lifecycle
Below demonstrates how the agents communicate when a user issues a play request:

1.  **User Interacts**: A user types `!play https://asma.atari.org/.../Acidjazzed_Evening.sap` in a text channel.
2.  **Discord Interface Agent** catches the message string, strips parameters, and invokes the **Queue & State Manager Agent** to check if the voice pipeline is active.
3.  The **ASMA Catalog & Search Agent** verifies the URL, extracts the filename, downloads the data chunk, and scrapes the internal SAP metadata tag block to return the track name and sub-track limits.
4.  Once cleared, the **Audio Processing & Emulator Agent** steps in, spins up `asapconv`, and materializes an uncompressed audio file or starts an internal loopback capture matrix.
5.  The **Discord Interface Agent** accepts the resulting audio handle, pipes it through FFmpeg, and begins broadcasting raw audio into the voice channel while updating the text interface.

---

## 4. Error Handling Matrix & Resilience

| Failure State | Triggering Agent | Resolution Policy |
| :--- | :--- | :--- |
| **Network Timeout (ASMA Offline)** | ASMA Catalog Agent | Fail gracefully; notify Discord Interface Agent to output a user-friendly error block indicating the archive repository is temporarily down. |
| **Corrupted .sap Header** | ASMA Catalog Agent | Abort parsing immediately. Return data error up the stack. Fall back to standard filename string representation. |
| **Voice WebSocket Disconnect** | Discord Interface Agent | Initiate automated reconnect sequences. Alert Queue Agent to pause current audio playback pointer to preserve track positioning. |
| **Transcoder Crash (`asapconv` error)** | Audio Processing Agent | Purge temp file system spaces, fallback onto local warning routines, skip to the next item in queue automatically. |

---

## 5. Development Roles & AI Context
When developing, modifying, or prompting code creation agents for this repository, respect the boundaries established by this document:
*   Never write blocking/synchronous network or CPU calculations directly inside the Discord event loops (`on_message`, etc.).
*   Isolate system-level file transcoding actions within execution blocks managed by the **Audio Processing Agent**.
