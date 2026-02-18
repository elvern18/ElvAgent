# Instagram Integration - Quick Start

## ✅ What I Built

1. **Image Generator** - Creates beautiful newsletter cards
   - Intro card with summary
   - Item cards (colorful, category-coded)
   - Outro card with branding
   - Uses Pillow (already installed)

2. **Instagram Formatter** - Formats as carousel posts
   - Up to 10 images per post
   - Captions with hashtags
   - Link aggregation

3. **Instagram Publisher** - Posts via Graph API
   - Uploads images
   - Creates carousel
   - Publishes to your account

4. **Test Script** - Safe testing before going live

## 💰 Cost: FREE

Instagram Graph API is completely free! No payment required.

## 📋 What You Need to Do

### Quick Setup (10 minutes)

1. **Convert Instagram to Business**
   - Instagram app → Settings → Switch to Professional Account
   - Choose "Business" (NOT Creator)

2. **Create/Link Facebook Page**
   - Need a Facebook Page (can be hidden)
   - Link it in Instagram settings
   - This is just for API authentication - **nothing posts to Facebook!**

3. **Get Credentials**
   - Follow: `docs/INSTAGRAM_SETUP.md`
   - Get 2 values:
     - `INSTAGRAM_ACCESS_TOKEN`
     - `INSTAGRAM_BUSINESS_ACCOUNT_ID`

4. **Add to .env**
   ```bash
   INSTAGRAM_ACCESS_TOKEN=your_token_here
   INSTAGRAM_BUSINESS_ACCOUNT_ID=your_id_here
   ```

5. **Test It!**
   ```bash
   source .venv/bin/activate
   python scripts/test_instagram.py
   ```

## 🎨 What It Looks Like

Your Instagram post will be a **carousel** (swipeable):

**Slide 1:** Intro card
```
┌─────────────────────────┐
│  🤖 AI News Update      │
│  Feb 16, 2026           │
│                         │
│  Today's AI highlights  │
│  include groundbreaking │
│  research in...         │
│                         │
│  📊 3 items             │
│  👉 Swipe to see all →  │
└─────────────────────────┘
```

**Slide 2-4:** Item cards (colorful, category-coded)
```
┌─────────────────────────┐
│  ①  📚 RESEARCH         │
│     ⭐ 9/10             │
│                         │
│  Novel LLM Architecture │
│  ─────────────────────  │
│                         │
│  Breakthrough in        │
│  transformer efficiency │
│  reduces training...    │
│                         │
│  🔗 Link in caption     │
└─────────────────────────┘
```

**Last Slide:** Outro card
```
┌─────────────────────────┐
│                         │
│  That's all for now!    │
│                         │
│  Follow for hourly      │
│  AI updates             │
│                         │
│  🤖 Powered by ElvAgent │
│                         │
└─────────────────────────┘
```

## 🧪 Testing Flow

1. Run test script (shows preview, asks confirmation)
2. Images generate locally
3. Script asks: "Post to Instagram? yes/no"
4. Type 'yes' to post

## 📊 Rate Limits

- **Posts per day:** 25 (recommended)
- **API calls per hour:** 200
- **Cost:** $0 (free!)

## ⚠️ Important Notes

### About Facebook Page

- **Required:** Yes (Meta's requirement)
- **Will it post there?** NO! Only Instagram.
- **Can it be hidden?** Yes
- **Can it be inactive?** Yes

The Facebook Page is just for authentication. Nothing posts to it.

### App Review

- **For testing (your account):** Works immediately ✅
- **For production (auto-posting):** Need approval (1-2 weeks)
- **How to apply:** See `docs/INSTAGRAM_SETUP.md` Part 5

## 🚀 Ready for End-to-End Test?

Once you have credentials set up:

```bash
# Test Instagram only
python scripts/test_instagram.py

# Full pipeline with Instagram
python scripts/test_full_pipeline_with_instagram.py
```

## 📚 Full Documentation

See `docs/INSTAGRAM_SETUP.md` for:
- Detailed setup instructions
- Credential generation guide
- Troubleshooting
- App review process

## Next Steps

1. Follow `docs/INSTAGRAM_SETUP.md` to get credentials
2. Test with `scripts/test_instagram.py`
3. Once working, we'll do full end-to-end testing
4. Then set up hourly automation!

Questions? Let me know! 🎉
