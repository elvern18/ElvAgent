# Telegram Setup - 5 Minutes ⚡

Super simple setup - no business accounts, no approval process!

## 📋 What You Need

Just 2 things:
1. Telegram Bot Token
2. Chat ID (where to post)

**Cost: FREE** ✅ (completely free, unlimited)

---

## Step 1: Create a Telegram Bot (2 minutes)

### 1.1 Open Telegram and find BotFather

1. Open Telegram app/web
2. Search for **@BotFather**
3. Start a chat

### 1.2 Create your bot

Send this command:
```
/newbot
```

BotFather will ask:
1. **Bot name:** "ElvAgent News Bot" (or anything you want)
2. **Username:** Must end in 'bot', e.g., `elvagent_news_bot`

### 1.3 Get your token

BotFather will reply with:
```
Done! Your token is:
123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

**Copy this token!** This is your `TELEGRAM_BOT_TOKEN`

---

## Step 2: Get Your Chat ID (2 minutes)

You have two options:

### Option A: Personal Chat (Simplest)

1. Start a chat with your new bot
2. Send any message to it (e.g., "Hello")
3. Visit this URL in browser (replace `YOUR_BOT_TOKEN`):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
4. Look for `"chat":{"id":123456789}` in the response
5. Copy that number - this is your `TELEGRAM_CHAT_ID`

### Option B: Channel (For public posts)

1. Create a Telegram channel
2. Add your bot as administrator
3. Post a message in the channel
4. Visit the same URL as above
5. Look for the chat ID (will be negative, like `-1001234567890`)

### Option C: Use a Helper Bot

1. Search for **@userinfobot** on Telegram
2. Start chat, it will show your chat ID immediately

---

## Step 3: Add to .env (1 minute)

Edit your `.env` file:

```bash
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=your_chat_id_here
```

**Note:** Chat ID is just a number (can be negative for channels)

---

## Step 4: Test It! (30 seconds)

```bash
source .venv/bin/activate
python scripts/test_telegram.py
```

Expected output:
```
Testing Telegram Publisher
============================================================

1. Initializing Telegram publisher...
2. Validating credentials...
✅ Credentials found

3. Testing bot connection...
✅ Bot connected: @elvagent_news_bot

4. Formatting newsletter as Telegram message...

📝 Generated 1 message(s):

--- Message 1 (XXX chars) ---
🤖 AI News Update - Feb 16, 10:00

Testing ElvAgent's automated Telegram posting...

============================================================
⚠️  READY TO POST TO TELEGRAM
============================================================

Post to Telegram? (yes/no):
```

Type `yes` and check your Telegram chat! 🎉

---

## What Gets Posted

Your Telegram messages will include:

```
🤖 AI News Update - Feb 16, 10:00

Testing ElvAgent's automated Telegram posting with markdown formatting!

📊 3 items in this update:

1. 📚 Novel LLM Architecture
   ⭐ Score: 9/10 | Category: RESEARCH
   This paper presents a breakthrough in transformer architectures...
   🔗 Read more

2. 🚀 Multimodal Learning Advances
   ⭐ Score: 8/10 | Category: PRODUCT
   We present a new approach to multimodal reasoning...
   🔗 Read more

3. 📰 Scaling Laws for Diffusion
   ⭐ Score: 8/10 | Category: NEWS
   Analysis of scaling behavior in diffusion models...
   🔗 Read more

━━━━━━━━━━━━━━━━━
🤖 Powered by ElvAgent
Automated AI news delivered hourly
```

**Features:**
- ✅ Markdown formatting (bold, links, etc.)
- ✅ Category emojis
- ✅ Relevance scores
- ✅ Clickable links
- ✅ Clean, readable format

---

## Troubleshooting

### Error: "Invalid token"
**Solution:** Double-check your `TELEGRAM_BOT_TOKEN` from BotFather

### Error: "Chat not found"
**Solution:**
1. Make sure you sent a message to the bot first
2. Check your `TELEGRAM_CHAT_ID` is correct
3. For channels: Make sure bot is admin

### Error: "Bot can't initiate conversation"
**Solution:** You need to start a chat with the bot first (send any message)

### Messages not appearing
**Solution:**
1. Check you're looking at the right chat/channel
2. For channels: Bot must be admin
3. Try sending to your personal chat first

---

## Advantages of Telegram

✅ **Free** - Completely free, no limits
✅ **Simple** - 5-minute setup
✅ **No approval** - Works immediately
✅ **Unlimited** - No rate limits for bots
✅ **Rich formatting** - Markdown support
✅ **Reliable** - Very stable API
✅ **Multi-platform** - Works on all devices

---

## Next Steps

Once it works:

1. **Test the full pipeline:**
   ```bash
   python scripts/test_full_pipeline_telegram.py
   ```

2. **Add to production:**
   Update `src/main.py`:
   ```python
   publishers = [
       TelegramPublisher(),
       MarkdownPublisher()
   ]
   ```

3. **Set up hourly automation**

4. **Invite others to your channel** (optional)

---

## Tips

- **For personal use:** Post to your personal chat
- **For sharing:** Create a channel and share the link
- **For team:** Create a group and add team members
- **For public:** Create a public channel with a username

---

## That's It!

Telegram is the simplest platform to set up. Ready to test? 🚀
