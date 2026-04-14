"""
Telecontact.ma Scraper Module
Scrapes business data from Telecontact (Moroccan Yellow Pages directory).
"""

import asyncio
import logging
import re
import random
from typing import List, Dict, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# Moroccan city mappings for directory searches
CITY_MAPPINGS = {
    'casablanca': 'casablanca',
    'rabat': 'rabat',
    'marrakech': 'marrakech',
    'fes': 'fes',
    'fès': 'fes',
    'tanger': 'tanger',
    'tangier': 'tanger',
    'agadir': 'agadir',
    'meknes': 'meknes',
    'meknès': 'meknes',
    'oujda': 'oujda',
    'kenitra': 'kenitra',
    'kénitra': 'kenitra',
    'tetouan': 'tetouan',
    'tétouan': 'tetouan',
    'safi': 'safi',
    'mohammedia': 'mohammedia',
    'el jadida': 'el-jadida',
    'beni mellal': 'beni-mellal',
    'nador': 'nador',
    'taza': 'taza',
    'settat': 'settat',
    'sale': 'sale',
    'salé': 'sale',
    'khouribga': 'khouribga',
    'temara': 'temara',
}

# Common business categories
CATEGORIES = {
    'restaurant': ['restaurant', 'restauration', 'café', 'fast food', 'pizzeria', 'snack'],
    'salon': ['coiffure', 'salon de beauté', 'esthétique', 'barbier', 'spa'],
    'hotel': ['hôtel', 'riad', 'hébergement', 'auberge', 'motel'],
    'shop': ['magasin', 'boutique', 'commerce', 'épicerie', 'supermarché'],
    'health': ['médecin', 'pharmacie', 'clinique', 'dentiste', 'cabinet médical'],
    'education': ['école', 'lycée', 'université', 'formation', 'crèche'],
    'auto': ['garage', 'auto', 'mécanique', 'pneu', 'lavage'],
    'construction': ['construction', 'immobilier', 'plomberie', 'électricité', 'peinture'],
    'technology': ['informatique', 'téléphone', 'réparation', 'électronique'],
    'services': ['avocat', 'notaire', 'comptable', 'assurance', 'banque'],
}


class TelecontactScraper:
    """Scrapes business information from Telecontact.ma (Moroccan Yellow Pages)."""

    BASE_URL = "https://www.telecontact.ma"
    SEARCH_URL = "https://www.telecontact.ma/search"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.results: List[Dict] = []

    def _normalize_city(self, city: str) -> str:
        """Normalize city name for URL construction."""
        city_lower = city.lower().strip()
        return CITY_MAPPINGS.get(city_lower, city_lower.replace(' ', '-'))

    async def scrape(self, city: str, category: str = "", max_results: int = 100,
                     progress_callback=None) -> List[Dict]:
        """
        Scrape business data from Telecontact.ma.

        Args:
            city: The Moroccan city to search in
            category: Optional category filter
            max_results: Maximum number of results
            progress_callback: Optional callback for progress updates

        Returns:
            List of business data dictionaries
        """
        self.results = []
        normalized_city = self._normalize_city(city)

        if progress_callback:
            progress_callback("status", f"🌐 Searching Telecontact.ma for businesses in {city}...")

        # Build search queries
        search_terms = []
        if category:
            search_terms.append(category)
        else:
            # Search multiple common categories
            for cat_name, terms in CATEGORIES.items():
                search_terms.extend(terms[:2])  # Take first 2 terms per category

        total_terms = len(search_terms)
        for idx, term in enumerate(search_terms):
            if len(self.results) >= max_results:
                break

            try:
                if progress_callback:
                    progress_callback("progress", {
                        "current": idx + 1,
                        "total": total_terms,
                        "message": f"🔍 Searching '{term}' in {city}..."
                    })

                page_results = await self._search_telecontact(term, normalized_city, city)
                self.results.extend(page_results)

                # Rate limiting
                await asyncio.sleep(random.uniform(1.0, 3.0))

            except Exception as e:
                logger.warning(f"Error searching '{term}' on Telecontact: {e}")
                continue

        if progress_callback:
            progress_callback("status", f"✅ Found {len(self.results)} businesses on Telecontact.ma")

        return self.results[:max_results]

    async def _search_telecontact(self, query: str, normalized_city: str,
                                   original_city: str) -> List[Dict]:
        """Search Telecontact.ma for a specific query."""
        results = []

        try:
            # Telecontact search URL format
            search_url = f"{self.SEARCH_URL}?q={quote_plus(query)}&ville={quote_plus(normalized_city)}"

            response = await asyncio.to_thread(
                self.session.get, search_url, timeout=15
            )

            if response.status_code != 200:
                logger.warning(f"Telecontact returned status {response.status_code}")
                return results

            soup = BeautifulSoup(response.text, 'lxml')

            # Find business listings
            listings = soup.select('.result-item, .company-item, .listing-item, article.result')

            if not listings:
                # Try alternative selectors
                listings = soup.select('[class*="result"], [class*="listing"], [class*="company"]')

            for listing in listings:
                try:
                    business = self._parse_listing(listing, original_city, query)
                    if business and business.get('name'):
                        results.append(business)
                except Exception as e:
                    logger.debug(f"Error parsing listing: {e}")
                    continue

            # Check for pagination
            page_num = 2
            while len(results) < 50:  # Limit per search term
                next_url = f"{search_url}&page={page_num}"
                try:
                    response = await asyncio.to_thread(
                        self.session.get, next_url, timeout=15
                    )
                    if response.status_code != 200:
                        break

                    soup = BeautifulSoup(response.text, 'lxml')
                    listings = soup.select('.result-item, .company-item, .listing-item, article.result')

                    if not listings:
                        listings = soup.select('[class*="result"], [class*="listing"], [class*="company"]')

                    if not listings:
                        break

                    for listing in listings:
                        try:
                            business = self._parse_listing(listing, original_city, query)
                            if business and business.get('name'):
                                results.append(business)
                        except Exception:
                            continue

                    page_num += 1
                    await asyncio.sleep(random.uniform(1.5, 3.0))

                except Exception:
                    break

        except Exception as e:
            logger.error(f"Error searching Telecontact: {e}")

        return results

    def _parse_listing(self, listing, city: str, category: str) -> Optional[Dict]:
        """Parse a single business listing from Telecontact."""
        business = {
            'name': '',
            'phone': '',
            'email': '',
            'website': '',
            'address': '',
            'city': city,
            'category': category,
            'latitude': '',
            'longitude': '',
            'source': 'Telecontact.ma'
        }

        # Extract business name
        name_el = listing.select_one('h2, h3, h4, .company-name, .result-title, [class*="name"], [class*="title"]')
        if name_el:
            business['name'] = name_el.get_text(strip=True)
        else:
            # Try getting from link
            link = listing.select_one('a[href*="company"], a[href*="entreprise"]')
            if link:
                business['name'] = link.get_text(strip=True)

        # Extract phone
        phone_el = listing.select_one('[class*="phone"], [class*="tel"], a[href^="tel:"]')
        if phone_el:
            if phone_el.get('href', '').startswith('tel:'):
                business['phone'] = phone_el['href'].replace('tel:', '').strip()
            else:
                business['phone'] = phone_el.get_text(strip=True)
        else:
            # Search in the full text for phone patterns
            full_text = listing.get_text()
            phone_match = re.search(r'(?:\+212|0)[\s.-]?[567]\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}', full_text)
            if phone_match:
                business['phone'] = phone_match.group(0)

        # Extract email
        email_el = listing.select_one('a[href^="mailto:"]')
        if email_el:
            business['email'] = email_el['href'].replace('mailto:', '').strip()
        else:
            full_text = listing.get_text()
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', full_text)
            if email_match:
                business['email'] = email_match.group(0)

        # Extract website
        website_el = listing.select_one('a[href*="http"]:not([href*="telecontact"]):not([href*="google"]):not([href*="facebook"])')
        if website_el:
            href = website_el.get('href', '')
            if href and 'telecontact' not in href:
                business['website'] = href

        # Extract address
        addr_el = listing.select_one('[class*="address"], [class*="adresse"], [class*="location"]')
        if addr_el:
            business['address'] = addr_el.get_text(strip=True)

        # Extract category if available
        cat_el = listing.select_one('[class*="category"], [class*="activite"], [class*="sector"]')
        if cat_el:
            business['category'] = cat_el.get_text(strip=True)

        return business if business['name'] else None


class YellowPagesScraper:
    """Scrapes business information from Moroccan Yellow Pages / Annuaire."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.results: List[Dict] = []

    async def scrape(self, city: str, category: str = "", max_results: int = 100,
                     progress_callback=None) -> List[Dict]:
        """
        Scrape business data from Yellow Pages Morocco (pages-jaunes.ma).

        Args:
            city: City name to search
            category: Optional category
            max_results: Max results
            progress_callback: Progress callback

        Returns:
            List of business dictionaries
        """
        self.results = []

        if progress_callback:
            progress_callback("status", f"📒 Searching Yellow Pages Morocco for businesses in {city}...")

        # Search multiple categories or specific one
        search_terms = [category] if category else list(CATEGORIES.keys())

        for idx, term in enumerate(search_terms):
            if len(self.results) >= max_results:
                break

            try:
                if progress_callback:
                    progress_callback("progress", {
                        "current": idx + 1,
                        "total": len(search_terms),
                        "message": f"📒 Searching '{term}' in {city}..."
                    })

                page_results = await self._search_yellow_pages(term, city)
                self.results.extend(page_results)

                await asyncio.sleep(random.uniform(1.5, 3.0))

            except Exception as e:
                logger.warning(f"Error searching Yellow Pages for '{term}': {e}")
                continue

        return self.results[:max_results]

    async def _search_yellow_pages(self, query: str, city: str) -> List[Dict]:
        """Search Yellow Pages for businesses."""
        results = []

        try:
            url = f"https://www.pages-jaunes.ma/search?q={quote_plus(query)}&city={quote_plus(city)}"

            response = await asyncio.to_thread(
                self.session.get, url, timeout=15
            )

            if response.status_code != 200:
                return results

            soup = BeautifulSoup(response.text, 'lxml')

            listings = soup.select('.result-item, .business-item, article, .listing')
            if not listings:
                listings = soup.select('[class*="result"], [class*="listing"]')

            for listing in listings:
                try:
                    business = {
                        'name': '',
                        'phone': '',
                        'email': '',
                        'website': '',
                        'address': '',
                        'city': city,
                        'category': query,
                        'latitude': '',
                        'longitude': '',
                        'source': 'Pages Jaunes Morocco'
                    }

                    # Extract name
                    name_el = listing.select_one('h2, h3, .name, .title')
                    if name_el:
                        business['name'] = name_el.get_text(strip=True)

                    # Extract phone
                    phone_el = listing.select_one('[class*="phone"], [class*="tel"], a[href^="tel:"]')
                    if phone_el:
                        business['phone'] = phone_el.get_text(strip=True)

                    # Extract address
                    addr_el = listing.select_one('[class*="address"], [class*="location"]')
                    if addr_el:
                        business['address'] = addr_el.get_text(strip=True)

                    if business['name']:
                        results.append(business)

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Yellow Pages error: {e}")

        return results


async def scrape_directories(city: str, category: str = "", max_results: int = 100,
                              progress_callback=None) -> List[Dict]:
    """
    Scrape from multiple Moroccan business directories.

    Args:
        city: City name
        category: Business category
        max_results: Maximum results
        progress_callback: Progress callback

    Returns:
        Combined list of business data
    """
    all_results = []

    # Scrape from Telecontact
    try:
        tc_scraper = TelecontactScraper()
        tc_results = await tc_scraper.scrape(city, category, max_results // 2, progress_callback)
        all_results.extend(tc_results)
    except Exception as e:
        logger.error(f"Telecontact scraping error: {e}")

    # Scrape from Yellow Pages
    try:
        yp_scraper = YellowPagesScraper()
        yp_results = await yp_scraper.scrape(city, category, max_results // 2, progress_callback)
        all_results.extend(yp_results)
    except Exception as e:
        logger.error(f"Yellow Pages scraping error: {e}")

    return all_results
