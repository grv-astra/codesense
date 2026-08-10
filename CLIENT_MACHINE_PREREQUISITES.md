# Code Sense — Machine Prerequisites

Please prepare the target machine with the following **before** we begin the application setup.
This is a one-time preparation step; none of this requires our involvement.

## 1. Runtime software

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.13.x | Must be on `PATH` (`python --version` should work from any terminal) |
| Node.js | 20.19 or newer | Must be on `PATH` (`node --version` should work) |
| npm | (bundled with Node) | Comes with Node.js automatically |
| Git | any recent version | Only needed if we're deploying via a repository checkout |

## 2. Disk space

- At least **2 GB free** for the application, its dependencies, and the offline scanning
  tools (Semgrep/OpenGrep engine, vulnerability rule sets, dependency-vulnerability
  database).
- If AI-assisted verification will be enabled (optional), an additional **5–10 GB** for the
  local language model file. We'll confirm whether this applies to your setup.

## 3. Network access

- **One-time only**, during setup: outbound internet access is needed to download the
  application dependencies and the offline scanning tools.
- **After setup**: the application runs fully offline — no ongoing internet access is
  required for normal use (uploading/scanning code, viewing results).

## 4. Ports

Please confirm these two ports are free (not in use by another application) on the target
machine, or let us know which alternate ports you'd prefer:

- **Backend (API)**: a port of your choice, e.g. `8585`
- **Frontend (web UI)**: a port of your choice, e.g. `5173` (dev) or your production web
  server's port if serving a built static site

## 5. Access needed from us / for setup

- A user account with permission to install software and create files/folders (no need for
  full administrator rights unless your organization's policy requires it for installing
  Python/Node).
- Confirmation of where persistent application data should live on this machine (a folder
  outside any source-code checkout — we'll point to a specific path during setup).

## 6. Operating system

Currently verified on **Windows**. macOS is also supported by the project but hasn't been
re-verified in this round — let us know if the target machine is macOS or Linux so we can
confirm before setup day.

---

Once the above is in place, actual application setup (installing dependencies, configuring
the scanning engine, starting the services) typically takes under 30 minutes.
