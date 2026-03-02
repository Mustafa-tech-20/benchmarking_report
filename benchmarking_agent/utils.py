from typing import Dict, Any, List

from benchmarking_agent.Internal_Car_tools import CAR_SPECS


def normalize_car_name_for_url(car_name: str) -> str:
    """Normalize car name for URL format."""
    brands = ["mahindra", "tata", "hyundai", "mg", "toyota", "maruti", "suzuki", "kia",
              "honda", "ford", "jeep", "skoda", "volkswagen", "nissan", "renault", "citroen"]

    car_name_lower = car_name.lower()
    for brand in brands:
        car_name_lower = car_name_lower.replace(brand + " ", "")

    url_name = car_name_lower.strip().replace(" ", "-")
    return url_name


def get_brand_name(car_name: str) -> str:
    """Extract brand name from car name."""
    brands = ["mahindra", "tata", "hyundai", "mg", "toyota", "maruti", "kia",
              "honda", "ford", "jeep", "skoda", "volkswagen", "nissan", "renault", "citroen"]

    car_name_lower = car_name.lower()
    for brand in brands:
        if brand in car_name_lower:
            return brand

    return car_name.split()[0].lower()


def generate_sales_data_urls(car_name: str) -> List[str]:
    """Generate URLs specifically for sales data."""
    brand = get_brand_name(car_name)
    url_car_name = normalize_car_name_for_url(car_name)

    sales_urls = [
        # GoodReturns - Monthly sales figures
        f"https://www.goodreturns.in/cars/{brand}-{url_car_name}-sales.html",

        # CardDekho News - Sales reports
        f"https://www.cardekho.com/india-car-news/{url_car_name}-sales-report",

        # AutoPortal - Sales data
        f"https://www.autoportal.com/{brand}/{url_car_name}/sales",
        f"https://www.autoportal.com/newcars/{brand}/{url_car_name}",

        # ZigWheels News - Sales analysis
        f"https://www.zigwheels.com/news-features/news/{brand}-{url_car_name}-sales",

        # CarAndBike - Sales insights
        f"https://www.carandbike.com/{brand}-cars/{url_car_name}-sales",
    ]

    return sales_urls


def count_populated_fields(car_data: Dict[str, Any], field_list: List[str]) -> int:
    """Count how many fields have valid data (not 'Not Available')."""
    return sum(
        1 for field in field_list
        if car_data.get(field) not in ["Not Available", "N/A", None, ""]
        and str(car_data.get(field, "")).strip()
    )


def is_code_car(car_name: str) -> bool:
    """
    Check if a car name is a code/custom car.
    Code cars are identified ONLY by the 'CODE:' prefix (case-insensitive).
    """
    return car_name.strip().upper().startswith("CODE:")
