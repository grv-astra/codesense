# Code Sense — Architecture & Data Flow

Offline, self-contained desktop tool. Everything below runs **on the user's laptop**;
there is **no network egress** at runtime (listeners bind to `127.0.0.1` only).

---

## 1. Architecture (component / deployment view)

```mermaid
flowchart TB
  user(["Analyst / Operator"])

  subgraph LAPTOP["User laptop — loopback only, no network egress"]
    direction TB

    subgraph APP["Code Sense (Tauri desktop shell, Rust)"]
      tray["System tray:<br/>Open / Pause AI / Quit"]
      ui["WebView2 window<br/>React + Vite UI"]
    end

    subgraph BE["Django backend (waitress) @ 127.0.0.1:8585"]
      api["REST API<br/>JWT auth + RBAC<br/>ReadOnly-grace license middleware"]
    end

    llama["llama-server (llama.cpp)<br/>@ 127.0.0.1:&lt;port&gt;<br/>serves astra.gguf (CPU)"]
    tools["Syft / Grype / Grant / Cosign<br/>(resources/tools)"]
    gdb[("Grype CVE DB snapshot<br/>frozen — resources/grype-db")]
    db[("SQLite<br/>users · projects · scans · findings<br/>%LOCALAPPDATA%")]
    keys[("License stamp + Cosign keys<br/>file + registry (win) / plist (mac)")]
  end

  user --> ui
  ui -->|"HTTP loopback"| api
  APP -. "spawns &amp; supervises (sidecars)" .-> BE
  APP -. "spawns &amp; supervises" .-> llama
  api -->|"HTTP /v1/chat"| llama
  api -->|"subprocess"| tools
  tools -->|"reads"| gdb
  api -->|"read / write"| db
  api -->|"read / write"| keys

  classDef ext fill:#fff,stroke:#bf0000,stroke-width:1px;
  class user ext;
```

### ASCII fallback

```
+--------------------- User laptop  (loopback only, no egress) ----------------------+
|                                                                                    |
|   +----------- Code Sense  (Tauri shell, Rust) -----------+                         |
|   |  tray: Open / Pause AI / Quit                         |                         |
|   |  WebView2 window  ->  React + Vite UI                 |                         |
|   +----------------------------+--------------------------+                         |
|        |  (shell spawns &       |  HTTP  http://127.0.0.1:8585                       |
|        |   supervises sidecars) v                                                   |
|   +----------------- Django backend (waitress) -----------------+                   |
|   |  REST API · JWT auth · RBAC · ReadOnly-grace license check  |                   |
|   |    |                                                        |                   |
|   |    +-- HTTP /v1/chat ---> llama-server (llama.cpp + astra.gguf, CPU)            |
|   |    +-- subprocess ------> Syft / Grype / Grant / Cosign  (resources\tools)      |
|   |    +-- reads ----------->  Grype CVE DB snapshot (frozen, resources\grype-db)   |
|   |    +-- read/write ------>  SQLite  +  license stamp  +  cosign keys             |
|   |                            (%LOCALAPPDATA%\com.codesense.desktop)               |
|   +-------------------------------------------------------------+                   |
|                                                                                    |
|   X no inbound ports beyond loopback   X no outbound traffic   X no telemetry       |
+------------------------------------------------------------------------------------+
```

| Component | Role |
|---|---|
| Tauri shell (Rust) | Native window, tray, and lifecycle/supervision of the two sidecars |
| WebView2 UI (React/Vite) | The app UI; talks only to `127.0.0.1:8585` |
| Django backend (waitress) | REST API, JWT auth, RBAC, license gating, scan orchestration |
| llama-server (llama.cpp) | Local LLM inference for the SAST code review (CPU) |
| Syft / Grype / Grant / Cosign | SBOM generation, CVE scan, license scan, SBOM signing |
| Grype DB snapshot | Frozen offline CVE database (`AUTO_UPDATE` off at runtime) |
| SQLite | All app data (users, projects, scans, findings, SBOM findings) |
| License store | Signed first-run stamp in a file + a redundant OS store (registry/plist) |

---

## 2. Data flow diagram

```mermaid
flowchart TB
  user(["Operator"])

  subgraph LAP["Trust boundary — the laptop (nothing leaves the device)"]
    ui["WebView2 UI"]

    subgraph API["Django backend @ 127.0.0.1:8585"]
      auth["JWT auth + RBAC"]
      lic["License middleware<br/>(read-only grace)"]
      orch["Scan orchestrator"]
      sast["SAST: AST + risky-chunk selection"]
      sca["SCA: Syft -> Grype + Grant"]
      dash["Dashboard aggregations"]
    end

    llama["llama-server (GGUF)"]
    gdb[("Grype DB (frozen)")]
    sql[("SQLite:<br/>users · projects · scans ·<br/>findings · sbom_findings · licenses")]
    lstore[("License stamp<br/>file + registry/plist")]
  end

  user -->|"creds / code / SBOM"| ui
  ui -->|"HTTP loopback (Bearer JWT)"| auth
  auth -->|"first run: create admin"| sql
  auth -. "stamp first_seen" .-> lstore
  auth --> lic
  lic <-->|"state: active / expired / tampered"| lstore
  lic -->|"writes (scans/edits) if licensed"| orch
  lic -->|"reads always allowed"| dash

  orch -->|"code chunks"| sast
  sast -->|"POST /v1/chat"| llama
  llama -->|"vulnerability findings"| sast
  sast -->|"persist findings"| sql

  orch -->|"dir / uploaded SBOM"| sca
  sca -->|"query CVEs"| gdb
  sca -->|"persist CVE + license findings"| sql

  dash -->|"read aggregates"| sql
```

### ASCII fallback

```
 Operator
    |  creds / source code / SBOM
    v
 [WebView2 UI] --HTTP loopback (Bearer JWT)--> [Django backend @127.0.0.1:8585]
                                                   |
        +------------------------------------------+-----------------------------+
        |                       |                  |                             |
        v                       v                  v                             v
   [JWT auth + RBAC]     [License middleware] [Scan orchestrator]          [Dashboard]
        |                  ^   (read-only grace)   |                            |
        | create admin     |  state: active/        +--- code ---> [SAST: AST + chunks]
        v                  |  expired/tampered                         |  POST /v1/chat
   (SQLite users)          v                                           v
                      [License stamp]                          [llama-server (GGUF)]
                       file + reg/plist                                |  findings
                                                                       v
   [Scan orchestrator] --- dir / SBOM ---> [SCA: Syft -> Grype + Grant] ---> (SQLite findings)
                                                |  query CVEs
                                                v
                                        [Grype DB snapshot (frozen)]

   Dashboard / finding views ----read----> (SQLite)
   ===> No data ever leaves the laptop (no cloud, no telemetry, no license server) <===
```

---

## 3. Scan lifecycle (sequence)

```mermaid
sequenceDiagram
  actor U as Operator
  participant UI as WebView2 UI
  participant API as Django (127.0.0.1:8585)
  participant LIC as License middleware
  participant LL as llama-server
  participant SY as Syft/Grype/Grant
  participant DB as SQLite

  U->>UI: submit source (zip / path) or SBOM
  UI->>API: POST /api/scans/... (Bearer JWT)
  API->>LIC: evaluate license state
  LIC-->>API: active -> allow write
  alt SAST (code review)
    API->>API: AST metrics + select risky chunks
    loop per chunk
      API->>LL: POST /v1/chat (code chunk)
      LL-->>API: structured finding (CWE, severity, fix)
    end
  else SCA (dependencies)
    API->>SY: syft -> grype + grant (subprocess)
    SY-->>API: CVEs + license findings
  end
  API->>DB: persist findings
  UI->>API: GET /api/findings/...
  API->>DB: read findings
  API-->>UI: findings JSON
  Note over U,DB: 100% on-device — no network egress
```

---

## Notes
- **Ports:** backend `127.0.0.1:8585`; `llama-server` on a private loopback port. No other listeners.
- **OS specifics:** Windows uses WebView2 + a registry second store for the license; macOS uses WKWebView + a `~/Library/Preferences` plist second store. Logic is otherwise identical.
- **At rest:** data lives in `%LOCALAPPDATA%` (Windows) / `~/Library/Application Support` (macOS); confidentiality relies on endpoint full-disk encryption.
- **License gating:** the middleware lets reads through always; write/scan endpoints are blocked once the license is expired or tampered (read-only grace).
