# TeamTask Manager

A full-stack team task management app built with Flask + SQLite/PostgreSQL.

## Features
- 🔐 Authentication (Signup / Login)
- 📁 Project management with team invitations
- ✅ Task creation, assignment & status tracking
- 👥 Role-based access (Admin / Member)
- 📊 Dashboard with task stats & overdue alerts

---

## Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python app.py

# 3. Visit http://localhost:5000
```

---

## Deploy to Railway (Free)

### Step 1: Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/teamtask.git
git push -u origin main
```

### Step 2: Deploy on Railway
1. Go to **https://railway.app** → Sign in with GitHub
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `teamtask` repo
4. Railway auto-detects Python — click **Deploy**

### Step 3: Add PostgreSQL (optional, recommended)
1. In your Railway project, click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway automatically sets `DATABASE_URL` env var — no extra config needed!

### Step 4: Set Environment Variables
In Railway project settings → Variables:
```
SECRET_KEY = your-super-secret-key-change-this
```

### Step 5: Get your URL
Railway gives you a public URL like `https://teamtask-production.up.railway.app`

---

## Environment Variables
| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Flask session secret | `dev-secret-key` |
| `DATABASE_URL` | PostgreSQL URL (auto-set by Railway) | SQLite |
| `PORT` | Server port (auto-set by Railway) | `5000` |

---

## Project Structure
```
taskmanager/
├── app.py              # Flask app + routes + models
├── requirements.txt    # Python dependencies
├── Procfile            # Gunicorn start command
├── railway.toml        # Railway config
└── templates/
    ├── auth.html       # Login / Signup page
    ├── dashboard.html  # Main dashboard
    └── project.html    # Project detail + tasks
```
