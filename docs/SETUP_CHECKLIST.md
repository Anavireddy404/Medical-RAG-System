# Medical RAG System - Setup Checklist ✓

Use this checklist to ensure everything is configured correctly before running the system.

---

## 📋 Pre-Installation Checklist

- [ ] **Operating System**: macOS, Linux, or Windows
- [ ] **Python**: Version 3.9+ installed
  ```bash
  python3 --version  # Should show Python 3.9+
  ```
- [ ] **Git**: Installed for version control (optional)
  ```bash
  git --version  # Should show git version
  ```
- [ ] **Text Editor**: VS Code, PyCharm, or similar
- [ ] **OpenAI Account**: Created and API key generated
  - Visit: https://platform.openai.com/account/api-keys
  - [ ] API key copied and saved in safe place
  - [ ] Usage limits set (optional but recommended)

---

## 🔑 Step 1: API Key Setup

- [ ] **OpenAI API Key Obtained**
  ```bash
  # Go to https://platform.openai.com/account/api-keys
  # Create new secret key
  # Save it somewhere safe
  ```

- [ ] **Credit Added to OpenAI Account**
  - Minimum $5 recommended for testing
  - Check at: https://platform.openai.com/account/billing/overview

- [ ] **API Key Format Verified**
  - Should start with `sk-`
  - Should be ~48 characters long
  - Example: `sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

---

## 📁 Step 2: Project Structure Setup

### Option A: Local Development

- [ ] **Create Project Directory**
  ```bash
  mkdir medical-rag-system
  cd medical-rag-system
  ```

- [ ] **Create Subdirectories**
  ```bash
  mkdir backend frontend data logs
  ```

- [ ] **Copy Project Files**
  - [ ] `main.py` → Copy to `backend/` directory
  - [ ] `index.html` → Copy to `frontend/` directory
  - [ ] `requirements.txt` → Copy to root directory
  - [ ] `.env.example` → Copy to root directory

- [ ] **Rename Configuration**
  ```bash
  cp .env.example .env
  ```

### Option B: Docker Setup

- [ ] **Docker Installed**
  ```bash
  docker --version        # Should show Docker version
  docker-compose --version # Should show Docker Compose version
  ```

- [ ] **Copy Project Files**
  - [ ] `Dockerfile`
  - [ ] `docker-compose.yml`
  - [ ] `nginx.conf`
  - [ ] `main.py`
  - [ ] `index.html`
  - [ ] `requirements.txt`

---

## ⚙️ Step 3: Environment Configuration

### For Local Development

- [ ] **Create `.env` File**
  ```bash
  nano .env  # or use any text editor
  ```

- [ ] **Add Configuration**
  ```bash
  OPENAI_API_KEY=sk-your-api-key-here
  DATABASE_URL=sqlite:///./medical_rag.db
  ENVIRONMENT=development
  DEBUG=True
  ```

- [ ] **Save File** (Ctrl+S or Cmd+S)

- [ ] **Verify File Created**
  ```bash
  cat .env  # Should show your configuration
  ```

⚠️ **Security Check:**
- [ ] `.env` file contains your API key
- [ ] `.env` is in `.gitignore` (don't commit it!)
- [ ] Never share your API key with others

### For Docker

- [ ] **Set Environment Variable**
  ```bash
  export OPENAI_API_KEY=sk-your-api-key-here
  ```

- [ ] **Verify It's Set**
  ```bash
  echo $OPENAI_API_KEY  # Should show your key
  ```

---

## 🐍 Step 4: Python Setup (Local Development Only)

- [ ] **Create Virtual Environment**
  ```bash
  python3 -m venv venv
  ```

- [ ] **Activate Virtual Environment**
  ```bash
  # macOS/Linux:
  source venv/bin/activate
  
  # Windows:
  venv\Scripts\activate
  
  # Should see (venv) at start of terminal line
  ```

- [ ] **Upgrade pip**
  ```bash
  pip install --upgrade pip
  ```

- [ ] **Install Dependencies**
  ```bash
  pip install -r requirements.txt
  ```

- [ ] **Verify Installation**
  ```bash
  pip list  # Should show fastapi, uvicorn, openai, etc.
  ```

- [ ] **Check Individual Packages**
  ```bash
  python3 -c "import fastapi; print(fastapi.__version__)"
  python3 -c "import openai; print(openai.__version__)"
  ```

---

## 🚀 Step 5: Run Backend

### Option A: Local Python

- [ ] **Navigate to Project Directory**
  ```bash
  cd medical-rag-system
  ```

- [ ] **Activate Virtual Environment**
  ```bash
  source venv/bin/activate  # macOS/Linux
  venv\Scripts\activate      # Windows
  ```

- [ ] **Start Backend Server**
  ```bash
  python3 main.py
  ```

- [ ] **Verify Backend Started**
  - Look for message: `INFO: Uvicorn running on http://0.0.0.0:8000`
  - [ ] No error messages
  - [ ] Port 8000 is free

### Option B: Docker

- [ ] **Start Docker Daemon**
  - Docker Desktop running (macOS/Windows)
  - Or `sudo systemctl start docker` (Linux)

- [ ] **Build and Run**
  ```bash
  docker-compose up -d
  ```

- [ ] **Verify Containers Started**
  ```bash
  docker-compose ps
  # Should show: api, db, cache, nginx all "Up"
  ```

- [ ] **Check Logs**
  ```bash
  docker-compose logs -f api
  # Should show: "Application startup complete"
  ```

---

## 🧪 Step 6: Test Backend

- [ ] **Health Check**
  ```bash
  curl http://localhost:8000/health
  # Should return: {"status":"healthy",...}
  ```

- [ ] **Create Test Profile**
  ```bash
  curl -X POST http://localhost:8000/api/health-profile/create \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": "test123",
      "age": 45,
      "gender": "Male",
      "medical_conditions": ["Hypertension"],
      "current_medications": ["Lisinopril"],
      "allergies": [],
      "lifestyle_factors": "Moderately Active",
      "family_history": []
    }'
  # Should return: profile_id
  ```

- [ ] **View API Docs**
  - Open browser to: http://localhost:8000/docs
  - [ ] Swagger UI loads
  - [ ] All endpoints listed

---

## 🖥️ Step 7: Access Frontend

- [ ] **Open Frontend in Browser**
  - Option 1: `file://` protocol
    - Drag `index.html` into browser
  - Option 2: Local server
    ```bash
    cd frontend
    python3 -m http.server 3000
    # Open: http://localhost:3000
    ```
  - Option 3: Docker
    - Open: http://localhost

- [ ] **Frontend Loads Successfully**
  - [ ] See "Medical Literature RAG System" header
  - [ ] Health profile form visible
  - [ ] Medical query form visible
  - [ ] No console errors (F12)

---

## ✅ Step 8: End-to-End Test

- [ ] **Create Health Profile**
  1. Fill in form:
     - Age: 45
     - Gender: Male
     - Condition: Hypertension
     - Medication: Lisinopril
  2. Click "Create Profile"
  3. See success message
  4. Profile ID displayed

- [ ] **Ask Medical Question**
  1. Enter query: "What are benefits of ACE inhibitors?"
  2. Enable personalization (if profile created)
  3. Click "Search Medical Literature"
  4. Wait for response
  5. [ ] See answer text
  6. [ ] See retrieved papers
  7. [ ] See personalized insights
  8. [ ] See metrics (accuracy %, response time)

- [ ] **No Errors**
  - [ ] Browser console clean (no red errors)
  - [ ] Backend logs show no errors
  - [ ] All responses return successfully

---

## 📊 Step 9: Verify Performance

- [ ] **Response Times**
  - [ ] Health profile creation: <100ms
  - [ ] Query processing: <1 second
  - [ ] Paper retrieval: <500ms

- [ ] **Data Quality**
  - [ ] Papers have titles, authors, abstracts
  - [ ] DOI links are valid format
  - [ ] Personalized insights generated

- [ ] **UI Responsiveness**
  - [ ] Forms submit without lag
  - [ ] Loading spinners appear
  - [ ] Results display smoothly

---

## 📱 Step 10: Browser Compatibility

Test on different browsers:

- [ ] **Chrome/Chromium**
  - [ ] Frontend loads
  - [ ] API calls work
  - [ ] All features functional

- [ ] **Firefox**
  - [ ] Frontend loads
  - [ ] API calls work
  - [ ] Styling correct

- [ ] **Safari** (macOS/iOS)
  - [ ] Frontend loads
  - [ ] API calls work
  - [ ] Mobile responsive

- [ ] **Mobile Browser**
  - [ ] Responsive design works
  - [ ] Touch inputs work
  - [ ] Layout adjusts

---

## 🔐 Step 11: Security Verification

- [ ] **Environment Variables**
  - [ ] API key in `.env` file
  - [ ] `.env` not in Git
  - [ ] `.env` has restricted permissions
  ```bash
  chmod 600 .env
  ```

- [ ] **CORS Configuration**
  - [ ] Frontend can call API
  - [ ] No CORS errors in console

- [ ] **API Security**
  - [ ] No sensitive data in URLs
  - [ ] Passwords not logged
  - [ ] Rate limiting functional

---

## 📈 Step 12: Performance Optimization

Optional but recommended:

- [ ] **Enable Caching**
  ```python
  # In main.py - already included
  from functools import lru_cache
  ```

- [ ] **Compression Enabled**
  - [ ] gzip compression in Nginx config

- [ ] **Database Indexing**
  - [ ] User profiles indexed
  - [ ] Query results cached

---

## 🚀 Step 13: Deployment Preparation

Before deploying to production:

- [ ] **Update Configuration**
  - [ ] `ENVIRONMENT=production`
  - [ ] `DEBUG=False`
  - [ ] `SECRET_KEY=` (change this)

- [ ] **Database Migration**
  - [ ] SQLite → PostgreSQL migration script ready
  - [ ] Backup strategy documented

- [ ] **SSL/HTTPS**
  - [ ] SSL certificate obtained (Let's Encrypt)
  - [ ] Nginx HTTPS config updated

- [ ] **Monitoring**
  - [ ] Logging configured
  - [ ] Error tracking setup (Sentry)
  - [ ] Performance monitoring ready

---

## 📋 Final Verification

Run this final check before considering setup complete:

```bash
# Backend health
curl http://localhost:8000/health

# Frontend accessible
# (Open index.html in browser)

# Full test
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is hypertension?"}'

# Logs show no errors
docker-compose logs --tail=50
```

---

## ✨ Success Criteria

**Your setup is complete when:**

- ✅ Backend running on `http://localhost:8000`
- ✅ Frontend accessible in browser
- ✅ Health check endpoint responds
- ✅ Health profile creation works
- ✅ Medical queries return results
- ✅ Papers displayed with citations
- ✅ No console errors
- ✅ Response times <1 second
- ✅ API documentation visible at `/docs`

---

## 🆘 Troubleshooting

### Backend Won't Start
```bash
# Check Python version
python3 --version  # Need 3.9+

# Check virtual environment activated
which python3  # Should show venv path

# Check dependencies installed
pip list | grep fastapi

# Try explicit host/port
python3 main.py --host 0.0.0.0 --port 8000
```

### Frontend Can't Connect to API
```bash
# Verify backend running
curl http://localhost:8000/health

# Check browser console (F12)
# Look for CORS errors

# Update API URL if needed
# In index.html: const API_URL = 'http://localhost:8000/api'
```

### Docker Issues
```bash
# Check containers running
docker-compose ps

# View logs
docker-compose logs api

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### API Key Not Working
```bash
# Verify key format
echo $OPENAI_API_KEY  # Should start with sk-

# Check OpenAI account
# Go to https://platform.openai.com/account/api-keys

# Test API directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

## 📞 Need Help?

If you're stuck:

1. **Check Logs**: Look at terminal/Docker logs for error messages
2. **Read Docs**: See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
3. **Run Tests**: Execute test suite to find issues
4. **Search Issues**: GitHub issues might have solutions
5. **Ask Community**: Create issue or discussion

---

## 🎉 Next Steps

Once setup is complete:

1. **Explore Features**
   - Try different health conditions
   - Ask various medical questions
   - Test personalization

2. **Customize System**
   - Modify UI colors
   - Add more medical papers
   - Extend with new features

3. **Deploy**
   - Choose deployment platform
   - Follow [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
   - Set up monitoring

4. **Integrate**
   - Connect to real PubMed API
   - Add user authentication
   - Implement database persistence

---

**Checklist Version:** 1.0  
**Last Updated:** January 2024  
**Status:** ✅ Complete
