# 📅 iCalendarPaper: Your Life, Reimagined as Art.

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![Render](https://img.shields.io/badge/Render-Deployed-46E3B7.svg)](https://icalwalpaper.onrender.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **"Don't just check your calendar, *wear* it."**
> Turn your boring Google Calendar schedule into a stunning, AI-generated wallpaper that reflects your day's mood and priorities.

🚀 **[LIVE DEMO: Try it now!](https://icalwalpaper.onrender.com)**

---

## ✨ What is iCalendarPaper?

iCalendarPaper is an intelligent web application that connects to your **Google Calendar**, analyzes your upcoming events using **Google Gemini 2.0 AI**, and generates a custom, artistic wallpaper using **Google Imagen 3**.

It's not just a background; it's a visual summary of your day - stylized as a premium **die-cut sticker** on a sleek dark background (`#000000`), perfect for modern OLED screens.

### 🌟 Key Features

-   **🧠 Smart Analysis:** Uses **Gemini 2.0 Flash** to understand if your day is "Busy", "Chill", "Creative", or "Stressful" and selects a matching mood.
-   **🎨 Generative Art:** Creates unique, high-contrast, die-cut sticker art for your phone's lock screen.
-   **🔄 Persistent Sessions:** Create a custom link (e.g., `/generate/my-link`) once, and it works forever. Your settings are saved securely in **PostgreSQL**.
-   **📱 Mobile First:** Fully responsive design with **glassmorphism UI**, optimized for all devices (supports `100dvh` & landscape modes).
-   **⚡ Rate Limit Handling:** Smart retry mechanisms ensure your wallpaper is generated even during peak API usage.

---

## 🛠️ Tech Stack

Built with modern web technologies and robust AI integrations:

-   **Backend:** Python 3.12, Flask, Gunicorn
-   **Database:** PostgreSQL (via SQLAlchemy)
-   **AI Engines:**
    -   🤖 **LLM:** Google Gemini 2.0 Flash (Prompt Engineering for Mood & Text)
    -   🖼️ **Image Gen:** Google Imagen 3 (High-quality Die-Cut Sticker Generation)
-   **Frontend:** HTML5, CSS3 (Glassmorphism), Vanilla JS (Particle Effects)
-   **Deployment:** Render.com (CI/CD connected to GitHub)

---

## 🚀 Installation & Setup

Want to run this locally? Follow these steps:

### 1. Clone the Repository
```bash
git clone https://github.com/Nalende/icalwalpap.git
cd icalwalpap
```

### 2. Install Dependencies
Ensure you have Python 3.12 installed.
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file or set environment variables:
```bash
# Google OAuth Credentials
export GOOGLE_CLIENT_ID="your_client_id"
export GOOGLE_CLIENT_SECRET="your_client_secret"

# Database (PostgreSQL or SQLite for local)
export DATABASE_URL="postgresql://user:pass@localhost/dbname" 
# OR use default SQLite for local testing
```

### 4. Run the App
```bash
python runserver.py
```
Visit `http://localhost:5000` in your browser.

---

## 🌍 Configuring for Production (Render.com)

1.  **Create a Web Service** on Render connected to this repo.
2.  **Environment Variables:**
    -   `PYTHON_VERSION`: `3.12.8`
    -   `DATABASE_URL`: (Connect a Render PostgreSQL database)
    -   `GOOGLE_CLIENT_ID` & `GOOGLE_CLIENT_SECRET`: From Google Cloud Console.
3.  **Build Command:** `pip install -r requirements.txt`
4.  **Start Command:** `gunicorn runserver:app`

---

## 🖼️ Gallery

*(Screenshots of the beautiful UI and generated wallpapers coming soon!)*

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

[MIT](https://choosealicense.com/licenses/mit/)
