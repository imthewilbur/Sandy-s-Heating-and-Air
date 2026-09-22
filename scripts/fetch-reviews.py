#!/usr/bin/env python3
"""
Fetches Sandy's Heating & Air's Google reviews via the Places API (New)
and writes them directly into index.html as plain HTML, between the
<!-- REVIEWS:START --> and <!-- REVIEWS:END --> markers.

Run manually:
    GOOGLE_PLACES_API_KEY=xxx GOOGLE_PLACE_ID=xxx python3 scripts/fetch-reviews.py

In CI, both env vars come from GitHub Actions secrets — see
.github/workflows/update-google-reviews.yml

Design choice: this never touches index.html unless the API call fully
succeeds. A failed run (bad key, rate limit, network blip) just exits
non-zero and leaves the last known-good reviews on the live site.
"""

import html
import os
import re
import sys
import urllib.request
import urllib.error
import json

API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")
PLACE_ID = os.environ.get("GOOGLE_PLACE_ID")
INDEX_HTML_PATH = os.path.join(os.path.dirname(__file__), "..", "index.html")

START_MARKER = "<!-- REVIEWS:START -->"
END_MARKER = "<!-- REVIEWS:END -->"
SCHEMA_START = "<!-- REVIEW-SCHEMA:START -->"
SCHEMA_END = "<!-- REVIEW-SCHEMA:END -->"

FIELD_MASK = "id,displayName,rating,userRatingCount,googleMapsUri,reviews"


def fetch_place_details():
    url = f"https://places.googleapis.com/v1/places/{PLACE_ID}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("X-Goog-Api-Key", API_KEY)
    req.add_header("X-Goog-FieldMask", FIELD_MASK)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def star_svg(filled):
    fill = "var(--ember)" if filled else "none"
    stroke = "var(--ember)" if not filled else "none"
    return (
        f'<svg viewBox="0 0 20 20" aria-hidden="true">'
        f'<path d="M10 1.5l2.6 5.6 6 .7-4.5 4.2 1.2 6-5.3-3-5.3 3 1.2-6L1.4 7.8l6-.7z" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1"/></svg>'
    )


def stars_html(rating):
    full = round(rating)
    return "".join(star_svg(i < full) for i in range(5))


def review_card_html(review):
    author = html.escape(review.get("authorAttribution", {}).get("displayName", "A customer"))
    rating = review.get("rating", 5)
    text_obj = review.get("text") or review.get("originalText") or {}
    text = html.escape(text_obj.get("text", "")).strip()
    if len(text) > 220:
        text = text[:217].rsplit(" ", 1)[0] + "…"
    relative_time = html.escape(review.get("relativePublishTimeDescription", ""))

    return f"""        <div class="review-card">
          <div class="review-stars">{stars_html(rating)}</div>
          <p class="review-text">&ldquo;{text}&rdquo;</p>
          <div class="review-meta">
            <span class="review-author">{author}</span>
            <span class="review-date">{relative_time}</span>
          </div>
        </div>"""


def build_reviews_block(place):
    rating = place.get("rating", 0)
    count = place.get("userRatingCount", 0)
    maps_uri = place.get("googleMapsUri", "#")
    reviews = place.get("reviews", [])[:5]

    cards = "\n".join(review_card_html(r) for r in reviews)

    summary = f"""        <div class="reviews-summary">
          <div class="reviews-summary-stars">{stars_html(rating)}</div>
          <span class="reviews-summary-score">{rating:.1f}</span>
          <span class="reviews-summary-count">({count} Google reviews)</span>
          <a class="btn btn-ghost btn-accent reviews-summary-cta" href="{html.escape(maps_uri)}" target="_blank" rel="noopener">Leave a review</a>
        </div>"""

    return f"""{START_MARKER}
      <div class="reviews-widget-slot" data-reveal>
{summary}
        <div class="review-grid">
{cards}
        </div>
      </div>
      {END_MARKER}"""


def build_review_schema(place):
    """
    A small, homepage-only AggregateRating + Review block. Kept separate
    from the main LocalBusiness schema so this script only ever has to
    touch numbers it actually fetched — never guesses, never goes stale
    silently. Matches exactly what's visibly shown in the reviews section
    above, per Google's schema-must-match-visible-content requirement.
    """
    rating = place.get("rating", 0)
    count = place.get("userRatingCount", 0)
    reviews = place.get("reviews", [])[:5]

    review_entries = []
    for r in reviews:
        text_obj = r.get("text") or r.get("originalText") or {}
        review_entries.append({
            "@type": "Review",
            "author": {"@type": "Person", "name": r.get("authorAttribution", {}).get("displayName", "A customer")},
            "reviewRating": {"@type": "Rating", "ratingValue": str(r.get("rating", 5))},
            "reviewBody": text_obj.get("text", "").strip()[:300],
        })

    data = {
        "@context": "https://schema.org",
        "@type": "HVACBusiness",
        "name": "Sandy's Heating & Air",
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": str(rating),
            "reviewCount": str(count),
        },
        "review": review_entries,
    }
    return f'{SCHEMA_START}\n<script type="application/ld+json">\n{json.dumps(data, indent=2)}\n</script>\n{SCHEMA_END}'


def main():
    if not API_KEY or not PLACE_ID:
        print("Missing GOOGLE_PLACES_API_KEY or GOOGLE_PLACE_ID — aborting, leaving index.html untouched.")
        sys.exit(1)

    try:
        place = fetch_place_details()
    except urllib.error.HTTPError as e:
        print(f"Places API returned HTTP {e.code}: {e.read().decode('utf-8', 'ignore')}")
        sys.exit(1)
    except Exception as e:
        print(f"Fetch failed: {e}")
        sys.exit(1)

    if "reviews" not in place or not place.get("reviews"):
        print("API call succeeded but returned no reviews — leaving index.html untouched.")
        sys.exit(1)

    new_block = build_reviews_block(place)
    new_schema = build_review_schema(place)

    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL
    )
    if not pattern.search(html_content):
        print(f"Could not find {START_MARKER} ... {END_MARKER} markers in index.html — aborting.")
        sys.exit(1)

    schema_pattern = re.compile(
        re.escape(SCHEMA_START) + r".*?" + re.escape(SCHEMA_END), re.DOTALL
    )
    if not schema_pattern.search(html_content):
        print(f"Could not find {SCHEMA_START} ... {SCHEMA_END} markers in index.html — aborting.")
        sys.exit(1)

    updated = pattern.sub(new_block, html_content)
    updated = schema_pattern.sub(new_schema, updated)

    with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"Updated index.html with {len(place.get('reviews', [])[:5])} reviews "
          f"(rating {place.get('rating')}, {place.get('userRatingCount')} total).")


if __name__ == "__main__":
    main()
