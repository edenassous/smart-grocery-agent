"""
מוריד עוד קבצי PriceFull משופרסל להגדלת כיסוי.
"""
from il_supermarket_scarper import ScarpingTask, ScraperFactory
from il_supermarket_scarper.utils import FileTypesFilters


def main():
    scraper = ScarpingTask(
        enabled_scrapers=[ScraperFactory.SHUFERSAL.name],
        files_types=[FileTypesFilters.PRICE_FULL_FILE.name],
    )
    scraper.start(limit=5)
    scraper.join()
    print("\n✓ הסתיימה הורדת קבצי שופרסל")


if __name__ == "__main__":
    main()
