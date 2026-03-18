# EC2 Backend Integration Guide

This document describes the changes made to connect your React frontend (hosted on AWS Amplify) to your Flask backend on EC2.

## What Was Changed

### 1. **New API Configuration File** (`/react-frontend/src/config.js`)
- Centralized API URL management
- Supports environment variables via `VITE_API_BASE_URL`
- Dev mode: Uses relative paths (proxied to localhost by Vite)
- Prod mode: Uses the EC2 instance IP (54.145.3.50:5050)

### 2. **Updated Vite Config** (`/react-frontend/vite.config.js`)
- Changed proxy target from `localhost:5050` to `54.145.3.50:5050`
- Allows local development to test against the EC2 backend

### 3. **Updated All API Calls in React Pages**
All components now import and use `getApiUrl()` from the config:
- `DraftPage.jsx` - apiCall() function updated
- `LandingPage.jsx` - apiCall() and useAPI() hooks updated
- `CardDetailPage.jsx` - fetch() calls updated
- `CardStatsPage.jsx` - fetch() calls updated
- `PlayerStatsPage.jsx` - fetch() calls updated

### 4. **Environment Files**
- `.env.production` - Sets API URL for Amplify production builds
- `.env.example` - Documents available configuration options

## Deployment Steps for AWS Amplify

### Step 1: Update Amplify Environment Variables
In your Amplify console, add an environment variable for your build:

```
VITE_API_BASE_URL = http://54.145.3.50:5050
```

**Note:** If your EC2 instance has a custom domain name, update this URL accordingly.

### Step 2: Build Configuration
Ensure your Amplify build settings include:
```yaml
build:
  commands:
    - cd react-frontend && npm ci && npm run build
artifacts:
  baseDirectory: react-frontend/dist
```

Or if that's already configured, just trigger a new build with the new environment variable.

### Step 3: Test the Connection
After deployment:
1. Visit your Amplify frontend URL
2. Try loading the dashboard (should show match history, ELO data, etc.)
3. Check browser DevTools Console for any network errors
4. Verify API calls are going to `http://54.145.3.50:5050` (not your Amplify domain)

## Local Development

For local development with the EC2 backend:

```bash
cd react-frontend
npm run dev
```

The dev server (port 5173) will proxy requests to `http://54.145.3.50:5050` automatically via the Vite config.

**Alternative:** Edit `vite.config.js` to point back to `localhost:5050` if you're running the Flask app locally.

## CORS Considerations

⚠️ **Important:** If you get CORS errors, you need to enable CORS on your Flask app.

Update your `main.py` in the Flask backend:

```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
```

And install the dependency:
```bash
pip install flask-cors
```

Then restart the Flask app on EC2.

## API URL Format

The frontend will call URLs like:
```
http://54.145.3.50:5050/api/start
http://54.145.3.50:5050/api/action
http://54.145.3.50:5050/elixir.svg
```

Ensure your Flask app is listening on `0.0.0.0` (not just `localhost`) in your EC2 configuration.

Check [config.py](../config.py) for the port:
```python
PORT = 5050  # or your configured port
```

## Troubleshooting

### "Connection refused" or "ERR_CONNECTION_REFUSED"
- Verify the Flask app is running on EC2
- Check the security group allows inbound traffic on port 5050
- Verify the EC2 instance IP is correct (54.145.3.50)

### CORS errors
- Install and enable `flask-cors` (see CORS section above)
- Verify the CORS origin includes your Amplify domain

### API returns 404 or 500
- Check Flask app logs on EC2
- Verify all routes exist (compare with local version)
- Ensure the Flask app is using the correct port

### Environmental differences
- EC2 might be missing dependencies (check requirements.txt)
- CR API token might not be whitelisted for the EC2 IP (.env file)
- File paths might differ (ensure data/ directory exists on EC2)

---

For questions, refer to [CLAUDE.md](../CLAUDE.md) for the full codebase architecture.
