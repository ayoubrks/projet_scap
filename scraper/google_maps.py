"""
Google Maps Scraper Module
Scrapes business data from Google Maps for Moroccan cities using Playwright.
"""

import asyncio
import logging
import re
import time
import random
from typing import List, Dict, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class GoogleMapsScraper:
    """Scrapes business information from Google Maps."""

    BASE_URL = "https://www.google.com/maps/search/"

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.results: List[Dict] = []

    async def initialize(self):
        """Initialize Playwright browser."""
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='fr-FR',
            geolocation={'latitude': 33.5731, 'longitude': -7.5898},
            permissions=['geolocation']
        )
        self.page = await self.context.new_page()

    async def close(self):
        """Close browser resources."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def scrape(self, city: str, category: str = "", max_results: int = 100,
                     progress_callback=None, deep_scrape: bool = True, country: str = "Morocco") -> List[Dict]:
        """
        Scrape business data from Google Maps.
        """
        self.results = []

        try:
            await self.initialize()

            # Build search query
            if category:
                query = f"{category} {city} {country}"
            else:
                query = f"entreprises {city} {country}"
            
            # ... rest of initial logic ...

            encoded_query = quote_plus(query)
            url = f"{self.BASE_URL}{encoded_query}"

            logger.info(f"Navigating to Google Maps: {url}")
            if progress_callback:
                progress_callback("status", f"🔍 Searching: {query}")

            # Use domcontentloaded for faster initial load
            try:
                await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            except Exception:
                try:
                    await self.page.goto(url, wait_until='load', timeout=15000)
                except Exception:
                    pass
            
            await asyncio.sleep(1.5)

            # Accept cookies if prompted (Quick check)
            try:
                selectors = [
                    'button[aria-label*="Accept"]', 
                    'button[aria-label*="Accepter"]',
                    'button:has-text("Tout accepter")',
                    'button:has-text("I agree")',
                    'button:has-text("Accept all")'
                ]
                for selector in selectors:
                    btn = await self.page.query_selector(selector)
                    if btn:
                        await btn.click(timeout=2000)
                        await asyncio.sleep(1)
                        break
            except Exception:
                pass

            # Scroll through results to load more
            results_count = 0
            scroll_attempts = 0
            max_scroll_attempts = 25 

            while results_count < max_results and scroll_attempts < max_scroll_attempts:
                # Find the scrollable results panel
                feed = await self.page.query_selector('div[role="feed"]')
                if not feed:
                    feed = await self.page.query_selector('div[aria-label*="Results"]')

                if feed:
                    await self.page.evaluate('(feed) => feed.scrollTop += 3000', feed)
                else:
                    await self.page.keyboard.press('PageDown')

                await asyncio.sleep(random.uniform(0.8, 1.5))

                # Count loaded results
                items = await self.page.query_selector_all('a[href*="/maps/place/"]')
                new_count = len(items)

                if progress_callback and new_count != results_count:
                    progress_callback("progress", {
                        "current": min(new_count, max_results),
                        "total": max_results,
                        "message": f"📍 Found {new_count} businesses..."
                    })

                # Check for end of list
                end_of_list = await self.page.query_selector('span:has-text("end of list"), span:has-text("fin de la liste")')
                if end_of_list:
                    break

                if new_count == results_count:
                    scroll_attempts += 1
                else:
                    scroll_attempts = 0
                    results_count = new_count
                
                if new_count >= max_results:
                    break

            # Extract list data
            items = await self.page.query_selector_all('div:has(> a[href*="/maps/place/"])')
            if not items:
                items = await self.page.query_selector_all('a[href*="/maps/place/"]')
                
            total_items = min(len(items), max_results)
            initial_results = []

            for i, item in enumerate(items[:max_results]):
                try:
                    # Look for the link within the container
                    link_el = await item.query_selector('a[href*="/maps/place/"]')
                    if not link_el:
                        link_el = item if (await item.get_attribute('href')) else None
                    
                    if not link_el: continue

                    business = await self._extract_business_from_list(link_el, item, city, category)
                    if business and business.get('name'):
                        initial_results.append(business)

                    if progress_callback:
                        progress_callback("progress", {
                            "current": i + 1,
                            "total": total_items,
                            "message": f"📋 Extracting {i + 1}/{total_items}: {business['name']}"
                        })
                except Exception as e:
                    logger.warning(f"Error in initial extraction {i}: {e}")

            # Now, only get detailed info if deep_scrape is enabled
            if deep_scrape:
                if progress_callback:
                    progress_callback("status", f"🔎 Vérification de {len(initial_results)} entreprises pour plus de données...")

                final_results = []
                for i, business in enumerate(initial_results):
                    # We visit the detailed page if we are missing critical fields
                    # or if we simply haven't checked for website/email yet (rarely in list view)
                    has_phone = bool(business.get('phone'))
                    has_website = bool(business.get('website'))
                    has_email = bool(business.get('email'))
                    
                    # If any of these are missing and we are in deep_scrape mode, we visit
                    if not has_phone or not has_website or not has_email:
                        try:
                            detailed = await self._get_business_details(business, city, category)
                            final_results.append(detailed)
                        except Exception as e:
                            logger.warning(f"Error getting details for {business.get('name')}: {e}")
                            final_results.append(business)
                    else:
                        final_results.append(business)

                    if progress_callback:
                        progress_callback("progress", {
                            "current": i + 1,
                            "total": len(initial_results),
                            "message": f"📊 Finalisation {i + 1}/{len(initial_results)}: {business.get('name')}"
                        })
                self.results = final_results
            else:
                self.results = initial_results
                if progress_callback:
                    progress_callback("status", f"✅ Extraction rapide terminée ({len(self.results)} résultats)")

        except Exception as e:
            logger.error(f"Google Maps scraping error: {e}")
            if progress_callback:
                progress_callback("error", f"❌ Error: {str(e)}")
        finally:
            await self.close()

        return self.results

    async def _extract_business_from_list(self, link_el, item, city: str, category: str) -> Optional[Dict]:
        """Extract basic business info from a list item."""
        try:
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
                'source': 'Google Maps'
            }

            # Get the aria-label which usually contains the business name
            aria_label = await link_el.get_attribute('aria-label')
            if aria_label:
                business['name'] = aria_label.replace('·', '').strip()

            # Get the href which contains place info
            href = await link_el.get_attribute('href')
            if href:
                # Extract coordinates from URL if available
                coords_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', href)
                if coords_match:
                    business['latitude'] = coords_match.group(1)
                    business['longitude'] = coords_match.group(2)

                business['_href'] = href

            # Try to get additional info from the parent container
            parent = await item.query_selector('..')
            if parent:
                text_content = await parent.inner_text()
                lines = [l.strip() for l in text_content.split('\n') if l.strip()]

                # Try to find phone number in text
                for line in lines:
                    phone_match = re.search(r'(?:\+212|0)[\s.-]?[567]\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}', line)
                    if phone_match:
                        business['phone'] = phone_match.group(0)

                    # Try to detect address-like content
                    if any(word in line.lower() for word in ['rue', 'av', 'avenue', 'bd', 'boulevard', 'lot', 'quartier', city.lower()]):
                        business['address'] = line

            return business if business['name'] else None

        except Exception as e:
            logger.debug(f"Error extracting from list item: {e}")
            return None

    async def _get_business_details(self, business: Dict, city: str, category: str) -> Optional[Dict]:
        """Get detailed business information by navigating to the business page."""
        try:
            href = business.get('_href', '')
            if not href:
                return business

            # Use domcontentloaded instead of networkidle to avoid infinite hangs
            try:
                await self.page.goto(href, wait_until='domcontentloaded', timeout=20000)
                # Wait for the main content to actually render
                await self.page.wait_for_selector('h1', timeout=5000)
                await asyncio.sleep(random.uniform(1.5, 2.5))
            except Exception:
                # If it fails to load completely, we still try to scrape what's there
                pass

            # Extract phone number
            try:
                # Primary: data-item-id starting with phone:tel:
                # Secondary: aria-labels in English/French
                # Tertiary: any tel link
                phone_el = await self.page.query_selector('button[data-item-id^="phone:tel:"], a[href^="tel:"], button[aria-label*="Phone"], button[aria-label*="Téléphone"]')
                if phone_el:
                    # If it's a link, get href. If it's a button, get inner text or aria-label
                    href = await phone_el.get_attribute('href')
                    if href and href.startswith('tel:'):
                        business['phone'] = href.replace('tel:', '').strip()
                    else:
                        phone_text = await phone_el.inner_text()
                        phone_match = re.search(r'[\+\d][\d\s\-\.]+\d', phone_text)
                        if phone_match:
                            business['phone'] = phone_match.group(0).strip()
                        else:
                            # Try aria-label
                            label = await phone_el.get_attribute('aria-label')
                            if label:
                                phone_match = re.search(r'[\+\d][\d\s\-\.]+\d', label)
                                if phone_match:
                                    business['phone'] = phone_match.group(0).strip()
            except Exception:
                pass

            # Alternative phone extraction (Regex search in page if still missing)
            if not business['phone']:
                try:
                    content = await self.page.content()
                    phone_match = re.search(r'(?:\+212|0)[\s.-]?[567]\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}', content)
                    if phone_match:
                        business['phone'] = phone_match.group(0)
                except Exception:
                    pass

            # Extract website
            try:
                # Primary: data-item-id="authority"
                # Secondary: aria-labels
                website_el = await self.page.query_selector('a[data-item-id="authority"], a[aria-label*="Website"], a[aria-label*="Site Web"], a[aria-label*="site web"]')
                if website_el:
                    website_url = await website_el.get_attribute('href')
                    if website_url and 'google' not in website_url:
                        business['website'] = website_url
            except Exception:
                pass

            # Extract address
            try:
                addr_el = await self.page.query_selector('button[data-item-id="address"], button[aria-label*="Address"], button[aria-label*="Adresse"]')
                if addr_el:
                    addr_text = await addr_el.inner_text()
                    if not addr_text:
                        addr_text = await addr_el.get_attribute('aria-label')
                    
                    if addr_text:
                        if ':' in addr_text: addr_text = addr_text.split(':', 1)[1]
                        business['address'] = addr_text.strip()
            except Exception:
                pass

            # Extract category if not set
            if not business.get('category') or business['category'] == '':
                try:
                    cat_btn = await self.page.query_selector('button[jsaction*="category"]')
                    if cat_btn:
                        business['category'] = (await cat_btn.inner_text()).strip()
                except Exception:
                    pass

            # Try to extract email from the page
            try:
                page_content = await self.page.content()
                email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_content)
                if email_match:
                    email = email_match.group(0)
                    if not any(x in email.lower() for x in ['google', 'gstatic', 'googleapis', 'example']):
                        business['email'] = email
            except Exception:
                pass

            # Extract coordinates from current URL
            try:
                current_url = self.page.url
                coords_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', current_url)
                if coords_match:
                    business['latitude'] = coords_match.group(1)
                    business['longitude'] = coords_match.group(2)
            except Exception:
                pass

            # Extract social networks (Instagram, Facebook, WhatsApp, TikTok)
            try:
                all_links = await self.page.query_selector_all('a[href*="instagram.com"], a[href*="facebook.com"], a[href*="wa.me"], a[href*="whatsapp.com"], a[href*="tiktok.com"]')
                for link in all_links:
                    href = await link.get_attribute('href')
                    if href:
                        if 'instagram.com' in href:
                            business['services'] = href
                        elif 'wa.me' in href or 'whatsapp' in href:
                            if not business['phone']:
                                # Try to extract phone from wa link
                                whatsapp_match = re.search(r'[\d]{10,}', href)
                                if whatsapp_match: business['phone'] = whatsapp_match.group(0)
                        elif 'facebook.com' in href and not business.get('services'):
                            business['services'] = href
            except Exception:
                pass

            # Extract booking/appointments
            try:
                booking_el = await self.page.query_selector('[data-item-id="action:2"], a[aria-label*="réservation"], a[aria-label*="rendez-vous"], a[aria-label*="booking"]')
                if booking_el:
                    booking_url = await booking_el.get_attribute('href')
                    if booking_url:
                        business['booking'] = booking_url
            except Exception:
                pass

            # Clean up internal fields
            business.pop('_href', None)

            return business

        except Exception as e:
            logger.warning(f"Error getting details: {e}")
            business.pop('_href', None)
            return business


async def scrape_google_maps(city: str, category: str = "", max_results: int = 100,
                              progress_callback=None, deep_scrape: bool = True, country: str = "Morocco") -> List[Dict]:
    """
    Convenience function to scrape Google Maps.
    """
    scraper = GoogleMapsScraper(headless=True)
    return await scraper.scrape(city, category, max_results, progress_callback, deep_scrape=deep_scrape, country=country)
