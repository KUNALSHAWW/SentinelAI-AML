# 🚀 SentinelAI Deployment Guide - Render.com

This guide walks you through deploying SentinelAI to **Render.com** (free tier).

---

## 📋 Prerequisites

1. **GitHub Account** with your code pushed
2. **Render.com Account** (free): https://render.com
3. **Groq API Key**: Already configured ✅

---

## 🎯 Quick Deploy (One-Click)

### Option 1: Blueprint Deploy

1. Push your code to GitHub
2. Go to https://render.com
3. Click **"New +"** → **"Blueprint"**
4. Connect your GitHub repo
5. Render will detect `render.yaml` and deploy automatically

### Option 2: Manual Deploy

Follow the step-by-step guide below.

---

## 📝 Step-by-Step Deployment

### Step 1: Push Code to GitHub

```powershell
# In your project directory
cd C:\Users\kunal\OneDrive\Desktop\GITHUB\SentinelAI-AML

# Initialize git if needed
git init

# Add all files
git add .

# Commit
git commit -m "feat: SentinelAI Enterprise AML Platform"

# Add remote and push
git remote add origin https://github.com/KUNALSHAWW/SentinelAI-AML.git
git push -u origin main
```

### Step 2: Create PostgreSQL Database on Render

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"PostgreSQL"**
3. Configure:
   - **Name**: `sentinelai-db`
   - **Database**: `sentinelai`
   - **User**: `sentinelai`
   - **Region**: Choose closest to you
   - **Plan**: **Free** (1GB storage)
4. Click **"Create Database"**
5. Wait for it to be created (~2 minutes)
6. **Copy the "External Database URL"** - you'll need this!

### Step 3: Deploy the Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `sentinelai-api`
   - **Region**: Same as your database
   - **Branch**: `main`
   - **Root Directory**: Leave empty
   - **Runtime**: **Docker**
   - **Plan**: **Free**

### Step 4: Configure Environment Variables

In the Web Service settings, add these environment variables:

| Key | Value |
|-----|-------|
| `GROQ_API_KEY` | *(Your Groq API key from https://console.groq.com/)* |
| `DATABASE_URL` | *(paste the External Database URL from Step 2)* |
| `SENTINEL_ENVIRONMENT` | `production` |
| `SENTINEL_LLM_PROVIDER` | `groq` |
| `SENTINEL_LLM_GROQ_MODEL` | `llama-3.3-70b-versatile` |
| `SENTINEL_API_HOST` | `0.0.0.0` |
| `SENTINEL_MONITOR_LOG_LEVEL` | `INFO` |

### Step 5: Deploy

1. Click **"Create Web Service"**
2. Wait for the build and deployment (~5-10 minutes)
3. Your API will be available at: `https://sentinelai-api.onrender.com`

---

## ✅ Verify Deployment

### Health Check

```bash
curl https://sentinelai-api.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

### API Documentation

Visit: `https://sentinelai-api.onrender.com/docs`

### Test Analysis

```bash
curl -X POST https://sentinelai-api.onrender.com/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "transaction": {
      "amount": 500000,
      "currency": "USD",
      "transaction_type": "WIRE_TRANSFER",
      "origin_country": "RU",
      "destination_country": "KY",
      "parties": ["moscow_trading_llc", "cayman_holdings"]
    },
    "customer": {
      "name": "Moscow Trading LLC",
      "customer_type": "CORPORATE",
      "account_age_days": 30
    }
  }'
```

---

## 🔧 Troubleshooting

### Build Fails

1. Check the build logs in Render dashboard
2. Ensure all files are committed and pushed
3. Verify `Dockerfile` and `requirements.txt` are present

### Database Connection Error

1. Verify DATABASE_URL is correct (starts with `postgres://` or `postgresql://`)
2. Check the database is running in Render dashboard
3. Wait a few minutes for the database to fully initialize

### Application Won't Start

1. Check the logs: Render Dashboard → Your Service → Logs
2. Verify all environment variables are set
3. Ensure GROQ_API_KEY is valid

### Slow Response (Free Tier)

- Free tier services spin down after 15 minutes of inactivity
- First request after idle may take 30-60 seconds
- Subsequent requests will be fast

---

## 🆓 Free Tier Limitations

| Resource | Free Tier Limit |
|----------|----------------|
| Web Service | 750 hours/month, spins down after 15min idle |
| PostgreSQL | 1GB storage, 256MB RAM |
| Bandwidth | 100GB/month |
| Build Time | 500 min/month |

---

## 🔒 Security Notes

1. **Never commit `.env` file** to GitHub
2. Set environment variables in Render dashboard
3. Use Render's secret management for API keys
4. Enable IP allowlist for database if needed

---

## 📈 Upgrading

When you're ready for production:

1. Upgrade to **Starter** plan ($7/month) for:
   - No spin-down
   - Better performance
   - Custom domains

2. Upgrade PostgreSQL for:
   - More storage
   - Better performance
   - Automated backups

---

## 🎉 Your SentinelAI is Live!

After deployment, your API is accessible at:

- **API Base URL**: `https://sentinelai-api.onrender.com`
- **API Docs**: `https://sentinelai-api.onrender.com/docs`
- **Health Check**: `https://sentinelai-api.onrender.com/health`

---

## 📞 Support

If you encounter issues:
1. Check Render status: https://status.render.com
2. Review logs in Render dashboard
3. Open an issue: https://github.com/KUNALSHAWW/SentinelAI-AML/issues

**Happy detecting! 🛡️**
