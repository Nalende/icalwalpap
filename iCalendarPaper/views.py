# -*- coding: utf-8 -*-
"""
iCalendarPaper - Ana görünüm modülü
AI destekli kişiselleştirilmiş duvar kağıdı üretimi
"""

import base64
import binascii
import hashlib
import io
import json
import os
import re
import textwrap
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from functools import lru_cache

from flask import render_template, request, send_file, jsonify, make_response, url_for, session
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont
import requests

from iCalendarPaper import app, db
from iCalendarPaper.models import SessionData

# =============================================================================
# 1. YAPILANDIRMA VE SABİTLER
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "credentials.json")
SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")
FONT_CACHE_DIR = os.path.join(BASE_DIR, "static", "fonts", "cache")
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Development için localhost HTTP'ye izin ver (production'da HTTPS kullan)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


def get_client_config() -> dict | None:
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

# Görsel tasarım sabitleri
MARGIN_RATIO = 0.08  # Ekran genişliğinin %8'i
FONT_SIZE_RATIO = 0.045  # Ekran genişliğinin %4.5'i
TEXT_Y_POSITION_RATIO = 0.80  # Ekran yüksekliğinin %80'i

# Şifreleme için secret key (production'da environment variable'dan al)
ENCRYPTION_KEY = os.environ.get('ICALENDAR_SECRET_KEY', 'dev-secret-key-change-in-production')

# =============================================================================
# 2. YARDIMCI FONKSİYONLAR
# =============================================================================


def simple_encrypt(data: str) -> str:
    """Basit XOR şifreleme (production için Fernet önerilir)"""
    key_bytes = hashlib.sha256(ENCRYPTION_KEY.encode()).digest()
    data_bytes = data.encode('utf-8')
    encrypted = bytes(d ^ key_bytes[i % len(key_bytes)] for i, d in enumerate(data_bytes))
    return base64.b64encode(encrypted).decode('utf-8')


def simple_decrypt(encrypted_data: str) -> str:
    """Basit XOR şifre çözme"""
    try:
        key_bytes = hashlib.sha256(ENCRYPTION_KEY.encode()).digest()
        data_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
        decrypted = bytes(d ^ key_bytes[i % len(key_bytes)] for i, d in enumerate(data_bytes))
        return decrypted.decode('utf-8')
    except (ValueError, TypeError, binascii.Error):
        return encrypted_data  # Eski şifrelenmemiş veri için fallback


def get_event_details(event: dict, now: datetime) -> dict:
    """
    Tek bir takvim etkinliğinin detaylarını çıkarır.
    DRY prensibi: Bu fonksiyon hem generate hem debug için kullanılır.
    """
    title = event.get('summary', 'Başlıksız')
    location = event.get('location', '')
    description = event.get('description', '')
    start_str = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))

    # Başlangıç zamanını parse et
    try:
        if 'T' in start_str:
            start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        else:
            start_time = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        start_time = now + timedelta(days=30)  # Parse edilemezse uzak gelecekte say

    # Kalan süreyi hesapla (SAAT BAZLI)
    time_until = start_time - now
    total_hours_until = time_until.total_seconds() / 3600
    days_until = time_until.days

    return {
        'title': title,
        'location': location,
        'description': description[:100] if description else '',
        'start_time': start_time,
        'start_str': start_str,
        'days_until': days_until,
        'total_hours_until': round(total_hours_until, 1),
        'full_info': f"{title}" + (f" - Konum: {location}" if location else "") + (f" - Detay: {description[:100]}" if description else "")
    }


def build_gemini_prompt(selected_event_info: str, use_next_event: bool) -> str:
    """
    Gemini için analiz prompt'unu oluşturur.
    Tek nokta: Hem generate hem debug aynı prompt'u kullanır.
    """
    return f"""Sen bir tasarım direktörüsün. Görsel, metin ve font arasında MÜKEMMEL UYUM sağlayacaksın.
YARATICILIK ÇOK ÖNEMLİ: Sıradanlıktan kaçın, özgün ve akılda kalıcı ol!

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
- "dark_humor" = Kara mizah, alaycı, absürt
- "sarcastic" = İğneleyici, ironik, sivri dilli

DİĞER SEÇENEKLER:
- "cheerful" = Neşeli, pozitif, enerjik
- "serious" = Ciddi, profesyonel, ağırbaşlı
- "cute" = Ponçik, tatlı, sevimli
- "motivational" = Motive edici, güçlü, ilham verici

GÖREV 3: YARATICI ve ÖZGÜN Türkçe mesaj yaz (max 12 kelime).
💡 YARATICILIK KURALLARI:
- BEKLENMEDİK açılar kullan, klişelerden kaçın
- ETKİNLİĞE ÖZGÜ detaylar ekle (randevu ise doktor/avukat/kuaför fark eder!)
- CESUR ol, sınırları zorla (ama saygılı kal)
- Örneklerden ESINLEN ama KOPYALAMA - kendi versiyonunu yarat!

İLHAM ÖRNEKLERI (bunları kullanma, benzeri yarat!):
- dark_humor: "İlaçlarını al, yoksa canavar geri gelir.", "Uyuyamazsan sabaha kadar bekle."
- sarcastic: "Bir saatlik toplantı. Beş dakikalık konu.", "E-posta da yollayabilirdin aslında."
- cheerful: "Konfetiler patlarken kendini hisset!", "Bugün senin şovun başlıyor!"
- serious: "Hazırlıksız gidersen pişman olursun.", "Profesyonellik zamanı, odaklan."
- cute: "Küçük kalpler büyük sevinçler getiriyor!", "Bugün seni gülümseten şeyler olacak!"
- motivational: "Bugün başarının tadını çıkaracaksın.", "Sen bu işi halledecek güçtesin!"

GÖREV 4: YARATICI ve GÖRSELLEŞTİRİLEBİLİR sticker konsepti (İNGİLİZCE, max 25 kelime).
💡 STICKER KURALLARI:
- Tekil, MERKEZİ karakter/obje (takvim, saat, kalp, pasta, kalem, vb)
- Absürt/unexpected DETAYLAR ekle
- DUYGU ve HAREKET belirt (crying, dancing, melting, exploding)
- Clean, white/grey LINES on SOLID BLACK background

İLHAM ÖRNEKLERI (bunları kullanma, benzeri yarat!):
- dark_humor: "a melting clock dripping into a coffee cup", "a calendar running away on tiny legs"
- cheerful: "a star-shaped cookie celebrating with sparkles", "a bouncing heart throwing tiny gifts"
- serious: "a geometric briefcase with sharp clean edges", "a minimalist pen standing tall"
- cute: "a smiling donut hugging a tiny spoon", "a chubby cloud raining hearts"
- sarcastic: "a yawning moon covering its mouth", "a bored pencil lying flat"
- motivational: "a lightning bolt cracking through darkness", "a rising sun with strong rays"

GÖREV 5: MOOD'a uygun Google Font (GERÇEK font adı, REGULAR weight):
✅ Türkçe destekli: "Nunito", "Poppins", "Open Sans", "Roboto", "Lato", "Montserrat", "Noto Sans", "Source Sans Pro", "Inter", "Quicksand", "Comfortaa", "Varela Round", "Mulish", "Karla"

🎯 ÖNEMLİ: Mesaj, sticker ve font AYNI MOOD'u yansıtmalı! ÖZGÜN OL!

SADECE JSON formatında cevap ver:
{{"event_name": "...", "mood": "dark_humor/cheerful/serious/cute/sarcastic/motivational", "message": "...", "sticker_concept": "...", "google_font": "Font Adı"}}"""


def build_imagen_prompt(sticker_concept: str) -> str:
    """Imagen için görsel üretim prompt'unu oluşturur."""
    return f"""Create a PURE DIE-CUT STICKER on a SOLID BLACK BACKGROUND (#000000).

🎯 MAIN SUBJECT: {sticker_concept}

🎨 VISUAL STYLE:
- Clean WHITE or LIGHT GREY illustration (NO other colors)
- Minimalist line art OR simple flat shapes
- Thin, consistent strokes with subtle grey shading
- Die-cut sticker aesthetic: subject is ISOLATED from background
- Quirky, playful, internet culture vibe

⚫ BACKGROUND RULES - CRITICAL:
- ENTIRE background MUST be SOLID BLACK (#000000)
- NO gradients, NO textures, NO patterns in background
- Sticker subject is the ONLY visible element
- Maximum contrast: white/grey subject on pure black
- Die-cut appearance: as if the sticker was physically cut out and placed on black surface

🚫 FORBIDDEN:
- ABSOLUTELY NO text, letters, numbers, symbols, words
- NO logos, watermarks, signatures
- NO additional background elements (stars, dots, lines)
- NO complex details - keep it SIMPLE and ICONIC

📐 COMPOSITION:
- Aspect ratio: 1:1 Square
- Subject centered with generous black space around it
- Focus on strong, recognizable silhouette
- Playful expression/pose that matches the mood

✨ MOOD: Surreal, witty, slightly absurd, memorable, shareable"""


@lru_cache(maxsize=20)
def get_cached_font(font_name: str, font_size: int) -> ImageFont.FreeTypeFont:
    """
    Font'u cache'den al veya indir.
    LRU cache ile memory'de tutulur, aynı font tekrar indirilmez.
    """
    # Önce cache dizininde ara
    os.makedirs(FONT_CACHE_DIR, exist_ok=True)
    safe_font_name = re.sub(r'[^a-zA-Z0-9]', '_', font_name)
    cached_font_path = os.path.join(FONT_CACHE_DIR, f"{safe_font_name}.ttf")

    # Cache'de varsa kullan
    if os.path.exists(cached_font_path):
        try:
            return ImageFont.truetype(cached_font_path, font_size)
        except Exception:
            pass  # Cache bozuksa devam et

    # Google Fonts'tan indir
    try:
        font_name_url = font_name.replace(' ', '+')
        font_api_url = f"https://fonts.googleapis.com/css2?family={font_name_url}:wght@400&display=swap"

        css_response = requests.get(
            font_api_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
            timeout=5
        )

        if css_response.status_code == 200:
            font_url_match = re.search(r'src: url\((https://fonts\.gstatic\.com/[^)]+)\)', css_response.text)
            if font_url_match:
                font_url = font_url_match.group(1)
                font_response = requests.get(font_url, timeout=10)
                if font_response.status_code == 200:
                    # Cache'e kaydet
                    with open(cached_font_path, 'wb') as f:
                        f.write(font_response.content)
                    return ImageFont.truetype(io.BytesIO(font_response.content), font_size)
    except Exception:
        pass

    # Fallback fontlar
    fallback_fonts = ['arial.ttf', 'segoeui.ttf', 'calibri.ttf', 'verdana.ttf']
    for fb_font in fallback_fonts:
        try:
            return ImageFont.truetype(fb_font, font_size)
        except Exception:
            continue

    return ImageFont.load_default()


def handle_error(error: Exception, include_traceback: bool = False) -> tuple:
    """
    Hata yönetimi - production'da traceback gizlenir.
    """
    import traceback

    is_production = os.environ.get('FLASK_ENV') == 'production'

    if is_production and not include_traceback:
        # Production'da genel hata mesajı
        return jsonify({
            "error": "Bir hata oluştu. Lütfen daha sonra tekrar deneyin.",
            "error_code": "INTERNAL_ERROR"
        }), 500
    else:
        # Development'ta detaylı hata
        return jsonify({
            "error": str(error),
            "traceback": traceback.format_exc()
        }), 500

# =============================================================================
# 3. SESSION YÖNETİMİ
# =============================================================================




def save_session(session_id: str, data: dict):
    """Session'ı veritabanına şifrelenmiş olarak kaydet."""
    
    # Hassas verileri şifrele
    encrypted_data = {
        'width': data['width'],
        'height': data['height'],
        'api_key': simple_encrypt(data['api_key']),
        'oauth_token': simple_encrypt(data['oauth_token']),
        'encrypted': True
    }
    
    try:
        session_entry = SessionData.query.get(session_id)
        if not session_entry:
            session_entry = SessionData(id=session_id)
            
        session_entry.set_data(encrypted_data)
        db.session.add(session_entry)
        db.session.commit()
    except Exception as e:
        print(f"DB Save Error: {e}")
        db.session.rollback()


def get_session(session_id: str) -> dict | None:
    """Session'ı veritabanından şifre çözerek al."""
    try:
        session_entry = SessionData.query.get(session_id)
        if not session_entry:
            return None
            
        data = session_entry.get_data()
        
        # Şifrelenmiş mi kontrol et
        if data.get('encrypted'):
            return {
                'width': data['width'],
                'height': data['height'],
                'api_key': simple_decrypt(data['api_key']),
                'oauth_token': simple_decrypt(data['oauth_token'])
            }
        else:
            return data
    except Exception as e:
        print(f"DB Get Error: {e}")
        return None

# =============================================================================
# 4. ROTALAR
# =============================================================================


@app.route('/')
def home():
    """Ana sayfa."""
    return render_template('index.html')


@app.route('/oauth/init', methods=['POST'])
def oauth_init():
    """OAuth akışını başlat."""
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
    """OAuth callback - STATE parametresi ile."""
    received_state = request.args.get('state')

    # State doğrulaması - popup ve ana pencere farklı session kullanabilir
    # Bu yüzden sadece state'in varlığını kontrol ediyoruz
    if not received_state:
        return """<script>
            window.opener.postMessage({type:'oauth_error', message:'State parametresi eksik'},'*');
            window.close();
        </script>""", 403

    try:
        client_config = get_client_config()
        if not client_config:
            return "OAuth credentials bulunamadı", 500
        
        flow = Flow.from_client_config(client_config, scopes=SCOPES)
        flow.redirect_uri = url_for('oauth_callback', _external=True)
        # State'i flow'a manuel olarak set et
        flow.fetch_token(
            authorization_response=request.url,
            state=received_state
        )

        return f"""<script>
            window.opener.postMessage({{type:'oauth_success',token:{json.dumps(flow.credentials.to_json())}}},'*');
            window.close();
        </script>"""
    except Exception as e:
        import traceback
        error_msg = str(e).replace("'", "\\'")
        print(f"OAuth Error: {e}")
        print(traceback.format_exc())
        return f"""<script>
            window.opener.postMessage({{type:'oauth_error', message:'{error_msg}'}},'*');
            window.close();
        </script>""", 500


@app.route('/create-session', methods=['POST'])
def create_session():
    """Yeni session oluştur."""
    data = request.get_json()

    # Validasyon
    required_fields = ['width', 'height', 'api_key', 'oauth_token']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'{field} gerekli'}), 400

    sid = data.get('custom_id') or str(uuid.uuid4())

    # ID formatı kontrolü
    if not re.match(r'^[a-zA-Z0-9\-]+$', sid):
        return jsonify({'success': False, 'error': 'ID sadece harf, rakam ve tire içerebilir'}), 400

    save_session(sid, {
        'width': int(data['width']),
        'height': int(data['height']),
        'api_key': data['api_key'],
        'oauth_token': data['oauth_token']
    })

    return jsonify({
        'success': True,
        'master_link': f"{request.host_url}generate/{sid}"
    })

# =============================================================================
# 5. WALLPAPER ÜRETİM
# =============================================================================


@app.route('/generate/<session_id>')
def generate_wallpaper(session_id: str):
    """AI destekli wallpaper üret."""
    data = get_session(session_id)
    if not data:
        return jsonify({"error": "Link geçersiz veya süresi dolmuş"}), 404

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
            maxResults=20,
            singleEvents=True,
            orderBy='startTime'
        ).execute().get('items', [])

        # Etkinlik detaylarını çıkar (ortak fonksiyon)
        events_details = [get_event_details(e, now) for e in events]

        # 24 SAAT veya daha az kaldıysa → sıradaki etkinliğe öncelik
        next_event = events_details[0] if events_details else None
        use_next_event = False

        if next_event and (next_event['total_hours_until'] <= 24):
            use_next_event = True
            selected_event_info = f"ACIL ETKİNLİK (24 saat veya daha az kaldı!):\n{next_event['full_info']}\nKalan süre: {next_event['total_hours_until']} saat"
        else:
            events_summary = "\n".join([
                f"- {e['full_info']} (Kalan: {e['total_hours_until']} saat / {e['days_until']} gün)"
                for e in events_details[:10]
            ]) or "Önümüzdeki 30 gün için planlanmış etkinlik yok."
            selected_event_info = events_summary

        # B. Gemini Pro ile Etkinlik Analizi (retry ile)
        client = genai.Client(api_key=data['api_key'])
        analyze_prompt = build_gemini_prompt(selected_event_info, use_next_event)

        # Retry mekanizması - rate limit için
        max_retries = 3
        retry_delay = 2  # başlangıç gecikmesi (saniye)
        
        for attempt in range(max_retries):
            try:
                analysis_resp = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=analyze_prompt
                )
                break  # Başarılı olursa döngüden çık
            except Exception as e:
                error_msg = str(e)
                if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                # Başka hata veya son deneme - hatayı fırlat
                raise

        # JSON parse
        response_text = analysis_resp.text.strip()
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            analysis = json.loads(response_text)

        sticker_concept = analysis.get('sticker_concept', 'a simple calendar icon')
        friendly_message = analysis.get('message', analysis.get('friendly_message', 'Etkinliğini unutma!'))
        google_font = analysis.get('google_font', 'Poppins')

        # C. Imagen ile Sticker Tarzı Görsel Üretimi (ortak prompt)
        imagen_prompt = build_imagen_prompt(sticker_concept)

        img_resp = client.models.generate_image(
            model="imagen-4.0-generate-001",
            prompt=imagen_prompt,
            config=types.GenerateImageConfig(
                aspect_ratio="1:1",
                number_of_images=1
            )
        )

        # D. Görsel İşleme ve Metin Giydirme
        
        # 1. Sticker'ı yükle (1:1 geliyor)
        sticker_img = Image.open(io.BytesIO(img_resp.generated_images[0].image.image_bytes)).convert('RGBA')
        
        # 2. Siyah Canvas oluştur (Telefon boyutunda)
        canvas = Image.new('RGBA', (data['width'], data['height']), (0, 0, 0, 255))
        
        # 3. Sticker'ı boyutlandır ve yerleştir
        # Sticker genişliği ekranın %85'i olsun
        sticker_target_width = int(data['width'] * 0.85)
        sticker_scale_ratio = sticker_target_width / sticker_img.width
        sticker_target_height = int(sticker_img.height * sticker_scale_ratio)
        
        sticker_img = sticker_img.resize((sticker_target_width, sticker_target_height), Image.LANCZOS)
        
        # Konumlandırma: Yatayda ORTALA, Dikeyde %60 (Alt-Orta)
        sticker_x = (data['width'] - sticker_target_width) // 2
        # Center of sticker at 60% of screen height
        center_y = int(data['height'] * 0.60)
        sticker_y = center_y - (sticker_target_height // 2)
        
        # Sticker'ı yapıştır (Alpha channel ile)
        canvas.paste(sticker_img, (sticker_x, sticker_y), sticker_img)
        
        img = canvas # Artık ana resmimiz bu canvas

        # Font yükleme (cache mekanizması ile)
        font_size = int(data['width'] * FONT_SIZE_RATIO)
        font = get_cached_font(google_font, font_size)

        # Margin hesapla
        margin = int(data['width'] * MARGIN_RATIO)
        max_text_width = data['width'] - (2 * margin)

        # Metin wrap
        avg_char_width = font_size * 0.55
        chars_per_line = int(max_text_width / avg_char_width)
        wrapped_text = textwrap.fill(friendly_message, width=max(chars_per_line, 20))

        # Metni görselin alt kısmına yerleştir (%82 seviyesine)
        text_y = int(data['height'] * 0.82)
        text_x = data['width'] // 2

        draw = ImageDraw.Draw(img)
        draw.multiline_text(
            (text_x, text_y),
            wrapped_text,
            fill=(255, 255, 255, 255), # BEYAZ METİN
            font=font,
            anchor="mm",
            align="center"
        )

        # RGB'ye dönüştür
        img = img.convert('RGB')

        # E. Sonucu Döndür
        buf = io.BytesIO()
        img.save(buf, format='PNG', quality=95)
        buf.seek(0)

        resp = make_response(send_file(buf, mimetype='image/png'))
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return resp

    except json.JSONDecodeError as e:
        return handle_error(Exception(f"OAuth token geçersiz: {e}"))
    except Exception as e:
        return handle_error(e)

# =============================================================================
# 6. DEBUG ENDPOINT (Sadece Development)
# =============================================================================


@app.route('/debug/<session_id>')
def debug_wallpaper(session_id: str):
    """
    AI'ya giden ve gelen tüm verileri göster - görsel üretmeden.
    SADECE development ortamında çalışır.
    """
    # Production'da devre dışı
    if os.environ.get('FLASK_ENV') == 'production':
        return jsonify({"error": "Debug endpoint production'da kullanılamaz"}), 403

    data = get_session(session_id)
    if not data:
        return jsonify({"error": "Link geçersiz"}), 404

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
        # Takvim Verisi Çekme
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
        raw_events = [{
            "summary": e.get('summary', 'Başlıksız'),
            "location": e.get('location', ''),
            "description": e.get('description', '')[:200] if e.get('description') else '',
            "start": e.get('start', {}),
            "end": e.get('end', {})
        } for e in events]

        debug_info["steps"].append({
            "step": 1,
            "name": "Google Calendar API",
            "input": "30 günlük etkinlik isteği (max 20)",
            "output": raw_events,
            "event_count": len(events)
        })

        # Etkinlik detayları (ortak fonksiyon)
        events_details = [get_event_details(e, now) for e in events]

        next_event = events_details[0] if events_details else None
        use_next_event = next_event and (next_event['total_hours_until'] <= 24)

        if use_next_event:
            selected_event_info = f"ACIL ETKİNLİK (24 saat veya daha az kaldı!):\n{next_event['full_info']}\nKalan süre: {next_event['total_hours_until']} saat"
        else:
            events_summary = "\n".join([
                f"- {e['full_info']} (Kalan: {e['total_hours_until']} saat / {e['days_until']} gün)"
                for e in events_details[:10]
            ]) or "Önümüzdeki 30 gün için planlanmış etkinlik yok."
            selected_event_info = events_summary

        debug_info["steps"].append({
            "step": 2,
            "name": "Etkinlik İşleme",
            "use_next_event": use_next_event,
            "next_event_details": next_event,
            "all_events_details": events_details[:5],
            "selected_event_info": selected_event_info
        })

        # Gemini Prompt (AYNI prompt fonksiyonu)
        analyze_prompt = build_gemini_prompt(selected_event_info, use_next_event)

        debug_info["steps"].append({
            "step": 3,
            "name": "Gemini Prompt (INPUT)",
            "model": "gemini-2.0-flash",
            "prompt": analyze_prompt
        })

        # Gemini Çağrısı
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

        sticker_concept = analysis.get('sticker_concept', 'a simple calendar icon')
        friendly_message = analysis.get('message', analysis.get('friendly_message', 'Etkinliğini unutma!'))

        debug_info["steps"].append({
            "step": 5,
            "name": "Gemini Parsed Data",
            "parsed_json": analysis,
            "extracted": {
                "sticker_concept": sticker_concept,
                "friendly_message": friendly_message
            }
        })

        # Imagen Prompt (AYNI prompt fonksiyonu)
        imagen_prompt = build_imagen_prompt(sticker_concept)

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
