"""BigQuery Travel Intelligence — setup and seed data.

Creates a `travel_intelligence` dataset in your GCP project with tables
that the Data Fetcher agent uses for destination-aware planning.

Usage:
    python setup_bq.py

Tables created:
  - destinations       : destination profiles (cost index, safety, visa, timezone)
  - airport_lookup     : IATA→city mapping with coordinates
  - seasonal_insights  : best-visit months, crowd levels, weather patterns
  - trip_history       : past itineraries for learning/recommendations
"""

import os
import logging
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
DATASET = "travel_intelligence"
FULL_DATASET = f"{PROJECT}.{DATASET}"


def create_dataset(client: bigquery.Client):
    """Create the travel_intelligence dataset if it doesn't exist."""
    dataset_ref = bigquery.Dataset(FULL_DATASET)
    dataset_ref.location = os.getenv("GOOGLE_CLOUD_LOCATION", "US")
    dataset_ref.description = "Travel planner intelligence layer — destination data, airport lookups, seasonal insights"

    try:
        client.get_dataset(FULL_DATASET)
        log.info(f"✅ Dataset {FULL_DATASET} already exists")
    except Exception:
        client.create_dataset(dataset_ref)
        log.info(f"✅ Created dataset {FULL_DATASET}")


def create_destinations_table(client: bigquery.Client):
    """Cities with travel-relevant metadata."""
    table_id = f"{FULL_DATASET}.destinations"
    schema = [
        bigquery.SchemaField("city", "STRING", description="City name"),
        bigquery.SchemaField("country", "STRING", description="Country name"),
        bigquery.SchemaField("continent", "STRING", description="Continent"),
        bigquery.SchemaField("lat", "FLOAT64", description="Latitude"),
        bigquery.SchemaField("lng", "FLOAT64", description="Longitude"),
        bigquery.SchemaField("iata_code", "STRING", description="Primary airport IATA code"),
        bigquery.SchemaField("timezone", "STRING", description="IANA timezone"),
        bigquery.SchemaField("currency", "STRING", description="Local currency code"),
        bigquery.SchemaField("language", "STRING", description="Primary language"),
        bigquery.SchemaField("cost_index", "FLOAT64", description="Relative cost index (1=cheapest, 5=most expensive)"),
        bigquery.SchemaField("safety_score", "FLOAT64", description="Safety score 1-10"),
        bigquery.SchemaField("visa_required_for_india", "BOOL", description="Whether Indians need a visa"),
        bigquery.SchemaField("avg_daily_budget_usd", "FLOAT64", description="Average daily spend in USD (mid-range)"),
        bigquery.SchemaField("best_months", "STRING", description="Best months to visit, comma-separated"),
        bigquery.SchemaField("description", "STRING", description="Short destination description"),
    ]

    table = bigquery.Table(table_id, schema=schema)
    table.description = "Destination profiles with travel intelligence"
    try:
        client.get_table(table_id)
        log.info(f"  ✅ Table {table_id} already exists")
    except Exception:
        client.create_table(table)
        log.info(f"  ✅ Created table {table_id}")
        _seed_destinations(client, table_id)


def _seed_destinations(client: bigquery.Client, table_id: str):
    """Seed with popular destinations."""
    rows = [
        {"city": "Tokyo", "country": "Japan", "continent": "Asia", "lat": 35.6762, "lng": 139.6503,
         "iata_code": "NRT", "timezone": "Asia/Tokyo", "currency": "JPY", "language": "Japanese",
         "cost_index": 3.5, "safety_score": 9.2, "visa_required_for_india": True, "avg_daily_budget_usd": 120,
         "best_months": "Mar,Apr,Oct,Nov", "description": "A dazzling fusion of ultra-modern technology and ancient temples"},
        {"city": "Paris", "country": "France", "continent": "Europe", "lat": 48.8566, "lng": 2.3522,
         "iata_code": "CDG", "timezone": "Europe/Paris", "currency": "EUR", "language": "French",
         "cost_index": 4.0, "safety_score": 7.5, "visa_required_for_india": True, "avg_daily_budget_usd": 150,
         "best_months": "Apr,May,Jun,Sep,Oct", "description": "The City of Light — art, cuisine, and romance"},
        {"city": "Bangkok", "country": "Thailand", "continent": "Asia", "lat": 13.7563, "lng": 100.5018,
         "iata_code": "BKK", "timezone": "Asia/Bangkok", "currency": "THB", "language": "Thai",
         "cost_index": 1.5, "safety_score": 7.0, "visa_required_for_india": False, "avg_daily_budget_usd": 45,
         "best_months": "Nov,Dec,Jan,Feb", "description": "Vibrant street food, temples, and nightlife"},
        {"city": "Dubai", "country": "UAE", "continent": "Asia", "lat": 25.2048, "lng": 55.2708,
         "iata_code": "DXB", "timezone": "Asia/Dubai", "currency": "AED", "language": "Arabic",
         "cost_index": 4.5, "safety_score": 9.0, "visa_required_for_india": True, "avg_daily_budget_usd": 180,
         "best_months": "Nov,Dec,Jan,Feb,Mar", "description": "Futuristic skyline, luxury shopping, and desert adventures"},
        {"city": "Singapore", "country": "Singapore", "continent": "Asia", "lat": 1.3521, "lng": 103.8198,
         "iata_code": "SIN", "timezone": "Asia/Singapore", "currency": "SGD", "language": "English",
         "cost_index": 4.0, "safety_score": 9.5, "visa_required_for_india": False, "avg_daily_budget_usd": 130,
         "best_months": "Feb,Mar,Apr,Jul,Aug", "description": "Garden city — Marina Bay, hawker food, and clean streets"},
        {"city": "London", "country": "United Kingdom", "continent": "Europe", "lat": 51.5074, "lng": -0.1278,
         "iata_code": "LHR", "timezone": "Europe/London", "currency": "GBP", "language": "English",
         "cost_index": 4.5, "safety_score": 7.8, "visa_required_for_india": True, "avg_daily_budget_usd": 160,
         "best_months": "May,Jun,Jul,Aug,Sep", "description": "Royal palaces, world-class museums, and iconic landmarks"},
        {"city": "Bali", "country": "Indonesia", "continent": "Asia", "lat": -8.3405, "lng": 115.092,
         "iata_code": "DPS", "timezone": "Asia/Makassar", "currency": "IDR", "language": "Indonesian",
         "cost_index": 1.5, "safety_score": 7.5, "visa_required_for_india": False, "avg_daily_budget_usd": 50,
         "best_months": "Apr,May,Jun,Sep,Oct", "description": "Tropical paradise — rice terraces, temples, and surf"},
        {"city": "New York", "country": "United States", "continent": "North America", "lat": 40.7128, "lng": -74.006,
         "iata_code": "JFK", "timezone": "America/New_York", "currency": "USD", "language": "English",
         "cost_index": 5.0, "safety_score": 7.0, "visa_required_for_india": True, "avg_daily_budget_usd": 200,
         "best_months": "Apr,May,Sep,Oct,Dec", "description": "The city that never sleeps — Broadway, Central Park, skyline views"},
        {"city": "Istanbul", "country": "Turkey", "continent": "Europe", "lat": 41.0082, "lng": 28.9784,
         "iata_code": "IST", "timezone": "Europe/Istanbul", "currency": "TRY", "language": "Turkish",
         "cost_index": 2.0, "safety_score": 7.2, "visa_required_for_india": True, "avg_daily_budget_usd": 60,
         "best_months": "Apr,May,Sep,Oct", "description": "Where East meets West — bazaars, mosques, and Bosphorus views"},
        {"city": "Goa", "country": "India", "continent": "Asia", "lat": 15.2993, "lng": 74.124,
         "iata_code": "GOI", "timezone": "Asia/Kolkata", "currency": "INR", "language": "Konkani",
         "cost_index": 1.0, "safety_score": 7.5, "visa_required_for_india": False, "avg_daily_budget_usd": 30,
         "best_months": "Nov,Dec,Jan,Feb,Mar", "description": "Beaches, Portuguese heritage, and legendary nightlife"},
    ]

    errors = client.insert_rows_json(table_id, rows)
    if errors:
        log.warning(f"  ⚠️ Seed errors: {errors}")
    else:
        log.info(f"  ✅ Seeded {len(rows)} destinations")


def create_airport_lookup_table(client: bigquery.Client):
    """IATA↔city mapping for flight routing."""
    table_id = f"{FULL_DATASET}.airport_lookup"
    schema = [
        bigquery.SchemaField("iata_code", "STRING"),
        bigquery.SchemaField("airport_name", "STRING"),
        bigquery.SchemaField("city", "STRING"),
        bigquery.SchemaField("country", "STRING"),
        bigquery.SchemaField("lat", "FLOAT64"),
        bigquery.SchemaField("lng", "FLOAT64"),
    ]
    table = bigquery.Table(table_id, schema=schema)
    table.description = "Airport IATA code lookup for flight routing"
    try:
        client.get_table(table_id)
        log.info(f"  ✅ Table {table_id} already exists")
    except Exception:
        client.create_table(table)
        log.info(f"  ✅ Created table {table_id}")
        rows = [
            {"iata_code": "BLR", "airport_name": "Kempegowda International", "city": "Bengaluru", "country": "India", "lat": 13.1986, "lng": 77.7066},
            {"iata_code": "DEL", "airport_name": "Indira Gandhi International", "city": "Delhi", "country": "India", "lat": 28.5562, "lng": 77.1000},
            {"iata_code": "BOM", "airport_name": "Chhatrapati Shivaji Maharaj", "city": "Mumbai", "country": "India", "lat": 19.0896, "lng": 72.8656},
            {"iata_code": "NRT", "airport_name": "Narita International", "city": "Tokyo", "country": "Japan", "lat": 35.7647, "lng": 140.3864},
            {"iata_code": "HND", "airport_name": "Haneda", "city": "Tokyo", "country": "Japan", "lat": 35.5494, "lng": 139.7798},
            {"iata_code": "CDG", "airport_name": "Charles de Gaulle", "city": "Paris", "country": "France", "lat": 49.0097, "lng": 2.5479},
            {"iata_code": "LHR", "airport_name": "Heathrow", "city": "London", "country": "UK", "lat": 51.4700, "lng": -0.4543},
            {"iata_code": "JFK", "airport_name": "John F. Kennedy", "city": "New York", "country": "USA", "lat": 40.6413, "lng": -73.7781},
            {"iata_code": "DXB", "airport_name": "Dubai International", "city": "Dubai", "country": "UAE", "lat": 25.2532, "lng": 55.3657},
            {"iata_code": "SIN", "airport_name": "Changi", "city": "Singapore", "country": "Singapore", "lat": 1.3644, "lng": 103.9915},
            {"iata_code": "BKK", "airport_name": "Suvarnabhumi", "city": "Bangkok", "country": "Thailand", "lat": 13.6900, "lng": 100.7501},
            {"iata_code": "DPS", "airport_name": "Ngurah Rai", "city": "Bali", "country": "Indonesia", "lat": -8.7482, "lng": 115.1672},
            {"iata_code": "IST", "airport_name": "Istanbul Airport", "city": "Istanbul", "country": "Turkey", "lat": 41.2614, "lng": 28.7419},
            {"iata_code": "GOI", "airport_name": "Goa Manohar Int'l", "city": "Goa", "country": "India", "lat": 15.3808, "lng": 73.8314},
        ]
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            log.warning(f"  ⚠️ Seed errors: {errors}")
        else:
            log.info(f"  ✅ Seeded {len(rows)} airports")


def create_seasonal_insights_table(client: bigquery.Client):
    """Monthly travel conditions per destination."""
    table_id = f"{FULL_DATASET}.seasonal_insights"
    schema = [
        bigquery.SchemaField("city", "STRING"),
        bigquery.SchemaField("month", "INT64", description="1-12"),
        bigquery.SchemaField("avg_temp_c", "FLOAT64"),
        bigquery.SchemaField("rain_mm", "FLOAT64"),
        bigquery.SchemaField("crowd_level", "STRING", description="low/medium/high/peak"),
        bigquery.SchemaField("recommended", "BOOL"),
        bigquery.SchemaField("note", "STRING"),
    ]
    table = bigquery.Table(table_id, schema=schema)
    table.description = "Monthly travel conditions for seasonal trip planning"
    try:
        client.get_table(table_id)
        log.info(f"  ✅ Table {table_id} already exists")
    except Exception:
        client.create_table(table)
        log.info(f"  ✅ Created table {table_id}")
        # Seed a subset — Tokyo months
        rows = [
            {"city": "Tokyo", "month": m, "avg_temp_c": t, "rain_mm": r, "crowd_level": c, "recommended": rec, "note": n}
            for m, t, r, c, rec, n in [
                (1, 5, 52, "low", True, "Winter sales, few tourists"),
                (2, 6, 56, "low", True, "Plum blossoms start"),
                (3, 10, 117, "medium", True, "Cherry blossom season begins"),
                (4, 15, 125, "peak", True, "Peak sakura — book early"),
                (5, 20, 138, "medium", True, "Pleasant weather, Golden Week crowds"),
                (6, 22, 168, "low", False, "Rainy season (tsuyu)"),
                (7, 26, 154, "medium", False, "Hot and humid"),
                (8, 27, 168, "high", False, "Obon holiday, very hot"),
                (9, 23, 210, "medium", False, "Typhoon risk"),
                (10, 18, 198, "medium", True, "Autumn foliage begins"),
                (11, 13, 93, "high", True, "Peak koyo — beautiful fall colors"),
                (12, 8, 51, "medium", True, "Winter illuminations"),
            ]
        ]
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            log.warning(f"  ⚠️ Seed errors: {errors}")
        else:
            log.info(f"  ✅ Seeded {len(rows)} seasonal records")


def create_trip_history_table(client: bigquery.Client):
    """Past trip records for learning and recommendations."""
    table_id = f"{FULL_DATASET}.trip_history"
    schema = [
        bigquery.SchemaField("trip_id", "STRING"),
        bigquery.SchemaField("origin", "STRING"),
        bigquery.SchemaField("destination", "STRING"),
        bigquery.SchemaField("start_date", "DATE"),
        bigquery.SchemaField("end_date", "DATE"),
        bigquery.SchemaField("num_travelers", "INT64"),
        bigquery.SchemaField("budget_level", "STRING"),
        bigquery.SchemaField("total_cost_usd", "FLOAT64"),
        bigquery.SchemaField("rating", "FLOAT64", description="User satisfaction 1-5"),
        bigquery.SchemaField("itinerary_json", "STRING", description="Stored TravelItinerary JSON"),
        bigquery.SchemaField("created_at", "TIMESTAMP"),
    ]
    table = bigquery.Table(table_id, schema=schema)
    table.description = "Historical trip records for personalization and analytics"
    try:
        client.get_table(table_id)
        log.info(f"  ✅ Table {table_id} already exists")
    except Exception:
        client.create_table(table)
        log.info(f"  ✅ Created table {table_id}")


def main():
    if not PROJECT:
        print("❌ GOOGLE_CLOUD_PROJECT not set. Check your .env file.")
        return

    log.info(f"\n🔧 Setting up BigQuery travel intelligence for project: {PROJECT}")
    log.info(f"   Dataset: {FULL_DATASET}\n")

    client = bigquery.Client(project=PROJECT)

    create_dataset(client)
    create_destinations_table(client)
    create_airport_lookup_table(client)
    create_seasonal_insights_table(client)
    create_trip_history_table(client)

    log.info(f"\n✅ BigQuery travel intelligence ready!")
    log.info(f"   Query example:")
    log.info(f"   SELECT city, avg_daily_budget_usd, best_months FROM `{FULL_DATASET}.destinations` WHERE cost_index <= 2.0")


if __name__ == "__main__":
    main()
