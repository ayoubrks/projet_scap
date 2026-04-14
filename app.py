import os
import time
import json
import logging
import threading
import asyncio
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from flask_socketio import SocketIO, emit

from scraper.google_maps import scrape_google_maps
from scraper.telecontact import TelecontactScraper, YellowPagesScraper
from scraper.data_cleaner import DataCleaner
from scraper.exporter import DataExporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'morocco-scraper-secret-key-2026'
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

# Create output folder if it doesn't exist
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Initialize SocketIO for real-time progress updates
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state to keep track of scraping jobs
# In a real production app, use Redis or a database
jobs = {}

def get_progress_callback(job_id):
    """Factory function to create a progress callback for a specific job."""
    def progress_callback(update_type, data):
        if update_type == "status":
            socketio.emit('status_update', {'job_id': job_id, 'message': data})
            logger.info(f"Job {job_id}: {data}")
        elif update_type == "progress":
            socketio.emit('progress_update', {'job_id': job_id, 'progress': data})
        elif update_type == "error":
            socketio.emit('error_update', {'job_id': job_id, 'message': data})
            logger.error(f"Job {job_id} Error: {data}")
    return progress_callback

def run_scraping_job(job_id, settings):
    """Background task that runs the actual scraping process."""
    try:
        jobs[job_id]['status'] = 'running'
        city = settings.get('city', 'Casablanca')
        category = settings.get('category', '')
        country = settings.get('country', 'Morocco')
        max_results = min(int(settings.get('max_results', 50)), 500)
        sources = settings.get('sources', ['google'])
        deep_scrape = settings.get('deep_scrape', True)
        
        callback = get_progress_callback(job_id)
        
        # We need a new event loop for this thread if using async Playwright
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        all_results = []
        
        # 1. Scrape Google Maps
        if 'google' in sources:
            callback("status", f"Lancement de l'extraction Google Maps pour {city}...")
            google_results = loop.run_until_complete(
                scrape_google_maps(city, category, max_results, callback, deep_scrape=deep_scrape, country=country)
            )
            all_results.extend(google_results)
            
        # 2. Scrape Telecontact
        if 'telecontact' in sources:
            callback("status", f"Starting Telecontact extraction for {city}...")
            tc_scraper = TelecontactScraper()
            tc_results = loop.run_until_complete(
                tc_scraper.scrape(city, category, max_results // 2, callback)
            )
            all_results.extend(tc_results)
            
        # 3. Scrape Yellow Pages
        if 'yellowpages' in sources:
            callback("status", f"Starting Yellow Pages extraction for {city}...")
            yp_scraper = YellowPagesScraper()
            yp_results = loop.run_until_complete(
                yp_scraper.scrape(city, category, max_results // 2, callback)
            )
            all_results.extend(yp_results)
            
        loop.close()
        
        if not all_results:
            callback("error", "No results found across selected sources.")
            jobs[job_id]['status'] = 'failed'
            return

        # 4. Clean Data
        callback("status", f"Collected {len(all_results)} raw records. Starting data cleaning...")
        cleaner = DataCleaner()
        cleaned_data = cleaner.clean(all_results, callback, country=country)
        stats = cleaner.get_stats()
        
        # 5. Export Data
        callback("status", "Exporting data to Excel and CSV...")
        exporter = DataExporter(output_dir=app.config['OUTPUT_FOLDER'])
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = f"{city}_{category}_{timestamp}".replace(' ', '_').lower()
        if not category:
            base_name = f"{city}_all_{timestamp}".replace(' ', '_').lower()
            
        export_files = exporter.export_all(cleaned_data, city)
        
        # Store results info
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['results'] = {
            'total_found': stats['total_input'],
            'total_extracted': stats['total_output'],
            'duplicates_removed': stats['duplicates_removed'],
            'invalid_emails': stats['invalid_emails_removed'],
            'files': {
                'csv': os.path.basename(export_files['csv']),
                'excel': os.path.basename(export_files['xlsx'])
            }
        }
        
        callback("status", "Job completed successfully!")
        socketio.emit('job_complete', {'job_id': job_id, 'results': jobs[job_id]['results']})
        
    except Exception as e:
        logger.exception(f"Job {job_id} failed with an unhandled exception")
        jobs[job_id]['status'] = 'failed'
        error_cb = get_progress_callback(job_id)
        error_cb("error", f"An unexpected error occurred: {str(e)}")
        socketio.emit('job_failed', {'job_id': job_id, 'error': str(e)})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    settings = request.json
    
    if not settings.get('city'):
        return jsonify({'error': 'City is required'}), 400
        
    job_id = f"job_{int(time.time())}"
    jobs[job_id] = {
        'status': 'starting',
        'settings': settings,
        'started_at': datetime.now().isoformat()
    }
    
    # Start background thread for scraping
    thread = threading.Thread(target=run_scraping_job, args=(job_id, settings))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'job_id': job_id,
        'message': 'Scraping job started successfully'
    })

@app.route('/api/status/<job_id>', methods=['GET'])
def get_status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(jobs[job_id])

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    logger.info("Starting Morocco Business Scraper Web App...")
    # Run the Flask app with SocketIO
    socketio.run(app, debug=True, host='127.0.0.1', port=5000)
