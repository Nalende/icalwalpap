from iCalendarPaper import db
from datetime import datetime
import json

class SessionData(db.Model):
    """
    Kullanıcı oturum verilerini (API key, OAuth token vb.) saklamak için veritabanı modeli.
    Render.com gibi geçici filesystem kullanan platformlarda (sleeping dynos) kalıcılık sağlar.
    """
    id = db.Column(db.String(100), primary_key=True)
    # JSON veriyi text olarak saklayacağız (SQLite ve Postgres uyumlu)
    data = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_data(self, data_dict):
        self.data = json.dumps(data_dict, ensure_ascii=False)

    def get_data(self):
        try:
            return json.loads(self.data)
        except:
            return {}
