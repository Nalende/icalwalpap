# -*- coding: utf-8 -*-
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os

app = Flask(__name__)
# Secret Key (Environment variable or fallback)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Database Configuration
# Render.com will provide DATABASE_URL. Local fallback to sqlite.
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)  # SQLAlchemy fix for Render

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Init extensions
db = SQLAlchemy(app)
CORS(app)

from . import views, models

# DB Creation (Local development only)
with app.app_context():
    db.create_all()
