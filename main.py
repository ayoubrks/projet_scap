import sys
import logging
from app import app, socketio

# Moroccan Scraper Main Entry Point
if __name__ == '__main__':
    print("🚀 Démarrage du Business Scraper (Maroc & Europe)...")
    print("👉 Accédez à: http://127.0.0.1:5000")
    
    # Run the same logic as app.py
    socketio.run(app, debug=True, host='127.0.0.1', port=5000)
