"""
Car Scout - Firecrawl-based scraper for Cars.com and CarGurus.
Scrapes search results pages and parses listing data from markdown.
"""

import os
import re
import logging
from firecrawl import FirecrawlApp

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)


def get_firecrawl():
    api_key = os.getenv('FIRECRAWL_API_KEY')
    if not api_key:
        raise RuntimeError('FIRECRAWL_API_KEY not set in environment')
    return FirecrawlApp(api_key=api_key)


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------

def build_cars_com_url(search, config):
    make = search['make']
    model = search['model']
    params = (
        f"stock_type=used"
        f"&makes%5B%5D={make}"
        f"&models%5B%5D={model}"
        f"&year_min={config['year_min']}"
        f"&mileage_max={config['mileage_max']}"
        f"&zip={config['zip']}"
        f"&maximum_distance={config['radius_miles']}"
        f"&sort=list_date_desc"
    )
    if config.get('one_owner'):
        params += "&one_owner=true"
    if config.get('no_accidents'):
        params += "&no_accidents=true"
    return f"https://www.cars.com/shopping/results/?{params}"


def build_cargurus_url(search, config):
    entity_id = search.get('cargurus_entity_id', '')
    if not entity_id:
        return None
    params = (
        f"zip={config['zip']}"
        f"&distance={config['radius_miles']}"
        f"&minMileage={config['mileage_min']}"
        f"&maxMileage={config['mileage_max']}"
        f"&minYear={config['year_min']}"
        f"&entityId={entity_id}"
        f"&sortDir=DESC"
        f"&sortType=LIST_DATE"
    )
    if config.get('no_accidents'):
        params += "&hasAccidents=false"
    if config.get('one_owner'):
        params += "&ownerCount=1"
    return f"https://www.cargurus.com/Cars/inventorylisting/viewDetailsFilterViewInventoryListing.action?{params}"


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_cars_com(markdown, search):
    """Parse Cars.com search results markdown into listing dicts."""
    listings = []

    # Each listing has a heading: ## [Title](url)
    heading_re = re.compile(
        r'## \[(.+?)\]\((https://www\.cars\.com/vehicledetail/([a-f0-9\-]+)/[^)]*)\)'
    )

    matches = list(heading_re.finditer(markdown))
    for i, match in enumerate(matches):
        title = match.group(1)
        url = match.group(2).split('?')[0]
        listing_id = match.group(3)

        # Context before heading: price and mileage
        prev_end = matches[i - 1].end() if i > 0 else 0
        before = markdown[prev_end:match.start()]

        # Context after heading: location (next 600 chars)
        after = markdown[match.end():match.end() + 600]

        # Price — first $XX,XXX pattern before heading
        price_match = re.search(r'\$([\d,]{4,})', before)
        price = price_match.group(1) if price_match else None

        # Mileage — "XX,XXX mi."
        mileage_match = re.search(r'([\d,]+)\s+mi\.', before)
        mileage = None
        if mileage_match:
            mileage = int(mileage_match.group(1).replace(',', ''))

        # Location — "City, ST (XX mi)"
        location_match = re.search(r'([A-Za-z][A-Za-z\s]+,\s*[A-Z]{2}\s*\(\d+\s*mi\))', after)
        location = location_match.group(1).strip() if location_match else None

        # Image URL — first cstatic-images URL in the block before heading
        img_match = re.search(r'!\[.*?\]\((https://platform\.cstatic-images\.com/[^)]+)\)', before)
        image_url = img_match.group(1) if img_match else None

        listing = {
            'id': f'carscom_{listing_id}',
            'source': 'Cars.com',
            'vehicle': search['display_name'],
            'title': title,
            'url': url,
            'price': price,
            'mileage': mileage,
            'location': location,
            'image_url': image_url,
        }
        listings.append(listing)

    log.info(f"Cars.com parsed {len(listings)} listings for {search['display_name']}")
    return listings


def parse_cargurus(markdown, search):
    """Parse CarGurus search results markdown into listing dicts."""
    listings = []

    # CarGurus listings have a heading like: ## [Title](url)
    heading_re = re.compile(
        r'## \[(.+?)\]\((https://www\.cargurus\.com/Cars/[^)]+)\)'
    )

    matches = list(heading_re.finditer(markdown))
    for i, match in enumerate(matches):
        title = match.group(1)
        url = match.group(2).split('?')[0]

        # Extract listing ID from URL
        id_match = re.search(r'listing=(\d+)', match.group(2))
        listing_id = id_match.group(1) if id_match else re.sub(r'[^a-z0-9]', '', url[-30:])

        prev_end = matches[i - 1].end() if i > 0 else 0
        before = markdown[prev_end:match.start()]
        after = markdown[match.end():match.end() + 600]

        price_match = re.search(r'\$([\d,]{4,})', before)
        price = price_match.group(1) if price_match else None

        mileage_match = re.search(r'([\d,]+)\s+mi', before)
        mileage = None
        if mileage_match:
            mileage = int(mileage_match.group(1).replace(',', ''))

        location_match = re.search(r'([A-Za-z][A-Za-z\s]+,\s*[A-Z]{2})', after)
        location = location_match.group(1).strip() if location_match else None

        img_match = re.search(r'!\[.*?\]\((https://[^)]+(?:jpg|jpeg|png|webp)[^)]*)\)', before)
        image_url = img_match.group(1) if img_match else None

        listings.append({
            'id': f'cargurus_{listing_id}',
            'source': 'CarGurus',
            'vehicle': search['display_name'],
            'title': title,
            'url': url,
            'price': price,
            'mileage': mileage,
            'location': location,
            'image_url': image_url,
        })

    log.info(f"CarGurus parsed {len(listings)} listings for {search['display_name']}")
    return listings


# ---------------------------------------------------------------------------
# Post-filter
# ---------------------------------------------------------------------------

def apply_filters(listings, config):
    """Remove listings that don't meet mileage_min (Cars.com ignores it in URL)."""
    filtered = []
    for l in listings:
        if l.get('mileage') is not None:
            if l['mileage'] < config.get('mileage_min', 0):
                continue
            if l['mileage'] > config.get('mileage_max', 999999):
                continue
        filtered.append(l)
    return filtered


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_all(config):
    """Scrape all sites and return deduplicated, filtered listings."""
    app = get_firecrawl()
    all_listings = []
    seen_ids = set()

    for search in config['searches']:
        # Cars.com
        try:
            url = build_cars_com_url(search, config)
            log.info(f"Scraping Cars.com for {search['display_name']}: {url}")
            result = app.scrape(url, formats=['markdown'])
            listings = parse_cars_com(result.markdown, search)
            listings = apply_filters(listings, config)
            for l in listings:
                if l['id'] not in seen_ids:
                    seen_ids.add(l['id'])
                    all_listings.append(l)
        except Exception as e:
            log.error(f"Cars.com scrape failed for {search['display_name']}: {e}")

        # CarGurus
        try:
            url = build_cargurus_url(search, config)
            if not url:
                log.warning(f"No CarGurus entity ID for {search['display_name']} — skipping")
                continue
            log.info(f"Scraping CarGurus for {search['display_name']}: {url}")
            result = app.scrape(url, formats=['markdown'])
            listings = parse_cargurus(result.markdown, search)
            listings = apply_filters(listings, config)
            for l in listings:
                if l['id'] not in seen_ids:
                    seen_ids.add(l['id'])
                    all_listings.append(l)
        except Exception as e:
            log.error(f"CarGurus scrape failed for {search['display_name']}: {e}")

    log.info(f"Total listings after dedup + filter: {len(all_listings)}")
    return all_listings
