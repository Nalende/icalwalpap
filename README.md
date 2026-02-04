# iCalendarPaper - AI Wallpaper Generator

Yapay zeka defterinizi ve Google Takviminizi kullanarak kişiselleştirilmiş, estetik duvar kağıtları oluşturur.

## Özellikler

- **Google Takvim Entegrasyonu**: Yaklaşan etkinlikleri otomatik çeker.
- **Akıllı Önceliklendirme**: Doğum günleri, yıldönümleri ve acil randevuları ayırt eder.
- **Mood Analizi**: Etkinliğin ruhuna göre (Sarkastik, Neşeli, Ciddi vb.) mod belirler.
- **AI Tasarım**: Google Imagen ve Gemini kullanarak minimalist, sticker tarzı görseller ve uyumlu mesajlar üretir.
- **Okunabilir Tasarım**: Yumuşak gölgeli, Türkçe karakter destekli modern tipografi.

## Kurulum

1. Gereksinimleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

2. Google Cloud Console'dan `credentials.json` (OAuth Client ID) dosyanızı alın ve ana dizine koyun.
   - Gerekli API'ler: Google Calendar API, Google Gemini API.

3. Uygulamayı başlatın:
   ```bash
   python runserver.py
   ```

4. Tarayıcıda `http://localhost:5000` adresine gidin.

## Dosya Yapısı

- `iCalendarPaper/views.py`: Ana mantık, AI promptları ve görsel işleme.
- `requirements.txt`: Gerekli kütüphaneler.
- `sessions.json`: Kullanıcı oturum verileri (temiz başlar).

## Notlar

- `credentials.json` dosyanızı **ASLA** paylaşmayın veya GitHub'a yüklemeyin.
- `.gitignore` dosyası gereksiz dosyaların yüklenmesini engeller.
