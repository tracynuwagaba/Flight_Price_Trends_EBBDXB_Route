'''
flight scraper.py
-----------------
Flight price scraper for EBB -> DXB (Kampala to Dubai).

Data strategy:
    Primary  - Scrap Google Flights public search page (no API key needed)
    Fallback - Kayak/Skyscanner public pages
    Offline  - Realistic synthetic data generator used when live scraping is blocked 
               by JS rendering, for reproducible analysis/testing

For production use with live data, install Playwright:
    pip install playwright && playwright install chromium
THEN set USE_PLAYWRIGHT = True below.
'''

import requests
from bs4 import BeautifulSoup
import pandas as pd 
import numpy as np
import time
import logging
import os
import json 
from datetime import datetime, timedelta 
from typing import Optional

# Config
ORIGIN         = "EBB" # Entebbe International Airport
DESTINATION    = "DXB" # Dubai International Airport
CURRENCY       = "USD"
WEEKS_AHEAD    = 12
USE_PLAYWRIGHT = True # Set to True to enable live Playwright scraping

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_DELAY = 3.0
OUTPUT_DIR    = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("flight_scraper.log")]
)
logger = logging.getLogger(__name__)


# Live Scraper (requests + BeautifulSoup)
def scrape_google_flights(date_str: str) -> Optional[float]:
    '''
    Attempt to scrape the cheapest one way flights from Google Flights for EBB -> DXB
    on a given date.

    Parameters
    ----------
    date_str: str
        Departure date in YYYY-MM-DD format.

    Returns
    -------
    float | None
        Cheapest price found in USD, or None if scraping fails.

    Notes
    -----
    Google Flights is heavily JavaScript rendered. This static scraper captures prices
    when they appear in the pre-rendered HTML.
    For full reliability, use Playwright (USE_PLAYWRIGHT = True).
    '''

    url = (
        f"https://www.google.com/travel/flights/search?"
        f"tfs=CBwQAhokagcIARIDRUJCEgoyMDI2LXtEQVRFfXILCAESB0RYQiABGAFwAYIBCwgBEgdEWEIgARgB"
        f"&curr={CURRENCY}"
    )
    # Replace placeholder date
    url = url.replace("{DATE}", date_str.replace("-", ""))

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        time.sleep(REQUEST_DELAY)

        # Google Flight prices appear in spans with arial-label containing "$"
        price_spans = soup.find_all("span", attrs={"arial-label": True})
        for span in price_spans:
            label = span.get("arial-label", "")
            if "$" in label or "USD" in label:
                price_str = "".join(c for c in label if c.isdigit() or c == ".")
                if price_str:
                    return float(price_str)
    except Exception as e:
        logger.warning(f"Scrape failed for {date_str}: {e}")

    return None


def scrape_with_playwright(date_str: str) -> Optional[float]:
    '''
    Use Playwright headless browser to scrape Google Flight prices.
    Requires: pip install playwright && playwright install chromium

    Parameters
    ----------
    date_str: str - departure date YYYY-MM-DD

    Returns
    -------
    float | None
    '''

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers(HEADERS)

            url = (
                f"https://www.google.com/travel/flights?q="
                f"flights+from+{ORIGIN}+to+{DESTINATION}+on+{date_str}"
            )
            page.goto(url, timeout=30000)
            page.wait_for_timeout(4000) # wait for JS to render price

            # Look for price elements
            price_els = page.query_selector_all("[data-gs] span")
            for el in price_els:
                text = el.inner_text().strip()
                if "$" in text:
                    price_str = "".join(c for c in text if c.isdigit() or c ==".")
                    if price_str:
                        browser.close()
                        return float(price_str)
            browser.close()
    except ImportError:
        logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")
    except Exception as e:
        logger.warning(f"Playwright scrape failed for {date_str}: {e}")

    return None

# Synthetic Data Generator
def generate_synthetic_prices(
        origin: str = ORIGIN,
        destination: str = DESTINATION,
        weeks: int = WEEKS_AHEAD,
        seed: int = 42
) -> pd.DataFrame:
    '''
    Generate realistic synthetic flight price data for analysis.

    Simulates the pricing patterns observed on EBB -> DXB routes:
    - Base fare ~$450–650 depending on airline and season
    - Weekend premium (Fri/Sat typically higher)
    - Advance booking discount (prices spike in final 2 weeks)
    - Random market noise
    - Occasional sales / flash deals
    - Days-to-departure price curve (key pattern to analyse)

    Parameters
    ----------
    origin      : str  — IATA origin code
    destination : str  — IATA destination code
    weeks       : int  — Number of weeks of data to generate
    seed        : int  — Random seed for reproducibility
 
    Returns
    -------
    pd.DataFrame
        Columns: search_date, departure_date, days_to_departure,
                 price_usd, airline, day_of_week, week_number,
                 is_weekend, month, scrape_timestamp
    '''

    rng = np.random.default_rng(seed)

    airlines = {
        "Emirates":         {"base": 580, "variance": 80},
        "Kenya Airways":    {"base": 490, "variance": 70},
        "Ethiopian Airlines":{"base": 460, "variance": 65},
        "Flydubai":         {"base": 420, "variance": 90},
        "Qatar Airways":    {"base": 610, "variance": 85},
        "Turkish Airlines": {"base": 530, "variance": 75},
        "Air Arabia":      {"base": 400, "variance": 100},
        "RwandAir":        {"base": 470, "variance": 70},
        "EgyptAir":       {"base": 480, "variance": 65},
        "Uganda Airlines":  {"base": 450, "variance": 60},
    }

    # Day of week multipliers (Mon=0 ... Sun=6)
    dow_multipliers = {0: 0.97, 1: 0.95, 2: 0.93, 3: 0.98, 4: 1.08, 5: 1.15, 6: 1.06}

    # Days to departure price curve
    # Far out = moderate, mid-range = cheapest, close-in = expensive

    def days_to_dep_factor(d: int) -> float:
        """
        Calculate the price factor based on days to departure.

        Parameters
        ----------
        d : int
            Days to departure.

        Returns
        -------
        float
            Price factor.
        """
        if d >= 60:   return 1.05 + rng.uniform(-0.03, 0.03)
        if d >= 45:   return 0.98 + rng.uniform(-0.03, 0.03)
        if d >= 30:   return 0.93 + rng.uniform(-0.03, 0.03)   # sweet spot
        if d >= 21:   return 0.96 + rng.uniform(-0.03, 0.03)
        if d >= 14:   return 1.04 + rng.uniform(-0.04, 0.04)
        if d >= 7:    return 1.18 + rng.uniform(-0.05, 0.05)
        return             1.35 + rng.uniform(-0.05, 0.08)      # last minute spike
    
    records = []
    today = datetime(2026, 5, 3)

    # For each departure date in next `weeks` weeks
    for week_offset in range(weeks):
        for day_offset in range(7):
            dep_date = today + timedelta(weeks=week_offset, days=day_offset)
 
            # For each departure date, simulate price checks at different
            # days-to-departure (as if we scraped every few days)
            for days_before in [84, 77, 70, 63, 56, 49, 42, 35, 28, 21, 14, 10, 7, 5, 3, 2, 1]:
                search_date = dep_date - timedelta(days=days_before)
                if search_date < today:
                    search_date = today  # clamp to today
 
                for airline, params in airlines.items():
                    base   = params["base"]
                    var    = params["variance"]
                    dow    = dep_date.weekday()
                    dtd_f  = days_to_dep_factor(days_before)
                    dow_f  = dow_multipliers[dow]
 
                    # Seasonal factor (summer slightly pricier)
                    month  = dep_date.month
                    season_f = 1.0 + 0.05 * np.sin((month - 3) * np.pi / 6)
 
                    # Flash sale (5% chance)
                    sale_f = 0.82 if rng.random() < 0.05 else 1.0
 
                    # Compute price
                    noise = rng.normal(0, var * 0.25)
                    price = base * dtd_f * dow_f * season_f * sale_f + noise
                    price = max(280, round(price, 2))   # floor at $280
 
                    records.append({
                        "search_date":       search_date.date(),
                        "departure_date":    dep_date.date(),
                        "days_to_departure": days_before,
                        "price_usd":         price,
                        "airline":           airline,
                        "day_of_week":       dep_date.strftime("%A"),
                        "week_number":       week_offset + 1,
                        "is_weekend":        dow in (4, 5, 6),
                        "month":             dep_date.strftime("%B"),
                        "scrape_timestamp":  datetime.now().isoformat(),
                    })
 
    df = pd.DataFrame(records)
    logger.info(f"Generated {len(df):,} synthetic price records for {origin} → {destination}")
    return df
 

# Main Collection Function
def collect_prices(use_live: bool = True) -> pd.DataFrame:
    """
    Collect flight price data for EBB → DXB.
 
    Parameters
    ----------
    use_live : bool
        If True, attempt live scraping first; fall back to synthetic on failure.
        If False, use synthetic data directly (default for analysis/testing).
 
    Returns
    -------
    pd.DataFrame  — full price dataset
    """
    if use_live:
        logger.info("Attempting live scraping...")
        records = []
        today = datetime.now()
        for days_ahead in range(1, WEEKS_AHEAD * 7 + 1):
            dep_date = today + timedelta(days=days_ahead)
            date_str = dep_date.strftime("%Y-%m-%d")
 
            price = (scrape_with_playwright(date_str)
                     if USE_PLAYWRIGHT else scrape_google_flights(date_str))
 
            if price:
                records.append({
                    "search_date":       today.date(),
                    "departure_date":    dep_date.date(),
                    "days_to_departure": days_ahead,
                    "price_usd":         price,
                    "airline":           "Best available",
                    "day_of_week":       dep_date.strftime("%A"),
                    "scrape_timestamp":  datetime.now().isoformat(),
                })
                logger.info(f"  {date_str}: ${price:.0f}")
 
        if records:
            df = pd.DataFrame(records)
            save_path = os.path.join(OUTPUT_DIR, "flight_prices_live.csv")
            df.to_csv(save_path, index=False)
            logger.info(f"Saved live data → {save_path}")
            return df
        else:
            logger.warning("Live scraping returned no data. Falling back to synthetic.")
 
    logger.info("Generating synthetic price data...")
    df = generate_synthetic_prices()
    save_path = os.path.join(OUTPUT_DIR, "flight_prices_ebb_dxb.csv")
    df.to_csv(save_path, index=False)
    logger.info(f"Saved synthetic data → {save_path}")
    return df
 
 
if __name__ == "__main__":
    df = collect_prices(use_live=True)
    print(f"\nDataset shape: {df.shape}")
    print(df.head(10).to_string(index=False))