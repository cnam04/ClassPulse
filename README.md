# ClassPulse

Quick classroom pulse-check tool built at a hackathon. Teachers create a session; students join with a code to:

- Run **60-second “confusion” votes** (Confused / So-so / Not Confused) with live charts  
- Start **yes/no polls** with per-poll revoting and results  
- **Broadcast a question** to all students (clears/hides on reset)  
- Let students **ask anonymous questions** (teacher inbox with broadcast/remove)  


> **Important:** Review code on the **`final`** branch (not `main`).

---

## Tech Stack

- **Frontend:** HTML/CSS + vanilla JS  
- **Backend:** Flask (Python)  
- **Data store:** Redis  
- **Sessions:** 8-char codes; voter IDs stored in localStorage

---

## Quick Start

### Requirements
- Python 3.11+  
- Redis (local or cloud)  
Install them via:

- Python: <https://www.python.org/downloads/>  
- Redis (all OSes): <https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/>

> If you don’t set `REDIS_URL`, the dev scripts default to `redis://localhost:6379/0` and expect a local Redis server.

### Setup
- Run these commands: 
  ```bash
  git clone <repo-url>
  cd <repo-folder>
  git checkout final
  ```
- If you're using *Windows*, run:
  ```bash
  dev.bat
  ```
- If you're using *Mac*, run:
  ```bat
  ./dev.sh
  ```
  

