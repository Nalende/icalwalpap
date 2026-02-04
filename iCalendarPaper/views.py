# -*- coding: utf-8 -*-
import os, io, json, re, uuid, textwrap, threading
from datetime import datetime, timezone, timedelta
from flask import render_template, request, send_file, jsonify, make_response, url_for, session
from iCalendarPaper import app
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont

# 1. YAPILANDIRMA VE DINAMIK YOLLAR
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "credentials.json")
SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Environment Variables'dan OAuth credentials oku (Render.com için)
def get_client_config():
    """
    Environment variables'dan OAuth credentials oku.
    Fallback: Local development için credentials.json kullan.
    """
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    if client_id and client_secret:
        # Production: Environment variables kullan
        return {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }
    elif os.path.exists(CLIENT_SECRETS_FILE):
        # Local development: credentials.json kullan
        with open(CLIENT_SECRETS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

# 2. SESSION YÖNETİMİ
sessions_lock = threading.Lock()
_SESSIONS_CACHE = {}

def init_sessions():
    global _SESSIONS_CACHE
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                _SESSIONS_CACHE = json.load(f)
        except: _SESSIONS_CACHE = {}
init_sessions()

def save_session(session_id, data):
    with sessions_lock:
        _SESSIONS_CACHE[session_id] = data
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(_SESSIONS_CACHE, f, indent=2, ensure_ascii=False)

# 3. ROTALAR
@app.route('/')
def home(): return render_template('index.html')

@app.route('/oauth/init', methods=['POST'])
def oauth_init():
    client_config = get_client_config()
    if not client_config:
        return jsonify({'error': 'OAuth credentials bulunamadı. GOOGLE_CLIENT_ID ve GOOGLE_CLIENT_SECRET ayarlanmalı.'}), 500
    
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = url_for('oauth_callback', _external=True)
    auth_url, state = flow.authorization_url(access_type='offline', prompt='consent')
    session['oauth_state'] = state
    return jsonify({'auth_url': auth_url})

@app.route('/oauth/callback')
def oauth_callback():
    client_config = get_client_config()
    if not client_config:
        return "OAuth credentials bulunamadı", 500
    
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = url_for('oauth_callback', _external=True)
    flow.fetch_token(authorization_response=request.url)
    return f"""<script>window.opener.postMessage({{type:'oauth_success',token:{json.dumps(flow.credentials.to_json())}}},'*');window.close();</script>"""

@app.route('/create-session', methods=['POST'])
def create_session():
    data = request.get_json()
    sid = data.get('custom_id') or str(uuid.uuid4())
    save_session(sid, {
        'width': int(data['width']), 'height': int(data['height']),
        'api_key': data['api_key'], 'oauth_token': data['oauth_token']
    })
    return jsonify({'success': True, 'master_link': f"{request.host_url}generate/{sid}"})

# 4. AKILLI WALLPAPER ÜRETİM MERKEZİ
@app.route('/generate/<session_id>')
def generate_wallpaper(session_id):
    data = _SESSIONS_CACHE.get(session_id)
    if not data: return "Link geçersiz", 404

    try:
        # A. Takvim Verisi Çekme (30 günlük periyod)
        creds = Credentials.from_authorized_user_info(json.loads(data['oauth_token']))
        service = build('calendar', 'v3', credentials=creds)
        
        now = datetime.now(timezone.utc)
        thirty_days_later = now + timedelta(days=30)
        
        events = service.events().list(
            calendarId='primary', 
            timeMin=now.isoformat(), 
            timeMax=thirty_days_later.isoformat(),
            maxResults=20,  # Daha fazla etkinlik çek
            singleEvents=True, 
            orderBy='startTime'
        ).execute().get('items', [])
        
        # Etkinliklerin TÜM detaylarını çıkar (başlık + konum + açıklama)
        def get_event_details(e):
            title = e.get('summary', 'Başlıksız')
            location = e.get('location', '')
            description = e.get('description', '')
            start_str = e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))
            
            # Başlangıç zamanını parse et
            try:
                if 'T' in start_str:
                    start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    start_time = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except:
                start_time = now + timedelta(days=30)  # Parse edilemezse uzak gelecekte say
            
            # Kalan süreyi hesapla (SAAT BAZLI)
            time_until = start_time - now
            total_hours_until = time_until.total_seconds() / 3600  # TOPLAM SAAT
            days_until = time_until.days
            
            return {
                'title': title,
                'location': location,
                'description': description,
                'start_time': start_time,
                'start_str': start_str,
                'days_until': days_until,
                'total_hours_until': round(total_hours_until, 1),
                'full_info': f"{title}" + (f" - Konum: {location}" if location else "") + (f" - Detay: {description[:100]}" if description else "")
            }
        
        events_details = [get_event_details(e) for e in events]
        
        # 24 SAAT veya daha az kaldıysa → sıradaki etkinliğe öncelik
        next_event = events_details[0] if events_details else None
        use_next_event = False
        
        if next_event and (next_event['total_hours_until'] <= 24):
            use_next_event = True
            selected_event_info = f"ACIL ETKİNLİK (24 saat veya daha az kaldı!):\n{next_event['full_info']}\nKalan süre: {next_event['total_hours_until']} saat"
        else:
            # 30 günlük tüm etkinlikleri Gemini'ye gönder, en önemlisini seçsin
            events_summary = "\n".join([
                f"- {e['full_info']} (Kalan: {e['total_hours_until']} saat / {e['days_until']} gün)" 
                for e in events_details[:10]  # İlk 10 etkinlik
            ]) or "Önümüzdeki 30 gün için planlanmış etkinlik yok."
            selected_event_info = events_summary

        # B. Gemini Pro ile Etkinlik Analizi
        client = genai.Client(api_key=data['api_key'])
        
        analyze_prompt = f"""Sen bir tasarım direktörüsün. Görsel, metin ve font arasında MÜKEMMEL UYUM sağlayacaksın.

Kullanıcının takvim bilgileri:
{selected_event_info}

{'🚨 ACİL: Bu etkinlik 24 saat içinde!' if use_next_event else '''ÖNEM KRİTERLERİ:
1. Kullanıcının KENDİ doğum günü → EN YÜKSEK
2. Evlilik yıldönümü, romantik günler
3. Aile özel günleri
4. Sağlık randevuları
5. İş toplantıları
6. Diğer
TARİH YAKINLIĞI ÖNEMSİZ!'''}

GÖREV 1: En önemli etkinliği seç.

GÖREV 2: Bu etkinlik için bir MOOD/ENERJİ belirle:
⭐ TERCİH EDİLEN (yüksek ihtimalle bunlardan birini seç):
- "dark_humor" = Kara mizah, alaycı (ağlayan pasta, kaçan takvim, zombie ikonu)
- "sarcastic" = İğneleyici, ironik (göz deviren emoji, bored yüz)

DİĞER SEÇENEKLER:
- "cheerful" = Neşeli, pozitif (gülen yüz, konfeti)
- "serious" = Ciddi, resmi (düz çizgiler, minimal)
- "cute" = Ponçik, tatlı (yuvarlak hatlar, sevimli)
- "motivational" = Motive edici, güçlü (yumruk, alev)

GÖREV 3: Seçtiğin MOOD'a UYGUN Türkçe mesaj yaz (max 12 kelime).
- Mesaj ve görsel AYNI enerjiyi taşımalı!
- DARK HUMOR VE SARCASTİK MESAJLAR TERCİH EDİLİR!
- dark_humor: "Hediye almayı unutursan, arkadaşlığınız biter.", "Geç kalırsan, seni beklemezler."
- sarcastic: "Evet, yine bir toplantı. Şaşırdın mı?", "Vay be, yine bir randevu. Heyecan verici."
- cheerful: "Harika bir gün olacak, keyfine bak!"
- serious: "Toplantını unutma. Hazırlıklı git."
- cute: "Bugün senin günün, süper olacak!"
- motivational: "Bugün fark yaratacaksın, git ve kazan!"

GÖREV 4: Seçtiğin MOOD'a UYGUN sticker konsepti yaz (İNGİLİZCE, max 20 kelime).
- Mesajla AYNI enerjiyi taşımalı!
- dark_humor: "a birthday cake crying because no one came"
- cheerful: "a happy dancing calendar throwing confetti"
- serious: "a clean minimalist briefcase with a clock"
- cute: "a chubby heart character hugging a gift box"
- sarcastic: "an eye-rolling clock looking bored"
- motivational: "a fist breaking through a wall"

GÖREV 5: Bu tasarıma uygun Google Font öner (GERÇEK font adı):
⛔ YASAK: Bold, kalın, italik fontlar KULLANMA!
✅ SADECE REGULAR weight, okunabilir fontlar:
- "Nunito", "Poppins", "Open Sans", "Roboto", "Lato", "Montserrat"
- "Noto Sans", "Source Sans Pro", "Inter", "Quicksand"
- "Comfortaa", "Varela Round", "Mulish", "Karla"

❗ TÜRKÇE KARAKTER DESTEKLEYEN FONTLARI SEÇ!

ÖNEMLİ: Mesaj, sticker ve font AYNI MOOD'u yansıtmalı!

SADECE JSON formatında cevap ver:
{{"event_name": "...", "mood": "dark_humor/cheerful/serious/cute/sarcastic/motivational", "message": "...", "sticker_concept": "...", "google_font": "Font Adı"}}"""

        analysis_resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=analyze_prompt
        )
        
        # JSON parse
        response_text = analysis_resp.text.strip()
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            analysis = json.loads(response_text)
        
        sticker_concept = analysis.get('sticker_concept', 'a simple calendar icon')
        friendly_message = analysis.get('message', analysis.get('friendly_message', 'Etkinliğini unutma!'))
        mood = analysis.get('mood', 'cheerful')
        google_font = analysis.get('google_font', 'Poppins')

        # C. Imagen 4 ile Sticker Tarzı Görsel Üretimi
        imagen_prompt = f"""Sticker design, minimalist and quirky illustration style, showcased on a simple white background.

MAIN SUBJECT: {sticker_concept}

STYLE REQUIREMENTS:
- Clean white illustration with minimal grey shading lines
- NO logos, NO text, NO letters, NO numbers, NO symbols
- Thin, consistent line work OR flat color shapes
- Die-cut sticker appearance around the main subject
- Simple and flat lighting suitable for graphic illustration

MOOD: Surreal, humorous, relaxed, internet culture aesthetic
- Captures a specific kind of cool, detached humor
- Slightly absurd or quirky interpretation

CRITICAL RULES:
- ABSOLUTELY NO TEXT anywhere
- NO watermarks, NO signatures
- Clean, minimal, sophisticated
- White/light grey color palette only

Aspect ratio: 9:16 portrait for mobile wallpaper.
The sticker should be centered with plenty of white space around it."""

        img_resp = client.models.generate_images(
            model="imagen-4.0-generate-001", 
            prompt=imagen_prompt,
            config=types.GenerateImagesConfig(
                aspect_ratio="9:16",
                number_of_images=1
            )
        )
        
        # D. Görsel İşleme ve Metin Giydirme (Python PIL ile)
        img = Image.open(io.BytesIO(img_resp.generated_images[0].image.image_bytes)).convert('RGBA')
        img = img.resize((data['width'], data['height']), Image.LANCZOS)
        
        # Google Fonts'tan font indir ve yükle (REGULAR weight - okunabilir)
        font_size = int(data['width'] * 0.045)  # Daha uygun boyut
        font = None
        
        try:
            # Google Fonts API'den REGULAR font indir (italik değil!)
            font_name_url = google_font.replace(' ', '+')
            # Regular weight için wght@400 kullan
            font_api_url = f"https://fonts.googleapis.com/css2?family={font_name_url}:wght@400&display=swap"
            
            import requests
            css_response = requests.get(font_api_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=5)
            
            if css_response.status_code == 200:
                # CSS'ten font URL'sini çıkar (woff2 veya ttf)
                import re as regex
                # Önce latin subset'i dene
                font_url_match = regex.search(r'src: url\((https://fonts\.gstatic\.com/[^)]+)\)', css_response.text)
                if font_url_match:
                    font_url = font_url_match.group(1)
                    font_response = requests.get(font_url, timeout=10)
                    if font_response.status_code == 200:
                        font = ImageFont.truetype(io.BytesIO(font_response.content), font_size)
        except Exception as e:
            pass
        
        # Fallback fontlar (okunabilir, düz fontlar)
        if font is None:
            fallback_fonts = ['arial.ttf', 'segoeui.ttf', 'calibri.ttf', 'verdana.ttf']
            for fb_font in fallback_fonts:
                try:
                    font = ImageFont.truetype(fb_font, font_size)
                    break
                except:
                    continue
        
        if font is None:
            font = ImageFont.load_default()
        
        # %8 margin hesapla (sağdan ve soldan)
        margin = int(data['width'] * 0.08)
        max_text_width = data['width'] - (2 * margin)
        
        # Metin wrap - karakter sayısını genişliğe göre hesapla
        avg_char_width = font_size * 0.55
        chars_per_line = int(max_text_width / avg_char_width)
        wrapped_text = textwrap.fill(friendly_message, width=max(chars_per_line, 20))
        
        # Metni görselin alt kısmına yerleştir (sticker'ın altında)
        text_y = int(data['height'] * 0.80)
        text_x = data['width'] // 2
        
        draw = ImageDraw.Draw(img)
        
        # Sadece ana metin (gölgesiz, temiz ve okunabilir)
        draw.multiline_text(
            (text_x, text_y), 
            wrapped_text, 
            fill=(0, 0, 0, 255),  # Tam siyah
            font=font, 
            anchor="mm", 
            align="center"
        )
        
        # RGB'ye dönüştür (PNG kaydetmek için)
        img = img.convert('RGB')

        # E. Sonucu Döndür
        buf = io.BytesIO()
        img.save(buf, format='PNG', quality=95)
        buf.seek(0)
        
        resp = make_response(send_file(buf, mimetype='image/png'))
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return resp
        
    except Exception as e: 
        import traceback
        return f"Hata detayı: {str(e)}\n\nTraceback:\n{traceback.format_exc()}", 500


# 5. DEBUG SAYFASI - TÜM AI GİRDİ/ÇIKTILARI
@app.route('/debug/<session_id>')
def debug_wallpaper(session_id):
    """AI'ya giden ve gelen tüm verileri göster - görsel üretmeden"""
    data = _SESSIONS_CACHE.get(session_id)
    if not data: return jsonify({"error": "Link geçersiz"}), 404

    debug_info = {
        "session_id": session_id,
        "session_data": {
            "width": data.get('width'),
            "height": data.get('height'),
            "api_key": data.get('api_key', '')[:10] + "..." if data.get('api_key') else None
        },
        "steps": []
    }

    try:
        # ADIM 1: Takvim Verisi Çekme
        creds = Credentials.from_authorized_user_info(json.loads(data['oauth_token']))
        service = build('calendar', 'v3', credentials=creds)
        
        now = datetime.now(timezone.utc)
        thirty_days_later = now + timedelta(days=30)
        
        events = service.events().list(
            calendarId='primary', 
            timeMin=now.isoformat(), 
            timeMax=thirty_days_later.isoformat(),
            maxResults=20,
            singleEvents=True, 
            orderBy='startTime'
        ).execute().get('items', [])
        
        # Ham etkinlik verileri
        raw_events = []
        for e in events:
            raw_events.append({
                "summary": e.get('summary', 'Başlıksız'),
                "location": e.get('location', ''),
                "description": e.get('description', '')[:200] if e.get('description') else '',
                "start": e.get('start', {}),
                "end": e.get('end', {})
            })
        
        debug_info["steps"].append({
            "step": 1,
            "name": "Google Calendar API",
            "input": f"30 günlük etkinlik isteği (max 20)",
            "output": raw_events,
            "event_count": len(events)
        })
        
        # ADIM 2: Etkinlik Detayları İşleme
        def get_event_details(e):
            title = e.get('summary', 'Başlıksız')
            location = e.get('location', '')
            description = e.get('description', '')
            start_str = e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))
            
            try:
                if 'T' in start_str:
                    start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    start_time = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except:
                start_time = now + timedelta(days=30)
            
            time_until = start_time - now
            days_until = time_until.days
            hours_until = time_until.seconds // 3600
            
            return {
                'title': title,
                'location': location,
                'description': description[:100] if description else '',
                'start_time': start_time.isoformat(),
                'days_until': days_until,
                'hours_until': hours_until,
                'full_info': f"{title}" + (f" - Konum: {location}" if location else "") + (f" - Detay: {description[:100]}" if description else "")
            }
        
        events_details = [get_event_details(e) for e in events]
        
        # 1 gün kuralı kontrolü
        next_event = events_details[0] if events_details else None
        use_next_event = False
        
        if next_event and (next_event['days_until'] < 1):
            use_next_event = True
            selected_event_info = f"SIRADAKİ ETKİNLİK (1 günden az kaldı!):\n{next_event['full_info']}\nKalan süre: {next_event['hours_until']} saat"
        else:
            events_summary = "\n".join([
                f"- {e['full_info']} (Tarih: {e['start_time']}, Kalan: {e['days_until']} gün)" 
                for e in events_details[:10]
            ]) or "Önümüzdeki 30 gün için planlanmış etkinlik yok."
            selected_event_info = events_summary
        
        debug_info["steps"].append({
            "step": 2,
            "name": "Etkinlik İşleme",
            "use_next_event": use_next_event,
            "next_event_details": next_event,
            "all_events_details": events_details[:5],  # İlk 5 etkinlik
            "selected_event_info": selected_event_info
        })
        
        # ADIM 3: Gemini Prompt Oluşturma
        analyze_prompt = f"""Sen sıcakkanlı bir arkadaş ve yaratıcı sanat yönetmenisin. Kullanıcının duvar kağıdı için kişiselleştirilmiş bir deneyim yaratacaksın.

Kullanıcının takvim bilgileri:
{selected_event_info}

{'Bu etkinlik çok yakın, ona odaklan!' if use_next_event else 'Tüm etkinlikleri değerlendir ve en anlamlı/önemli olanı seç.'}

GÖREV 1: Odaklanılacak etkinliği belirle. Etkinliğin TÜM detaylarına bak:
- Başlık ne söylüyor?
- Konum neresi? (Hastane mi, restoran mı, ofis mi?)
- Açıklamada ne yazıyor?

GÖREV 2: Bu etkinliği temsil edecek 1-3 adet minimalist ikon tarifi yaz (İNGİLİZCE).
- Sadece ikon tarifi, hiç yazı/numara/etiket OLMAYACAK
- Stil: İnce çizgili, zarif, tek renkli
- Örnek: steteskop, takvim sayfası, kalp, uçak, pasta dilimi

GÖREV 3: Türkçe 5-8 kelimelik SAMİMİ, SICAK bir mesaj yaz.
- Sanki yakın bir arkadaşın mesaj atıyor gibi
- ETKİNLİĞİN ADINI YAZMA, dolaylı hatırlat
- KONUMDAKİ BİLGİYİ KULLAN (hastane ise sağlık dileği, restoran ise afiyet olsun vb.)
- Robotik olma, içten ol

ÖRNEKLER:
- Hastane randevusu → "Sağlıklı günler diliyorum, kendine iyi bak!"
- Diş hekimi → "O güzel gülüşün için, geçmiş olsun!"
- Doğum günü → "Bugün senin günün, harika kutlamalar!"
- Toplantı → "İçindeki gücü göster, başaracaksın!"
- Evlilik yıldönümü → "Sevginiz daim olsun, tebrikler!"

SADECE JSON formatında cevap ver:
{{"event_name": "...", "icon1": "simple line art of ...", "icon2": "simple line art of ...", "icon3": "", "friendly_message": "..."}}"""

        debug_info["steps"].append({
            "step": 3,
            "name": "Gemini Prompt (INPUT)",
            "model": "gemini-2.0-flash",
            "prompt": analyze_prompt
        })
        
        # ADIM 4: Gemini Çağrısı
        client = genai.Client(api_key=data['api_key'])
        analysis_resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=analyze_prompt
        )
        
        response_text = analysis_resp.text.strip()
        
        debug_info["steps"].append({
            "step": 4,
            "name": "Gemini Response (OUTPUT)",
            "raw_response": response_text
        })
        
        # JSON parse
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            analysis = json.loads(response_text)
        
        icon1 = analysis.get('icon1', analysis.get('icon1_description', 'simple line art of a calendar'))
        icon2 = analysis.get('icon2', analysis.get('icon2_description', ''))
        icon3 = analysis.get('icon3', '')
        friendly_message = analysis.get('friendly_message', 'Harika bir gün geçir!')
        
        debug_info["steps"].append({
            "step": 5,
            "name": "Gemini Parsed Data",
            "parsed_json": analysis,
            "extracted": {
                "icon1": icon1,
                "icon2": icon2,
                "icon3": icon3,
                "friendly_message": friendly_message
            }
        })
        
        # ADIM 5: Imagen Prompt
        icons_list = [icon1]
        if icon2: icons_list.append(icon2)
        if icon3: icons_list.append(icon3)
        
        icons_description = "\n".join([f"  - {icon}" for icon in icons_list])
        icon_count = len(icons_list)
        
        imagen_prompt = f"""Professional mobile phone wallpaper design:

BACKGROUND:
- Deep warm chocolate brown gradient
- Soft, dreamy bokeh light effects scattered throughout
- Golden and cream colored blurred circles creating depth
- NO text, NO labels, NO watermarks, NO hashtags, NO color codes

CENTER COMPOSITION ({icon_count} icon{"s" if icon_count > 1 else ""}):
{icons_description}

ICON STYLING:
- Cream/beige colored thin line art only
- Elegant, minimal, single stroke style
- Icons arranged with professional design sensibility
- Different sizes for visual hierarchy if multiple icons
- Slightly overlapping or artistically positioned

CRITICAL RULES:
- ABSOLUTELY NO TEXT anywhere on the image
- NO numbers, NO letters, NO symbols, NO hashtags
- NO color codes like #FFF8DC or #2D1810
- NO watermarks or signatures
- Clean, premium, sophisticated aesthetic

Small decorative 4-pointed star element in bottom right corner.
Aspect ratio: 9:16 portrait.
Mood: Warm, cozy, luxurious, minimalist."""

        debug_info["steps"].append({
            "step": 6,
            "name": "Imagen Prompt (INPUT)",
            "model": "imagen-4.0-generate-001",
            "prompt": imagen_prompt,
            "note": "Bu prompt ile görsel üretilecek (debug modunda görsel üretilmez)"
        })
        
        debug_info["final_message"] = friendly_message
        debug_info["success"] = True
        
    except Exception as e:
        import traceback
        debug_info["error"] = str(e)
        debug_info["traceback"] = traceback.format_exc()
        debug_info["success"] = False
    
    # HTML formatında güzel görüntüle
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Debug - {session_id}</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
            .step {{ background: #16213e; border-radius: 10px; padding: 15px; margin: 15px 0; }}
            .step-header {{ color: #e94560; font-size: 18px; font-weight: bold; }}
            pre {{ background: #0f0f23; padding: 15px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; }}
            .success {{ color: #4ade80; }}
            .error {{ color: #ef4444; }}
            h1 {{ color: #e94560; }}
            h2 {{ color: #00d9ff; }}
        </style>
    </head>
    <body>
        <h1>🔍 Debug Panel</h1>
        <p>Session: <code>{session_id}</code></p>
        <p>Status: <span class="{'success' if debug_info.get('success') else 'error'}">{'✅ Success' if debug_info.get('success') else '❌ Error'}</span></p>
        
        <h2>📋 Debug Data (JSON)</h2>
        <pre>{json.dumps(debug_info, indent=2, ensure_ascii=False, default=str)}</pre>
        
        <p><a href="/generate/{session_id}" style="color: #00d9ff;">→ Görsel Üret</a></p>
    </body>
    </html>
    """
    return html