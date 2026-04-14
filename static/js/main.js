document.addEventListener('DOMContentLoaded', () => {
    // Connect to SocketIO 
    const socket = io();
    
    // UI Elements
    const form = document.getElementById('scrapeForm');
    const startBtn = document.getElementById('startBtn');
    const countryInput = document.getElementById('country');
    const cityInput = document.getElementById('city');
    const categoryInput = document.getElementById('category');
    
    // State Panels
    const welcomeState = document.getElementById('welcomeState');
    const activeState = document.getElementById('activeState');
    const resultsPanel = document.getElementById('resultsPanel');
    
    // Progress UI
    const logContainer = document.getElementById('logContainer');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const progressPercent = document.getElementById('progressPercent');
    const jobStatusTitle = document.getElementById('jobStatusTitle');
    const loader = document.getElementById('loader');
    
    // Status Bar
    const globalStatusText = document.getElementById('globalStatusText');
    const statusPulse = document.getElementById('statusPulse');
    const badge = document.getElementById('currentSelectionBadge');
    
    // Globals
    let currentJobId = null;
    let isScraping = false;

    // Handle Country Input Change
    countryInput.addEventListener('input', () => {
        const country = countryInput.value.trim().toLowerCase();
        
        // Toggle Morocco-specific sources
        const moroccoSources = ['src_telecontact', 'src_yellowpages'];
        const isMorocco = country.includes('maroc') || country.includes('morocco');
        
        moroccoSources.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.disabled = !isMorocco;
                if (!isMorocco) el.checked = false;
                else if (id === 'src_telecontact') el.checked = true;
            }
        });

        // Update UI labels if needed
        const welcomeTitle = document.querySelector('#welcomeState h3');
        if (welcomeTitle) {
            welcomeTitle.innerText = isMorocco ? 
                'Prêt à collecter des entreprises marocaines' : 
                `Prêt à collecter des entreprises (${countryInput.value})`;
        }
    });

    // UI Helpers
    function showNotification(msg, type = 'info') {
        const area = document.getElementById('notificationArea');
        const notif = document.createElement('div');
        notif.className = `notification ${type}`;
        
        const icon = type === 'error' ? 'fa-circle-xmark' : 
                     type === 'success' ? 'fa-circle-check' : 'fa-circle-info';
                     
        notif.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${msg}</span>`;
        area.appendChild(notif);
        
        setTimeout(() => {
            notif.style.animation = 'slideOut 0.3s forwards';
            setTimeout(() => notif.remove(), 300);
        }, 5000);
    }

    function addLog(msg, type = 'log-entry') {
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        
        const time = new Date().toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: "numeric", 
            minute: "numeric",
            second: "numeric"
        });
        
        entry.innerHTML = `<span class="log-time">[${time}]</span> ${msg}`;
        logContainer.appendChild(entry);
        
        // Auto scroll to bottom
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // Socket Event Listeners
    socket.on('connect', () => {
        console.log('Connected to backend');
    });

    socket.on('status_update', (data) => {
        if (data.job_id === currentJobId) {
            jobStatusTitle.innerText = data.message;
            
            let logType = 'info';
            if(data.message.includes('Cleaning')) logType = 'warning';
            if(data.message.includes('Exporting') || data.message.includes('success')) logType = 'success';
            
            addLog(data.message, logType);
        }
    });

    socket.on('progress_update', (data) => {
        if (data.job_id === currentJobId && data.progress) {
            const p = data.progress;
            
            if (p.total > 0 && p.current >= 0) {
                const percent = Math.min(Math.round((p.current / p.total) * 100), 100);
                progressFill.style.width = `${percent}%`;
                progressPercent.innerText = `${percent}%`;
                progressText.innerText = `${p.current} / ${p.total} extracted`;
            }
            
            if (p.message) {
                // Throttle log writes for rapid progress updates
                if (p.current % 5 === 0 || p.current === p.total) {
                    addLog(p.message, 'log-entry');
                }
            }
        }
    });

    socket.on('job_complete', (data) => {
        if (data.job_id === currentJobId) {
            isScraping = false;
            updateGlobalStatus('Completed successfully', 'idle');
            
            loader.classList.add('hidden');
            startBtn.disabled = false;
            startBtn.innerHTML = '<i class="fa-solid fa-play"></i> Start New Extraction';
            
            progressFill.style.width = '100%';
            progressPercent.innerText = '100%';
            
            showNotification('Data extraction completed successfully!', 'success');
            
            // Show Results
            const res = data.results;
            
            // Animate numbers
            animateValue("statFound", 0, res.total_found, 1500);
            animateValue("statExtracted", 0, res.total_extracted, 2000);
            animateValue("statDuplicates", 0, res.duplicates_removed, 1500);
            
            // Setup download links
            document.getElementById('btnDownloadExcel').href = `/download/${res.files.excel}`;
            document.getElementById('btnDownloadCsv').href = `/download/${res.files.csv}`;
            
            // Slide Down Results
            setTimeout(() => {
                resultsPanel.classList.remove('hidden');
                resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }, 800);
        }
    });

    socket.on('job_failed', (data) => {
        if (data.job_id === currentJobId) {
            isScraping = false;
            updateGlobalStatus('Extraction Failed', 'error');
            
            loader.classList.add('hidden');
            startBtn.disabled = false;
            startBtn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> Retry Extraction';
            
            addLog(`ERROR: ${data.error}`, 'error');
            jobStatusTitle.innerText = "Processing Error";
            jobStatusTitle.style.color = 'var(--error)';
            
            showNotification(`Error: ${data.error}`, 'error');
        }
    });

    function updateGlobalStatus(text, stateClass) {
        globalStatusText.innerText = text;
        statusPulse.className = `pulse ${stateClass}`;
    }

    // Number animation helper
    function animateValue(id, start, end, duration) {
        const obj = document.getElementById(id);
        if(!obj) return;
        
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            obj.innerHTML = Math.floor(progress * (end - start) + start);
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }

    // Dynamic UI Updates on Form change
    form.addEventListener('change', () => {
        if (!isScraping && cityInput.value) {
            let label = cityInput.value;
            if (categoryInput.value.trim()) {
                label += ` • ${categoryInput.value.trim()}`;
            }
            badge.innerText = label;
            badge.classList.remove('hidden');
        }
    });

    // Form Submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (isScraping) return;
        
        // Gather selected sources
        const sources = [];
        if(document.getElementById('src_google').checked) sources.push('google');
        if(document.getElementById('src_telecontact').checked) sources.push('telecontact');
        if(document.getElementById('src_yellowpages').checked) sources.push('yellowpages');
        
        if (sources.length === 0) {
            showNotification('Please select at least one data source.', 'error');
            return;
        }

        const payload = {
            city: cityInput.value,
            country: countryInput.value,
            category: categoryInput.value.trim(),
            max_results: parseInt(document.getElementById('max_results').value, 10),
            sources: sources,
            deep_scrape: document.getElementById('deep_scrape').checked
        };
        
        // UI transitions
        isScraping = true;
        welcomeState.classList.add('hidden');
        resultsPanel.classList.add('hidden');
        activeState.classList.remove('hidden');
        
        startBtn.disabled = true;
        startBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Extraction...';
        
        updateGlobalStatus('Extraction en cours...', 'active');
        jobStatusTitle.innerText = "Initialisation du moteur...";
        jobStatusTitle.style.color = 'white';
        loader.classList.remove('hidden');
        
        // Reset progress UI
        logContainer.innerHTML = '';
        progressFill.style.width = '0%';
        progressPercent.innerText = '0%';
        progressText.innerText = 'Démarrage...';
        
        addLog(`Lancement de l'extraction pour ${payload.city} (${payload.country})...`, 'info');
        if(payload.deep_scrape) {
            addLog(`Note: L'enrichissement complet est activé (Emails/Sites web). Cela peut prendre quelques minutes.`, 'log-entry');
        } else {
            addLog(`Note: Mode rapide activé (Extraction des noms et téléphones uniquement).`, 'success');
        }
        
        if(payload.category) {
            addLog(`Target category: ${payload.category}`, 'info');
        }

        try {
            const res = await fetch('/api/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            const data = await res.json();
            
            if (res.ok) {
                currentJobId = data.job_id;
                addLog(`Job ID ${currentJobId} created and dispatched to workers.`, 'success');
            } else {
                throw new Error(data.error || 'Failed to start job');
            }
            
        } catch (err) {
            isScraping = false;
            updateGlobalStatus('Failed to start', 'error');
            startBtn.disabled = false;
            startBtn.innerHTML = '<i class="fa-solid fa-play"></i> Start Scraping';
            
            addLog(`Initialization Error: ${err.message}`, 'error');
            showNotification(err.message, 'error');
            loader.classList.add('hidden');
        }
    });
});
