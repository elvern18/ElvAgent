# Instagram Integration Setup Guide

Complete step-by-step guide to set up Instagram Graph API for ElvAgent.

## ⚠️ Important: What You Need

- Instagram **Business** account (not Personal, not Creator)
- Facebook Page (can be hidden/inactive)
- Facebook Developer account
- 10 minutes of setup time

**Cost: FREE** ✅

---

## Part 1: Convert Instagram to Business Account

### Step 1: Open Instagram App

1. Go to your profile
2. Tap the menu (☰) → Settings

### Step 2: Switch Account Type

1. Tap **Account**
2. Tap **Switch to Professional Account**
3. Choose **Business** (NOT Creator)
4. Select a category (e.g., "News & Media Company")
5. Skip adding contact info (optional)

### Step 3: Connect Facebook Page

**If you DON'T have a Facebook Page:**
1. Go to facebook.com/pages/create
2. Create a simple page:
   - Name: "ElvAgent News" (or anything)
   - Category: "Media/News Company"
   - Skip the setup wizard
3. The page can stay unpublished/hidden - it's just for API auth

**Connect the Page:**
1. Instagram Settings → Account → Linked Accounts → Facebook
2. Log into Facebook
3. Select your page
4. Grant permissions

✅ Your Instagram is now a Business account connected to a Facebook Page!

---

## Part 2: Facebook Developer Setup

### Step 4: Create Facebook Developer Account

1. Go to: https://developers.facebook.com/
2. Click **Get Started** (top right)
3. Register as a developer:
   - Accept terms
   - Verify your account (email/phone)

### Step 5: Create Facebook App

1. Go to: https://developers.facebook.com/apps/
2. Click **Create App**
3. Choose **Business** as app type
4. Fill in details:
   - **App name:** "ElvAgent" (or anything)
   - **App contact email:** your email
   - **Business account:** (optional, skip if none)
5. Click **Create App**

### Step 6: Add Instagram Product

1. In your app dashboard, find **Products** in left sidebar
2. Find **Instagram** → Click **Set Up**
3. This adds Instagram Graph API to your app

---

## Part 3: Get Your Credentials

### Step 7: Get Access Token

**Method 1: Quick Test Token (expires in 1 hour)**

1. Go to: **Tools** → **Graph API Explorer**
2. Select your app from dropdown
3. Click **Generate Access Token**
4. Check these permissions:
   - ✅ `instagram_basic`
   - ✅ `instagram_content_publish`
   - ✅ `pages_read_engagement`
5. Click **Generate Token**
6. **Copy the token** (save it temporarily)

**Method 2: Long-Lived Token (expires in 60 days) - RECOMMENDED**

After getting short-lived token above:

1. Go to: https://developers.facebook.com/tools/accesstoken/
2. Find your short-lived token
3. Click **"Extend Access Token"**
4. Copy the **long-lived token**

OR use this API call (replace `{short-lived-token}` and `{app-id}|{app-secret}`):
```bash
curl "https://graph.facebook.com/v18.0/oauth/access_token?grant_type=fb_exchange_token&client_id={app-id}&client_secret={app-secret}&fb_exchange_token={short-lived-token}"
```

### Step 8: Get Instagram Business Account ID

1. Still in Graph API Explorer
2. Change the endpoint to: `me/accounts`
3. Click **Submit**
4. Find your Facebook Page in the response
5. Copy the page's `access_token` and `id`

Now query with that page access token:
```
GET /{page-id}?fields=instagram_business_account
```

6. Copy the `instagram_business_account.id`

**OR use this simpler method:**

1. Go to: https://www.instagram.com/{your-username}/
2. View page source (Ctrl+U)
3. Search for: `"owner":{"id":"`
4. The number after is your Instagram User ID

---

## Part 4: Configure ElvAgent

### Step 9: Add Credentials to .env

Edit your `.env` file and add:

```bash
# Instagram
INSTAGRAM_ACCESS_TOKEN=your_long_lived_access_token_here
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_instagram_business_id_here
```

### Step 10: Test the Connection

```bash
source .venv/bin/activate
python scripts/test_instagram.py
```

**Expected output:**
```
Testing Instagram Publisher
============================================================

1. Initializing Instagram publisher...
2. Validating credentials...
✅ Credentials found

3. Generating images and formatting caption...

📸 Generated 5 images:
  1. data/images/newsletter_cards/intro.jpg
  2. data/images/newsletter_cards/item_1.jpg
  ...

📝 Caption (845 chars):
------------------------------------------------------------
🤖 AI News Update - Feb 16, 2026

Testing ElvAgent's automated Instagram posting...
...
```

---

## Part 5: App Review (For Production Use)

### Step 11: Submit for App Review

For **testing** (your own account): ✅ Works immediately

For **production** (posting regularly): Need approval

1. Go to your app → **App Review** → **Permissions and Features**
2. Request **Advanced Access** for:
   - `instagram_basic`
   - `instagram_content_publish`
3. Provide details:
   - **How you'll use it:** "Automated AI news newsletter posting"
   - **Video demo:** Record screen showing your app posting
   - **Test credentials:** Provide test account
4. Submit for review

**Approval time:** Usually 1-2 weeks

**For testing:** You can use Standard Access immediately with your own account!

---

## Troubleshooting

### Error: "Invalid OAuth access token"

**Solution:** Regenerate your access token (they expire)

### Error: "Unsupported post request"

**Solution:** Make sure your Instagram account is a **Business** account, not Creator or Personal

### Error: "User does not have permission to post"

**Solution:**
1. Check your app has `instagram_content_publish` permission
2. Make sure the access token includes this permission
3. Apply for App Review if using Production

### Error: "The Instagram account is not connected"

**Solution:** Go to Instagram Settings → Linked Accounts → Facebook and reconnect

### Images not showing up

**Solution:**
1. Check images are generated: `ls data/images/newsletter_cards/`
2. Images must be JPG format
3. Images should be under 8MB each

---

## Testing Checklist

Before posting to Instagram:

- [ ] Instagram converted to Business account
- [ ] Facebook Page created and linked
- [ ] Facebook Developer App created
- [ ] Instagram product added to app
- [ ] Access token generated and added to .env
- [ ] Business Account ID added to .env
- [ ] Test script runs without credential errors
- [ ] Images generate successfully
- [ ] Caption formats correctly

---

## What Gets Posted

ElvAgent posts **carousel posts** with:

1. **Intro card** - Newsletter summary, date, item count
2. **Item cards** - Each AI news item (up to 8)
   - Title
   - Summary
   - Category badge
   - Relevance score
3. **Outro card** - Call-to-action, branding

**Caption includes:**
- Summary
- Numbered list of items
- All links
- Relevant hashtags
- Branding

**Example post:** Swipe through 3-5 beautifully designed cards showing today's AI news

---

## Next Steps

Once Instagram is working:

1. Add to production cycle:
   ```python
   publishers = [
       InstagramPublisher(),
       TwitterPublisher(),  # (when Twitter elevated access approved)
       MarkdownPublisher()
   ]
   ```

2. Schedule hourly posts

3. Monitor engagement

4. Adjust image designs based on performance

---

## Need Help?

Common resources:
- Instagram Graph API Docs: https://developers.facebook.com/docs/instagram-api
- Graph API Explorer: https://developers.facebook.com/tools/explorer/
- Access Token Debugger: https://developers.facebook.com/tools/debug/accesstoken/

Issues? Check the troubleshooting section above or review error logs in the test script output.
