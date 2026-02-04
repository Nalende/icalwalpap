from flask import Flask

app = Flask(__name__)
app.secret_key = 'NeMutluTurkumDiyeneYasasinCumhuriyet'

# 'iCalendarPaper.views' yerine sadece '.views' kullanarak yolu kýsaltýyoruz
from . import views