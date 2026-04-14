# 🚀 Business Scraper (Maroc & Europe)

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Framework-Flask-lightgrey.svg)](https://flask.palletsprojects.com/)
[![Playwright](https://img.shields.io/badge/Scraping-Playwright-green.svg)](https://playwright.dev/)

Une application web puissante et intuitive conçue pour l'extraction de données B2B (Prospects) depuis plusieurs sources majeures, spécialisée pour le marché Marocain et Européen.

## ✨ Fonctionnalités

- **Multisources** : Extraction de données depuis :
  - **Google Maps** (Extraction profonde : Emails, Sites Web, Réseaux Sociaux).
  - **Telecontact** (Annuaire professionnel Maroc).
  - **Yellow Pages** (Pages Jaunes).
- **Interface Web Moderne** : Suivi en temps réel de l'avancement via **Socket.IO**.
- **Nettoyage Intelligent** : Suppression automatique des doublons, validation des emails et formatage des numéros de téléphone.
- **Exports Multiples** : Téléchargez vos leads instantanément au format **Excel (.xlsx)** ou **CSV**.
- **Performance** : Utilisation de Playwright pour une extraction robuste et asynchrone.

## 🛠️ Technologies Utilisées

- **Backend** : Python, Flask, Flask-SocketIO
- **Scraping** : Playwright, BeautifulSoup4, Requests
- **Data** : Pandas, Openpyxl
- **Frontend** : HTML5, CSS3, JavaScript (Vanilla)

## 📦 Installation

1. **Cloner le dépôt** :
   ```bash
   git clone https://github.com/ayoubrks/projet_scap.git
   cd projet_scap
   ```

2. **Créer un environnement virtuel** :
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```

3. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

4. **Installer les navigateurs Playwright** :
   ```bash
   playwright install chromium
   ```

## 🚀 Utilisation

1. **Lancer l'application** :
   ```bash
   python main.py
   ```
2. **Accéder à l'interface** :
   Ouvrez votre navigateur sur `http://127.0.0.1:5000`.

3. **Lancer un scan** :
   - Entrez la **ville** et la **catégorie** (ex: "Web Agency" à "Casablanca").
   - Sélectionnez les sources souhaitées.
   - Cliquez sur "Démarrer l'extraction" et suivez le progrès en direct.

## 📂 Structure du Projet

```text
projet_scap/
├── app.py              # Application Flask (Serveur & API)
├── main.py             # Point d'entrée principal
├── scraper/            # Modules d'extraction
│   ├── google_maps.py  # Logique Google Maps
│   ├── telecontact.py  # Logique Telecontact
│   ├── data_cleaner.py # Nettoyage des données
│   └── exporter.py     # Gestion des exports Excel/CSV
├── static/             # Fichiers statiques (CSS, JS)
├── templates/          # Vues HTML
└── output/             # Dossier des fichiers générés (ignoré par Git)
```

## ⚠️ Avertissement

Cet outil est destiné à un usage éducatif et professionnel légitime. Veuillez respecter les conditions d'utilisation des sites scrapés et les réglementations sur la protection des données (RGPD/CNDP).

---
Développé avec ❤️ pour le marché Marocain.