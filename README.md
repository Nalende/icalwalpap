# iCalendarPaper - AI Wallpaper Generator

Yapay zeka defterinizi ve Google Takviminizi kullanarak kişiselleştirilmiş, estetik duvar kağıtları oluşturur.

## Özellikler

- **Google Takvim Entegrasyonu**: Yaklaşan etkinlikleri otomatik çeker.
- **Akıllı Önceliklendirme**: Doğum günleri, yıldönümleri ve acil randevuları ayırt eder.
- **Mood Analizi**: Etkinliğin ruhuna göre (Sarkastik, Neşeli, Ciddi vb.) mod belirler.
- **AI Tasarım**: Google Imagen ve Gemini kullanarak minimalist, sticker tarzı görseller ve uyumlu mesajlar üretir.
- **Okunabilir Tasarım**: Yumuşak gölgeli, Türkçe karakter destekli modern tipografi.

## Kurulum (local)

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

önizleme ve deneyim adresi:

https://icalwalpap.onrender.com

Not: Domain , api vs.. her şey tamamen ücretsiz olduğundan bazı kısıtlılıklar mevcut olabilir. Örneğin yanıt süresi geç olduğu için kestirmelere eklenen duvar kağıdı yap otomasyonu bazen sorun çıkarabiliyor. bunu aşmak için ilk olarak urlden başlığı al deyip ardından bekle komutu uygulayıp 10-15 sn bekledikten sonra url içeriğini al ve url içeriğini duvar kağıdı olarak ayarla şeklinde uyguladım. teknik olarak yapmak istediğim proje çalışıyor. sadece bunun için ödeme yapmak istemediğimden bu şekilde bir süreç yaşanmakta. ilhamı https://thelifecalendar.com/ 'dan aldım. maksadım neler yapılabileceğini ve bunu nasıl geliştrebileceğimizi görmekti. tüm kodlar yapay zekaya yazdırıldı. ben sadece yönlendirmelerde bulundum. ilgilenen arkadaşlar olursa credits vererek tüm fikri ve kodları gönül rahatlığıyla alabilir, kopyalayabilir, çoğaltıp geiştirebilir. beni de hatırlayın yeter :) 
Teşekkürler!
