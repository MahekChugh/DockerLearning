from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import hashlib, time, os
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response, RedirectResponse
import logging, json

# ── Structured logging ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ── Prometheus metrics ────────────────────────────────────────────────────────
REQUESTS  = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
LATENCY   = Histogram("http_request_duration_seconds", "Request latency", ["endpoint"])
REDIRECTS = Counter("redirects_total", "Total redirects served")

app = FastAPI(title="URL Shortener", version="1.0.0")

# In-memory store (replace with Redis in production)
db: dict[str, str] = {}

class ShortenRequest(BaseModel):
    url: HttpUrl

class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str

def make_short_code(url: str) -> str:
    return hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:7]

@app.get("/health")
def health():
    logger.info(json.dumps({"event": "health_check", "status": "ok"}))
    REQUESTS.labels("GET", "/health", "200").inc()
    return {"status": "ok", "service": "url-shortener"}

@app.post("/shorten", response_model=ShortenResponse)
def shorten(req: ShortenRequest):
    start = time.time()
    code  = make_short_code(str(req.url))
    db[code] = str(req.url)
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    logger.info(json.dumps({"event": "url_shortened", "code": code, "original": str(req.url)}))
    REQUESTS.labels("POST", "/shorten", "200").inc()
    LATENCY.labels("/shorten").observe(time.time() - start)
    return ShortenResponse(short_code=code, short_url=f"{base_url}/r/{code}", original_url=str(req.url))

@app.get("/r/{code}")
def redirect(code: str):
    if code not in db:
        REQUESTS.labels("GET", "/r/{code}", "404").inc()
        raise HTTPException(status_code=404, detail="Short URL not found")
    REDIRECTS.inc()
    REQUESTS.labels("GET", "/r/{code}", "307").inc()
    logger.info(json.dumps({"event": "redirect", "code": code}))
    return RedirectResponse(url=db[code], status_code=307)

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/urls")
def list_urls():
    return {"count": len(db), "urls": db}
