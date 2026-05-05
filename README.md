# Flight Price Trends — EBB → DXB

This repository collects and analyzes flight price trends for the route from Entebbe International Airport (EBB) to Dubai International Airport (DXB).

The project supports two modes:
- **Live scraping** from Google Flights, with optional Playwright support for JavaScript-rendered pages
- **Synthetic data generation** to allow reproducible analysis when live scraping is blocked or unavailable

## Features

- Scrape or simulate flight prices for one-way EBB → DXB travel
- Generate a synthetic 12-week dataset with airline, departure date, days-to-departure, price, and seasonality factors
- Save results automatically to `data/` as CSV
- Supports fallback to offline synthetic pricing when live scraping fails

## Installation

1. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Install Playwright for live scraping:
   ```bash
   pip install -r requirements-dev.txt
   playwright install chromium
   ```

## Usage

Run the scraper from the repository root:

```bash
python src/flight_scraper.py
```

By default, the script attempts live scraping first. If it cannot retrieve price data, it falls back to generating synthetic price records.

## Configuration

The script currently uses constants defined in `src/flight_scraper.py`:
- `ORIGIN` = `EBB`
- `DESTINATION` = `DXB`
- `CURRENCY` = `USD`
- `WEEKS_AHEAD` = `12`
- `USE_PLAYWRIGHT` = `True`
- `OUTPUT_DIR` = `data`
- `REQUEST_DELAY` = `3.0`

> Tip: If you want environment-based configuration, add `.env` support with `python-dotenv` and update the script accordingly.

## Output

The scraper writes CSV files into `data/`:
- `flight_prices_live.csv` when live scraping succeeds
- `flight_prices_ebb_dxb.csv` when synthetic data is generated

A log file is also created at `flight_scraper.log`.

## Insights from Visual Analysis

The included dashboard visualization highlights these patterns:

- **Best booking window:** ~28 days before departure.
- **Lowest observed price:** around `$280`.
- **Highest observed price:** around `$1,083`.
- **Savings potential:** up to `74%` by booking at the right time.

### Pricing patterns

- **Price vs departure date:** Prices fluctuate through the 12-week horizon, but the general pattern shows periodic dips and rises around the middle of the booking window.
- **Days-to-departure:** The cheapest prices appear roughly 30–40 days before departure, while prices climb sharply in the final 10–14 days.
- **Departure day of week:**
  - Lowest average prices: **Wednesday, Tuesday, Monday, Thursday**
  - Highest average prices: **Saturday, Friday, Sunday**
- **Airline ranking by average price:**
  - Most expensive: **Qatar Airways, Emirates, Turkish Airlines**
  - Lower-cost carriers: **Air Arabia, Flydubai, Uganda Airlines**

## Recommendations

1. **Book around 3–4 weeks before departure** to access the lowest average fares.
2. **Avoid last-minute bookings** within the final 10–14 days unless necessary.
3. **Travel midweek** if price is the priority; Saturdays and Fridays are typically more expensive.
4. **Compare carriers:** budget and mid-market airlines such as Air Arabia and Flydubai offer the cheapest synthetic fares in the modeled data.
5. **Use the synthetic fallback** when live scraping is blocked or if scraping reliability is low.

## Notes

- Google Flights is highly JavaScript-driven, so scraping with plain `requests` may fail often.
- Live scraping is more reliable when `USE_PLAYWRIGHT = True`, but Playwright adds installation overhead.
- This project is best used for trend exploration and analysis rather than guaranteed real-time fare booking recommendations.

## License

This repository is released under the terms of the included `LICENSE`.
