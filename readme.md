# Slackbot Local Development with ngrok

This guide explains how to start the Flask Slackbot server locally and expose it to the internet using **ngrok**, so Slack can send events to your local machine.

---

## ✅ Prerequisites

1. **Python Environment**

   - Ensure you have Python (≥3.8) installed.
   - Activate your virtual environment or Anaconda environment:
     ```bash
     conda activate base
     ```
     or
     ```bash
     source venv/bin/activate
     ```

2. **Install Dependencies**

   - From the project directory:
     ```bash
     pip install -r requirements.txt
     ```

3. **Install ngrok**

   - [Download ngrok](https://ngrok.com/download) and install it.
   - Connect your account (replace `YOUR_AUTHTOKEN` with your actual token):
     ```bash
     ngrok config add-authtoken YOUR_AUTHTOKEN
     ```

---

## ✅ Start the Flask App

1. Navigate to your working directory:

   ```bash
   cd ~/Desktop
   ```

2. Set the Flask environment and start the app:

   ```bash
   export FLASK_ENV=development
   python slackbot.py
   ```

   - The app should now run at:
     ```
     http://127.0.0.1:3000
     ```

---

## ✅ Start ngrok Tunnel

1. Open a **new terminal window/tab** and run:
   ```bash
   ngrok http 3000
   ```
2. You will see output like:
   ```
   Forwarding  https://<your-ngrok-subdomain>.ngrok-free.app -> http://localhost:3000
   ```
   - Copy the `https://<your-ngrok-subdomain>.ngrok-free.app` URL.

---

## ✅ Configure Slack App

1. In your Slack App settings:
   - Go to **Slash Commands** or **Event Subscriptions**.
   - Update the **Request URL** to:
     ```
     https://<your-ngrok-subdomain>.ngrok-free.app/slack/commands
     ```
2. Save changes.

---

## ✅ Test the Slash Command

- In Slack, run your command (e.g. `/purchase_request`).
- Check your terminal for incoming POST requests.

---

### 🔄 Common Commands

Restart the Flask server:

```bash
CTRL+C
python slackbot.py
```

Restart ngrok tunnel:

```bash
CTRL+C
ngrok http 3000
```

---

✅ **You’re all set!** Your Flask Slackbot is now accessible to Slack through the ngrok tunnel.

