# iCalendarPaper - AI Wallpaper Generator

iCalendarPaper is a Flask-based web application that generates personalized, aesthetic wallpapers by integrating with Google Calendar. It uses Google Gemini for context-aware mood analysis and Google Imagen for creating unique sticker-style illustrations.

## Features

- **Google Calendar Integration**: Automatically fetches and prioritizes upcoming events.
- **AI-Powered Design**: Uses Google Gemini to determine the "mood" of an event (e.g., Sarcastic, Cheerful, Serious) and generates matching text.
- **Custom Illustrations**: Generates unique, minimalist sticker-style artwork using Google Imagen.
- **Dynamic Typography**: Selects and downloads Google Fonts that match the event's mood.
- **Secure Handling**: Encrypted session management for sensitive API keys.

## Deployment & Setup

### Prerequisites

- Python 3.10+
- Google Cloud Project with the following APIs enabled:
    - Google Calendar API
    - Google Gemini API (Vertex AI or AI Studio)

### Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/iCalendarPaper.git
   cd iCalendarPaper
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Place your Google Cloud OAuth 2.0 Client ID file as `credentials.json` in the project root.
   *(Note: This file is sensitive and excluded from the repository. You must generate your own via Google Cloud Console.)*

4. **Run the application:**
   ```bash
   python runserver.py
   ```
   Visit `http://localhost:5000` in your browser.

### Deployment (Render.com)

1. **New Web Service:** Connect your GitHub repository to Render.
2. **Runtime:** Select `Python 3`.
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `gunicorn runserver:app`
5. **Environment Variables:**
   - `PYTHON_VERSION`: `3.10.0`
   - `FLASK_SECRET_KEY`: (Generate a strong random string)
   - `ICALENDAR_SECRET_KEY`: (Generate a strong random string for session encryption)
   - `OAUTHLIB_INSECURE_TRANSPORT`: `1` (Only if testing HTTP, otherwise remove for Production HTTPS)

## Project Structure

- `iCalendarPaper/`: Core application package.
  - `views.py`: Main application logic, AI prompting, and image processing.
  - `models.py`: Database models for session management.
  - `templates/`: HTML templates (Single Page Application design).
  - `static/`: Static assets and font cache.
- `runserver.py`: Application entry point.
- `Procfile`: Process file for deployment platforms like Render/Heroku.

## License

This project is open source and available under the [MIT License](LICENSE).
