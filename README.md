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

## Açıklama - Önizleme ve deneyim adresi:


Çalışma süreci şu şekilde özetleyebiliriz. 

🌐 Kullanıcı Tarafı (Web Arayüzü)

-Kullanıcı siteye girer: https://icalwalpap.onrender.com

-iPhone modelini seçer: Ekran çözünürlüğü belirlenir (örn: 1179x2556)

-Gemini API Key'ini girer: Kullanıcı kendi API anahtarını kullanır

-Google Takvim'e bağlanır:

-"TAKVİME BAĞLAN" butonuna tıklar

-Google OAuth popup açılır

-Kullanıcı izin verir

-OAuth token alınır ve saklanır

-Master Link oluşturur:

-Tüm bilgiler (çözünürlük, API key, OAuth token) sunucuya kaydedilir

-Benzersiz bir session ID oluşturulur

-Master Link kullanıcıya verilir: https://icalwalpap.onrender.com/generate/[session-id]

📱 iOS Shortcuts Tarafı (Otomatik Çalışma)

*Shortcuts linki çağırır: Her gün belirlenen saatte /generate/[session-id] adresine istek atar

*Sunucu takvimi çeker:

*Google Calendar API ile 30 günlük etkinlikler alınır

*Başlık, konum, açıklama, tarih bilgileri çıkarılır

*24 saat kuralı uygulanır:

*Eğer bir etkinlik 24 saat içindeyse → O etkinliğe odaklanılır

*Değilse → Gemini en önemli etkinliği seçer

*Gemini analiz yapar:

*Etkinlik türünü belirler (doğum günü, toplantı, randevu vb.)

*Mood seçer (dark_humor, sarcastic, cheerful vb.)

*Türkçe mesaj yazar (max 12 kelime)

*Sticker konsepti oluşturur (İngilizce)

*Uygun Google Font önerir

*Imagen görsel üretir:

*Sticker tarzı minimalist görsel oluşturulur

*Beyaz arka plan, ince çizgili tasarım

*9:16 dikey format (telefon wallpaper)

*PIL ile metin eklenir:

*Google Font indirilir

*Türkçe mesaj görselin alt kısmına yazılır

*Gölge efekti eklenir

*JPEG olarak döndürülür:

*iOS Shortcuts görseli alır

*Wallpaper olarak ayarlar



https://icalwalpap.onrender.com üzerinden deneyimleyebilirsiniz.

Not: Domain , api vs.. her şey tamamen ücretsiz olduğundan bazı kısıtlılıklar mevcut olabilir. Örneğin yanıt süresi geç olduğu için kestirmelere eklenen duvar kağıdı yap otomasyonu bazen sorun çıkarabiliyor. bunu aşmak için ilk olarak urlden başlığı al deyip ardından bekle komutu uygulayıp 10-15 sn bekledikten sonra url içeriğini al ve url içeriğini duvar kağıdı olarak ayarla şeklinde uyguladım. teknik olarak yapmak istediğim proje çalışıyor. sadece bunun için ödeme yapmak istemediğimden bu şekilde bir süreç yaşanmakta. ilhamı https://thelifecalendar.com/ 'dan aldım. maksadım neler yapılabileceğini ve bunu nasıl geliştrebileceğimizi görmekti. tüm kodlar yapay zekaya yazdırıldı. ben sadece yönlendirmelerde bulundum. ilgilenen arkadaşlar olursa credits vererek tüm fikri ve kodları gönül rahatlığıyla alabilir, kopyalayabilir, çoğaltıp geiştirebilir. beni de hatırlayın yeter :) 
Teşekkürler!
