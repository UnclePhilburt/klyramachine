# Deploying Klyra Machine to Render

This guide walks through deploying the Klyra Machine server to Render.com.

## Prerequisites

1. GitHub account
2. Render account (free tier works!)
3. OpenAI API key
4. ElevenLabs API key

## Step 1: Push to GitHub

```bash
cd C:\Users\CodyW\Documents\klyramachine

# Initialize git (if not already done)
git init
git add .
git commit -m "Initial commit - Klyra Machine"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/klyramachine.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy to Render

### Option A: Using Render Dashboard (Recommended)

1. Go to https://dashboard.render.com/
2. Click "New +" → "Web Service"
3. Connect your GitHub account if not already connected
4. Select your `klyramachine` repository
5. Configure the service:

   **Basic Settings:**
   - Name: `klyramachine-server`
   - Region: Choose closest to you
   - Branch: `main`
   - Root Directory: Leave blank

   **Build & Deploy:**
   - Runtime: `Python 3`
   - Build Command: `cd server && pip install -r requirements.txt`
   - Start Command: `cd server && uvicorn server:app --host 0.0.0.0 --port $PORT`

   **Instance Type:**
   - Free (for testing) or Starter (for production)

6. Add Environment Variables:
   Click "Add Environment Variable" for each:
   - Key: `OPENAI_API_KEY`, Value: `your-openai-key`
   - Key: `ELEVENLABS_API_KEY`, Value: `your-elevenlabs-key`

7. Click "Create Web Service"

### Option B: Using render.yaml (Auto-deploy)

The repo includes a `render.yaml` file for automatic deployment.

1. Go to https://dashboard.render.com/
2. Click "New +" → "Blueprint"
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml` and configure everything
5. Add your API keys as environment variables

## Step 3: Get Your Server URL

After deployment completes (takes 2-5 minutes):

1. You'll see your service URL: `https://klyramachine-server.onrender.com`
2. Click on it or visit it in a browser
3. You should see: `{"status":"online","service":"Klyra Machine Server"}`

## Step 4: Update Client Config

On your Windows PC or Raspberry Pi:

1. Edit `client/config.json`
2. Update `server_url` to your Render URL:
   ```json
   {
     "server_url": "https://klyramachine-server.onrender.com",
     "client_id": "klyra_client_001",
     ...
   }
   ```

## Step 5: Test the Connection

```bash
cd client
python client.py
```

You should see: `Server is online!`

## Important Notes

### Free Tier Limitations

Render's free tier:
- Server spins down after 15 minutes of inactivity
- First request after spin-down takes 30-60 seconds
- 750 hours/month free (enough for testing)

For production, upgrade to Starter ($7/month) for always-on service.

### Environment Variables on Render

Instead of `config.json`, the server can read from environment variables:

```python
# In server.py, modify to read from env vars:
import os

config = {
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "elevenlabs_api_key": os.getenv("ELEVENLABS_API_KEY"),
    # ... other config
}
```

### Monitoring

- Check logs: Render Dashboard → Your Service → Logs
- Health check: Visit your server URL in browser
- API test: `https://your-server.onrender.com/docs` for API documentation

## Troubleshooting

### Build Failed
- Check build logs in Render dashboard
- Verify `requirements.txt` has all dependencies
- Ensure build command is correct

### Server Won't Start
- Check start command: `cd server && uvicorn server:app --host 0.0.0.0 --port $PORT`
- Verify environment variables are set
- Check logs for errors

### Client Can't Connect
- Verify server URL in client config
- Check server is running (visit URL in browser)
- Ensure no typos in URL

### API Errors
- Verify API keys are correct in Render environment variables
- Check OpenAI and ElevenLabs account have credits
- Look at server logs for detailed errors

## Updating Your Deployment

When you make changes:

```bash
git add .
git commit -m "Description of changes"
git push
```

Render will automatically rebuild and deploy!

## Next Steps

- Test on Windows PC first
- Once working, deploy to Raspberry Pi
- Monitor API usage and costs
- Consider upgrading to paid tier for production use
