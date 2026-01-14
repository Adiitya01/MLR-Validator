# GEO Analytics - Test Guide for Ethosh Digital

## Quick Start

### 1. Start the Application

**Backend (Terminal 1):**
```powershell
cd C:\Users\aditya.pasare\Desktop\GEO
python server.py
```
*Server will run at: http://localhost:8000*

**Frontend (Terminal 2):**
```powershell
cd C:\Users\aditya.pasare\Desktop\GEO\frontend
npm run dev
```
*App will run at: http://localhost:3000*

---

## 2. Test with Ethosh Digital

### Option A: Using the Web Interface

1. Open browser: **http://localhost:3000**

2. Fill in the form:
   - **Company Website:** `https://www.ethosh.com`
   - **Manual Points:** Copy-paste this:

```
Company: Ethosh Digital

Core Business: A global digital experience agency specializing in high-end visual communication and immersive technologies (AR/VR/MR).

Primary Industries: Strong focus on Life Sciences, Healthcare, Medical Devices, and Engineering/Manufacturing sectors.

Key Services: 
- Digital Interactive Experiences
- XR (Augmented, Virtual, and Mixed Reality)
- 3D Product Demonstrations
- Visual Storytelling for complex products

Value Proposition: Simplifies complex medical and technical concepts through interactive 3D visuals and immersive simulations for marketing, sales training, and patient education.

Global Presence: Operates with teams in India and the USA, serving global Fortune 500 clients.

Specific Use Cases: Virtual Operating Rooms, Interactive 3D Medical Device walkthroughs, and technical training simulations.
```

3. Click **"Start Analysis"**
   - Wait for the AI to analyze the company
   - You should see ~20 generated test prompts

4. Test Individual Prompts:
   - Click on any prompt card
   - Click **"Gemini Check"** to test standard AI response
   - Click **"Google Search"** to test with Google Search grounding
   - Compare the results side-by-side

5. Run Full Audit:
   - Click **"Run Full Visibility Audit"**
   - Get an overall visibility score (0-100)
   - View key findings and optimization tips

---

### Option B: Using the Test Script

Run the automated test:
```powershell
python test_ethosh.py
```

This will:
1. Analyze Ethosh automatically
2. Test a prompt with Gemini
3. Test the same prompt with Google Search
4. Show you the results in the terminal

---

## What to Look For

### ✅ Success Indicators:
- Company name shows as "Ethosh Digital" (not "Unknown" or "Pending Analysis")
- Industry is correctly identified
- 20 diverse test prompts are generated
- Gemini Check returns a response
- Google Search Check returns a grounded response
- Toast notifications appear for each action
- No red error messages

### ❌ Common Issues Fixed:
1. **"Unknown" company name** → Fixed by improving summarizer
2. **"Evaluation failed" error** → Fixed Google Search API syntax
3. **500 Internal Server Error** → Fixed JSON parsing for list responses
4. **Website scraping blocked** → Added browser User-Agent headers

---

## Features to Test

### 1. Analysis Phase
- [ ] URL scraping works
- [ ] Manual points are incorporated
- [ ] Company name is extracted correctly
- [ ] Industry is identified
- [ ] 20 prompts are generated

### 2. Evaluation Phase
- [ ] Gemini Check works for individual prompts
- [ ] Google Search Check works (grounded results)
- [ ] Results show brand presence (✓ or ✗)
- [ ] Recommendation rank is displayed
- [ ] Competitors are listed

### 3. UI/UX
- [ ] Toast notifications appear
- [ ] Hover preview works
- [ ] Click for persistent modal works
- [ ] Loading states show correctly
- [ ] Error messages are clear

### 4. Full Audit
- [ ] "Run Full Visibility Audit" completes
- [ ] Overall score (0-100) is calculated
- [ ] Key findings are shown
- [ ] Optimizer tips are provided

---

## Troubleshooting

### If you see "Pending Analysis..." or "Unknown":
1. Check if backend is running (`python server.py`)
2. Restart the backend server
3. Make sure you filled in Manual Points
4. Check browser console for errors (F12)

### If Google Search fails:
1. Verify your Gemini API key supports grounding
2. Check backend terminal for error messages
3. Try Gemini Check first to isolate the issue

### If nothing loads:
1. Verify both servers are running
2. Check ports: Backend (8000), Frontend (3000)
3. Clear browser cache and reload

---

## Expected Results for Ethosh

When testing with Ethosh, you should see prompts like:
- "What are the best XR agencies for medical device training?"
- "Top companies for interactive 3D product demonstrations in life sciences"
- "How can AR/VR improve patient education in healthcare?"
- "Who are the leaders in immersive technology for pharma?"

**Brand Visibility:**
- Ethosh may or may not appear in standard Gemini responses (depends on training data)
- Google Search grounding should improve visibility if Ethosh has good SEO

---

## Files Modified (Latest Session)

### Backend:
- `app/evaluator.py` - Fixed Google Search API syntax
- `app/summarizer.py` - Improved JSON parsing and fallbacks
- `app/schemas.py` - Better default values
- `app/website_loader.py` - Added User-Agent headers

### Frontend:
- `src/app/page.js` - Enhanced error handling and toast notifications

### Test Files:
- `test_ethosh.py` - Automated test script

---

## Next Steps

1. ✅ Test the basic flow with Ethosh
2. Try other companies to verify robustness
3. Export results for reporting
4. Customize prompts based on your needs

---

**Need Help?** Check the backend terminal for detailed logs and error messages.
