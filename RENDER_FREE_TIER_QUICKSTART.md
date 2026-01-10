# Render Free Tier Deployment - Quick Start Cheatsheet

## 🚀 5-Minute Overview

You'll deploy on Render FREE tier + free external databases. **Cost: $0/month**

## Service Accounts Needed (All Free!)

```
1. Render          → https://render.com (sign up with GitHub)
2. Supabase        → https://supabase.com (PostgreSQL)
3. MongoDB Atlas   → https://cloud.mongodb.com (MongoDB)
4. GitHub          → https://github.com (push your code)
5. Google Gemini   → https://ai.google.dev (API key)
```

---

## Step-by-Step Deployment (20 minutes)

### 1️⃣ GitHub Setup (5 min)

```bash
# From your project folder
git init
git add .
git commit -m "MLR POC ready for deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/mlr-deploy.git
git push -u origin main
```

**⚠️ Repository MUST be PUBLIC for Render free tier**

---

### 2️⃣ Create Supabase PostgreSQL (2 min)

1. Go to https://supabase.com → Sign up with GitHub
2. Create project (any region is fine)
3. Go to **Settings** → **Database** → Copy connection string

Example:
```
postgresql://postgres:YOUR_PASSWORD@aws-0-us-west-1.pooler.supabase.com:6543/postgres
```

Save this! You'll need it for environment variables.

---

### 3️⃣ Create MongoDB Atlas (3 min)

1. Go to https://cloud.mongodb.com → Sign up
2. Create cluster → Choose **M0 Free** tier
3. Create database user:
   - Username: `mlr_user`
   - Password: `YOUR_STRONG_PASSWORD`
   
4. Go to **Network Access** → **Add IP Entry** → `0.0.0.0/0`

5. Click **Databases** → **Connect** → Copy connection string

Example:
```
mongodb+srv://mlr_user:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/mlr_db
```

Save this too!

---

### 4️⃣ Deploy Backend on Render (5 min)

1. Go to https://render.com → Sign in with GitHub
2. Click **New +** → **Web Service**
3. Select your `mlr-deploy` repository (MUST be public)
4. Fill in:
   - **Name:** `mlr-backend`
   - **Environment:** Python 3
   - **Region:** Pick closest to you
   - **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`

5. **At bottom, select PLAN: FREE** ✅

6. Click **Create Web Service**

7. While building, go to **Environment** tab and add:

```
ENVIRONMENT=production
LOG_LEVEL=INFO
SECRET_KEY=your-random-32-character-string-here-1234567890
ALGORITHM=HS256
GEMINI_API_KEY=your-google-gemini-api-key
DATABASE_URL=postgresql://postgres:PASSWORD@HOST:6543/postgres
MONGODB_URI=mongodb+srv://mlr_user:PASSWORD@cluster0.xxxxx.mongodb.net/mlr_db
CORS_ORIGINS=https://mlr-frontend-xxx.render.com
```

**Replace:**
- `SECRET_KEY` → Random string (use a password generator)
- `GEMINI_API_KEY` → From Google AI Studio
- `DATABASE_URL` → From Supabase
- `MONGODB_URI` → From MongoDB Atlas
- `CORS_ORIGINS` → Will update after frontend deployment

8. **SAVE** → Backend deploys (3-5 minutes)

9. Note your backend URL when it says "Live":
   ```
   https://mlr-backend-XXXXX.render.com
   ```

---

### 5️⃣ Deploy Frontend on Render (3 min)

1. In Render Dashboard → Click **New +** → **Static Site**
2. Select your repository again
3. Fill in:
   - **Name:** `mlr-frontend`
   - **Build Command:** `cd MLR_UI_React && npm install && npm run build`
   - **Publish Directory:** `MLR_UI_React/dist`

4. **At bottom, select PLAN: FREE** ✅

5. Click **Create Static Site**

6. After it asks for environment, add:
   ```
   REACT_APP_API_URL=https://mlr-backend-XXXXX.render.com
   ```
   (Use the actual backend URL from step 4)

7. Click Deploy → Frontend builds (1-2 minutes)

8. Note your frontend URL:
   ```
   https://mlr-frontend-YYYYY.render.com
   ```

---

### 6️⃣ Update Backend CORS (1 min)

1. Go to **mlr-backend** service in Render
2. Click **Environment**
3. Update `CORS_ORIGINS` with your frontend URL:
   ```
   https://mlr-frontend-YYYYY.render.com
   ```
4. **Save** (auto-redeploys)

---

## ✅ You're Done! 

| What | URL |
|-----|-----|
| **Frontend (Your App)** | https://mlr-frontend-YYYYY.render.com |
| **Backend API** | https://mlr-backend-XXXXX.render.com |
| **API Docs** | https://mlr-backend-XXXXX.render.com/docs |

---

## 🧪 Test It

1. Open frontend URL in browser
2. Click **Sign Up**
3. Create test account
4. Upload sample PDFs
5. Run validation
6. Check results!

---

## ⚙️ If Something Breaks

### Backend won't deploy
```
Render Dashboard → mlr-backend → Logs
Look for red error messages
```

### Frontend shows "Cannot reach backend"
```
1. Check CORS_ORIGINS matches frontend URL exactly
2. Make sure REACT_APP_API_URL is set in frontend
3. Restart backend: Manual Deploy → Deploy latest commit
```

### Cold start is slow (15+ seconds)
```
Normal for free tier - service wakes up after 15 min inactivity
Try: https://uptimerobot.com (free tier) to keep it warm
```

---

## 📊 What You're Using (Free Tier Limits)

| Service | Limit | Notes |
|---------|-------|-------|
| Render Backend | 512MB RAM | Shared resources, cold starts OK |
| Render Frontend | Unlimited | Serves static files fast |
| Supabase DB | 2GB storage | Plenty for POC |
| MongoDB Atlas | 512MB storage | Plenty for POC |
| Requests | Unlimited | Per second OK |

---

## 🔐 Important Security Notes

Before sharing with others:
- ✅ All credentials are in Render environment (not in code)
- ✅ Database is password-protected
- ✅ API has CORS configured
- ⚠️ Don't share SECRET_KEY with anyone
- ⚠️ Don't commit `.env` files to GitHub

---

## 💰 Final Cost

```
Render Backend:  FREE ✅
Render Frontend: FREE ✅
Supabase:        FREE (2GB included) ✅
MongoDB:         FREE (M0) ✅
Gemini API:      FREE (60 req/min) ✅
─────────────────────────────
TOTAL:           $0/month ✅✅✅
```

---

## 📝 Environment Variables Checklist

```bash
# Copy this template, fill in values, add to Render environment

ENVIRONMENT=production
LOG_LEVEL=INFO
SECRET_KEY=<32-char-random-string>
ALGORITHM=HS256
GEMINI_API_KEY=<from-google-ai-studio>
DATABASE_URL=<from-supabase>
MONGODB_URI=<from-mongodb-atlas>
CORS_ORIGINS=https://mlr-frontend-YYYYY.render.com
```

---

## 🆘 Need Help?

1. Check Render Logs (Dashboard → Service → Logs)
2. Read full guide: `RENDER_DEPLOYMENT_GUIDE.md`
3. Render Status: https://render.statuspage.io
4. MongoDB Help: https://docs.mongodb.com
5. Supabase Help: https://supabase.com/docs

---

**Total Deployment Time:** ~20 minutes  
**Total Cost:** $0  
**Status:** Ready to demo! 🎉
