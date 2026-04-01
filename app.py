from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "OK ONLINE 🚀"

@app.route('/dashboard')
def dashboard():
    return "PAINEL OK 📊"
