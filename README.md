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
- Environment variable:
  ```bash
  export REDIS_URL=redis://localhost:6379/0
### Setup
git clone <repo-url>
cd <repo-folder>
git checkout final

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python app.py
