from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from serpapi import GoogleSearch
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# ✅ Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/prices.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ✅ Keep API key in environment variable (more secure)
# Run this in terminal before starting app:
# Windows: set SERPAPI_KEY=your-key-here
# Then access it here safely
API_KEY = os.environ.get("SERPAPI_KEY")

if not API_KEY:
    raise ValueError("SERPAPI_KEY environment variable not set")



# ✅ Database Model
class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(200))
    title = db.Column(db.String(500))
    price = db.Column(db.Float)
    site = db.Column(db.String(100))
    date = db.Column(db.DateTime, default=datetime.utcnow)


# Create tables
with app.app_context():
    db.create_all()


@app.route("/")
def home():
    return render_template("index.html")


def parse_price(price_str):
    # Convert "₹17,399" → 17399.0
    try:
        return float(price_str.replace("₹", "").replace(",", "").strip())
    except:
        return None

def get_direct_link(p):
    """
    Extract the best direct product URL.
    """
    sources = p.get("multiple_sources", [])
    
    # ✅ Fix: make sure sources is actually a list, not True/False
    if isinstance(sources, list) and len(sources) > 0:
        direct = sources[0].get("link", "")
        if direct:
            return direct

    product_link = p.get("product_link", "")
    if product_link:
        return product_link

    return "#"

def get_products(query):
    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": "in",
        "hl": "en",
        "api_key": API_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()
    products = results.get("shopping_results", [])

    final = []
    for p in products[:12]:
        title = p.get("title", "N/A")
        price_str = p.get("price", "N/A")
        site = p.get("source", "N/A")
        image = p.get("thumbnail", "")
        link = get_direct_link(p)          # ✅ fixed link extraction
        rating = p.get("rating", None)
        reviews = p.get("reviews", None)
        price_val = parse_price(price_str)

        # ✅ Save to database
        if price_val and title != "N/A":
            record = PriceHistory(
                query=query.lower(),
                title=title,
                price=price_val,
                site=site
            )
            db.session.add(record)

        final.append({
            "title": title,
            "price": price_str,
            "site": site,
            "image": image,
            "link": link,
            "rating": rating,
            "reviews": reviews
        })

    db.session.commit()
    return final


@app.route("/search")
def search():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Enter product name"}), 400
    data = get_products(query)
    return jsonify(data)


@app.route("/history")
def history():
    query = request.args.get("q", "").lower()
    title = request.args.get("title", "")

    records = PriceHistory.query \
        .filter(PriceHistory.query == query) \
        .filter(PriceHistory.title == title) \
        .order_by(PriceHistory.date.asc()) \
        .all()

    history_data = []
    for r in records:
        history_data.append({
            "date": r.date.strftime("%d %b %Y %H:%M"),
            "price": r.price,
            "site": r.site
        })

    return jsonify(history_data)


if __name__ == "__main__":
    app.run(debug=True)
