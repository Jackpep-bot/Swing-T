"""Versioned constants for the live monitor (rule thresholds, code tables, timing). Nothing here is a magic number
elsewhere: every threshold in monitor/ either comes from here or from `settings.monitor`.
"""
from __future__ import annotations

from datetime import time

RULES_VERSION = "2026.10.06"

# ---- priorities ------------------------------------------------------------------------------------------
PRIORITY_RANK: dict[str, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

# ---- dedup -----------------------------------------------------------------------------------------------
DEDUP_WINDOW_MIN = 30
SIMHASH_BITS = 64
SIMHASH_MAX_HAMMING = 3
SIMHASH_SHINGLE = 3

# ---- matcher ---------------------------------------------------------------------------------------------
ALIAS_PROXIMITY_CHARS = 60  # company name must co-occur within this many chars of a word-like ticker
SHORT_TICKER_MAX_LEN = 2  # tickers this short are always treated as word-like
EXCHANGE_QUALIFIERS: tuple[str, ...] = ("NASDAQ", "NYSE", "NYSE AMERICAN", "AMEX", "OTC", "CBOE", "TSX")
# Common English words that are also US tickers; these need a cashtag / exchange qualifier / alias co-occurrence.
WORD_LIKE_TICKERS: frozenset[str] = frozenset(
    {
        "A", "ALL", "ARE", "AT", "BE", "BIG", "BILL", "BIO", "BOX", "CAR", "CARS", "CAT", "COST", "DAY", "DOG",
        "EAT", "EDIT", "FAST", "FIT", "FOR", "FUN", "GAIN", "GO", "GOOD", "HAS", "HE", "HIT", "HOLD", "HOT", "IT",
        "JOB", "KEY", "LIFE", "LOVE", "LOW", "MAIN", "MAN", "MOVE", "NEW", "NICE", "NOW", "ON", "ONE", "OPEN",
        "OUT", "PLAY", "PLUS", "POST", "PRO", "REAL", "RUN", "SAFE", "SEE", "SO", "SUN", "TAP", "TEAM", "TELL",
        "TWO", "UP", "USA", "VERY", "WELL", "WORK", "YOU", "ZIP",
    }
)

# ---- 8-K items (severity tiers). Full list of items the stage-1 rule knows about. ---------------------------
EIGHTK_ITEMS: dict[str, str] = {
    "1.01": "Entry into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "1.03": "Bankruptcy or Receivership",
    "1.04": "Mine Safety",
    "1.05": "Material Cybersecurity Incidents",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.02": "Results of Operations and Financial Condition",
    "2.03": "Creation of a Direct Financial Obligation",
    "2.04": "Triggering Events That Accelerate a Financial Obligation",
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting or Failure to Satisfy a Continued Listing Rule",
    "3.02": "Unregistered Sales of Equity Securities",
    "3.03": "Material Modification to Rights of Security Holders",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": "Non-Reliance on Previously Issued Financial Statements",
    "5.01": "Changes in Control of Registrant",
    "5.02": "Departure/Election of Directors or Officers",
    "5.03": "Amendments to Articles or Bylaws; Change in Fiscal Year",
    "5.04": "Temporary Suspension of Trading Under Employee Benefit Plans",
    "5.05": "Amendments to Code of Ethics",
    "5.06": "Change in Shell Company Status",
    "5.07": "Submission of Matters to a Vote of Security Holders",
    "5.08": "Shareholder Director Nominations",
    "6.01": "ABS Informational and Computational Material",
    "6.02": "Change of Servicer or Trustee",
    "6.03": "Change in Credit Enhancement",
    "6.04": "Failure to Make a Required Distribution",
    "6.05": "Securities Act Updating Disclosure",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}
EIGHTK_SEVERE: frozenset[str] = frozenset({"4.02", "3.01", "1.03"})  # P3 on a held position
EIGHTK_MAJOR: frozenset[str] = frozenset(
    {"1.01", "2.02", "5.02", "8.01", "4.01", "2.04", "2.05", "2.06", "3.02", "1.02", "5.01", "1.05", "2.01"}
)
EIGHTK_MINOR: frozenset[str] = frozenset({"7.01", "9.01", "5.03", "5.07", "3.03", "2.03"})
# Non-8-K forms the stage-1 filing rule cares about, with their base severity.
FILING_FORM_SEVERITY: dict[str, str] = {
    "NT 10-K": "severe",
    "NT 10-Q": "severe",
    "SC 13D": "major",
    "SC 13D/A": "major",
    "144": "minor",
    "S-1": "dilution",
    "S-1/A": "dilution",
    "S-3": "dilution",
    "S-3/A": "dilution",
    "F-1": "dilution",
    "F-3": "dilution",
    "424B1": "dilution",
    "424B2": "dilution",
    "424B3": "dilution",
    "424B4": "dilution",
    "424B5": "dilution",
    "424B7": "dilution",
}
DILUTION_FORM_PREFIXES: tuple[str, ...] = ("S-1", "S-3", "F-1", "F-3", "424B")

# ---- Form 4 ----------------------------------------------------------------------------------------------
FORM4_BUY_CODES: frozenset[str] = frozenset({"P", "A"})
INSIDER_CLUSTER_MIN = 3
INSIDER_CLUSTER_WINDOW_DAYS = 30
INSIDER_CLUSTER_IDENTICAL_REJECT_PCT = 80.0  # reject clusters with >= 80% identical date+price

# ---- halts -----------------------------------------------------------------------------------------------
HALT_NEWS_PENDING = "T1"
HALT_NEWS_RELEASED = "T2"
HALT_INFO_REQUESTED = "T12"
HALT_SEC_SUSPENSION = "H10"
HALT_LULD_PAUSE = "LUDP"
HALT_MARKET_WIDE = "MWC1"
MARKET_WIDE_HALT_CODES: frozenset[str] = frozenset({"MWC1", "MWC2", "MWC3", "MWC0", "M"})
TOXIC_HALT_CODES: frozenset[str] = frozenset({HALT_INFO_REQUESTED, HALT_SEC_SUSPENSION})
NEWS_HALT_CODES: frozenset[str] = frozenset({HALT_NEWS_PENDING, HALT_NEWS_RELEASED})
LULD_CODES: frozenset[str] = frozenset({HALT_LULD_PAUSE, "LUDS"})
# Alpaca `statuses` message status codes (sc), https://docs.alpaca.markets/docs/real-time-stock-pricing-data
# ("Status codes"). Tape C/O (UTP) use letters; Tape A/B (CTA: NYSE, NYSE American, Arca) use digits/letters.
ALPACA_STATUS_HALT = "H"  # UTP trading halt
ALPACA_STATUS_PAUSE = "P"  # UTP volatility trading pause
ALPACA_STATUS_RESUME = "T"  # UTP trading resumption
ALPACA_STATUS_QUOTE_RESUME = "Q"  # UTP quotation resumption
ALPACA_CTA_STATUS_HALT = "2"  # CTA trading halt
ALPACA_CTA_STATUS_RESUME = "3"  # CTA resume
ALPACA_CTA_STATUS_LULD = "F"  # CTA limit up-limit down (treated as a pause)
ALPACA_CTA_STATUS_SSR = "E"  # CTA short sale restriction -> an `ssr` event, never a halt
# CTA 5/6 price/trading-range indications, 7/8/9/A imbalances, C/D no imbalance: not halts, dropped
ALPACA_STATUS_RESUMED_CODES: frozenset[str] = frozenset(
    {ALPACA_STATUS_RESUME, ALPACA_STATUS_QUOTE_RESUME, ALPACA_CTA_STATUS_RESUME}
)
ALPACA_STATUS_PAUSED_CODES: frozenset[str] = frozenset({ALPACA_STATUS_PAUSE, ALPACA_CTA_STATUS_LULD})
ALPACA_STATUS_HALTED_CODES: frozenset[str] = frozenset({ALPACA_STATUS_HALT, ALPACA_CTA_STATUS_HALT})
# the only `status` values a halt event may carry (halt_log, smallcap and the halts rule ignore anything else)
HALT_STATUS_HALTED = "halted"
HALT_STATUS_PAUSED = "paused"
HALT_STATUS_RESUMED = "resumed"
HALT_STATUSES: frozenset[str] = frozenset({HALT_STATUS_HALTED, HALT_STATUS_PAUSED, HALT_STATUS_RESUMED})
HALT_OPENING_STATUSES: frozenset[str] = frozenset({HALT_STATUS_HALTED, HALT_STATUS_PAUSED})

# ---- SSR / index -----------------------------------------------------------------------------------------
SSR_TRIGGER_DROP_PCT = 10.0
INDEX_INCLUSION_PHRASES: tuple[str, ...] = (
    "set to join s&p",
    "to join s&p",
    "to join the s&p",
    "join the s&p 500",
    "added to the s&p",
    "added to s&p",
    "to be added to the s&p",
    "will replace",
    "to replace",
    "join the nasdaq-100",
    "added to the nasdaq-100",
    "join the russell",
    "added to the russell",
    "s&p 500 inclusion",
    "s&p midcap 400",
    "s&p smallcap 600",
)

# ---- RVOL gate / bar triggers ----------------------------------------------------------------------------
RVOL_GATE_DEFAULT = 2.0
RVOL_ESCALATE = 3.0
GAP_PCT_DEFAULT = 8.0
BREAKOUT_VOL_RATIO = 1.5  # 52w / ATH break requires >= 1.5x avg volume
BURST_CLOSE_RATIO = 1.04  # Stockbee: c/c1 >= 1.04
BURST_MIN_VOLUME = 100_000
ADVERSE_MOVE_PCT = 5.0  # >= 5% adverse move on a holding => P3
NEWS_TAG_WINDOW_HOURS = 24
TRIGGER_GAP = "gap"
TRIGGER_BREAKOUT_52W = "breakout_52w"
TRIGGER_BURST = "burst"
TRIGGER_ADVERSE = "adverse_move"
TRIGGER_PEG = "peg"
MINUTES_IN_SESSION = 390
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
PREMARKET_OPEN = time(4, 0)
AFTERHOURS_CLOSE = time(20, 0)
# NYSE / Nasdaq early-close sessions (day after Thanksgiving, Christmas Eve): 13:00 close, extended hours to 17:00.
EARLY_REGULAR_CLOSE = time(13, 0)
EARLY_AFTERHOURS_CLOSE = time(17, 0)
# EDGAR accepts submissions 06:00-22:00 ET on business days; nothing can arrive outside that window.
EDGAR_ACCEPTS_FROM_ET = time(6, 0)
EDGAR_ACCEPTS_UNTIL_ET = time(22, 0)

# ---- alert policy ---------------------------------------------------------------------------------------
DIGEST_TIMES_ET: tuple[time, ...] = (time(8, 30), time(15, 45), time(18, 30))
DEFAULT_ROUTING: dict[str, tuple[str, ...]] = {
    "P3": ("pushover", "telegram", "console"),
    "P2": ("telegram", "console"),
    "P1": ("digest",),
    "P0": (),
}
ALERT_TITLE_MAX = 120
ALERT_BODY_MAX = 900

# ---- classifier -----------------------------------------------------------------------------------------
CLASSIFY_MAX_TOKENS = 400
CLASSIFY_MAX_CONCURRENCY = 5
CLASSIFY_TIMEOUT_S = 20.0
CLASSIFY_INPUT_MAX_CHARS = 6000
SYSTEM_PROMPT_MIN_TOKENS = 4096  # Haiku 4.5 minimum cacheable prefix
SYSTEM_PROMPT_CHARS_PER_TOKEN = 4.5  # assume long tokens so the padded prompt clears the cache minimum for real
RELEVANCE_LEVELS: tuple[str, ...] = ("none", "low", "medium", "high")
SENTIMENTS: tuple[str, ...] = ("negative", "neutral", "positive")
SUGGESTED_ACTIONS: tuple[str, ...] = ("ignore", "watch", "review", "protect_position")
CLASSIFY_UPGRADE_MATERIALITY = 4  # relevance high + materiality >= 4 lifts P1 -> P2

# ---- delivery -------------------------------------------------------------------------------------------
TELEGRAM_API = "https://api.telegram.org"
TELEGRAM_RATE_PER_S = 1.0
TELEGRAM_MAX_RETRIES = 3
TELEGRAM_TEXT_MAX = 4096
#: a 429 `retry_after` longer than this is not waited for inline: the send fails and the next channel runs.
DELIVERY_RETRY_AFTER_MAX_S = 10.0
PUSHOVER_API = "https://api.pushover.net/1/messages.json"
PUSHOVER_PRIORITY: dict[str, int] = {"P3": 2, "P2": 0, "P1": -1, "P0": -2}
PUSHOVER_EMERGENCY_RETRY_S = 30
PUSHOVER_EMERGENCY_EXPIRE_S = 3600
PUSHOVER_MAX_RETRIES = 2  # short: P3 falls through to Telegram concurrently, so do not sit on a dead API
PUSHOVER_BACKOFF_BASE_S = 1.0
HTTP_TOO_MANY = 429
HTTP_FORBIDDEN = 403
HTTP_SERVER_ERROR = 500
NTFY_BASE = "https://ntfy.sh"
NTFY_PRIORITY: dict[str, str] = {"P3": "5", "P2": "3", "P1": "2", "P0": "1"}
HTTP_TIMEOUT_S = 10.0

# ---- feeds ----------------------------------------------------------------------------------------------
ALPACA_NEWS_WS = "wss://stream.data.alpaca.markets/v1beta1/news"
ALPACA_STOCKS_WS_IEX = "wss://stream.data.alpaca.markets/v2/iex"
ALPACA_STOCKS_WS_SIP = "wss://stream.data.alpaca.markets/v2/sip"
ALPACA_ACCOUNT_WS_PAPER = "wss://paper-api.alpaca.markets/stream"
ALPACA_ACCOUNT_WS_LIVE = "wss://api.alpaca.markets/stream"
ALPACA_NEWS_REST = "https://data.alpaca.markets/v1beta1/news"
WS_PING_INTERVAL_S = 20
#: statuses/lulds are silent for most of the day; one liquid symbol's trades make the stocks socket observably
#: alive (any received frame counts as transport liveness for the watchdog).
ALPACA_HEARTBEAT_SYMBOL = "SPY"
EDGAR_CURRENT_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
EDGAR_POLL_INTERVAL_S = 20
EDGAR_RATE_PER_S = 10.0
EDGAR_COUNT = 100
EDGAR_FORBIDDEN_RETRY_S = 600.0  # sec.gov answers 403 for ~10 min once the fair-access limit is tripped
POLL_SEEN_MAX = 5000  # ids a polling feed remembers for dedup before forgetting the oldest
EDGAR_DEFAULT_FORMS: tuple[str, ...] = ("8-K", "4", "SC 13D", "S-3", "424B5", "NT 10-K", "NT 10-Q")
NASDAQ_HALTS_RSS = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
NASDAQ_HALTS_INTERVAL_S = 60
NYSE_HALTS_CSV = "https://www.nyse.com/api/trade-halts/current/download"
NYSE_HALTS_INTERVAL_S = 60
BACKOFF_BASE_S = 1.0
BACKOFF_MAX_S = 60.0
BACKOFF_FACTOR = 2.0
BACKOFF_JITTER = 0.25

# ---- service --------------------------------------------------------------------------------------------
STALENESS_THRESHOLD_S: dict[str, float] = {
    "alpaca_news": 1800.0,
    "alpaca_stocks": 120.0,
    "alpaca_account": 7200.0,
    "edgar": 600.0,
    "nasdaq_halts": 600.0,
    "nyse_halts": 600.0,
    "file": 1e12,
}
STALENESS_DEFAULT_S = 900.0
#: ET window in which silence from a feed is suspicious. Regular-hours feeds are only judged in the `regular`
#: phase (so early closes are honoured); EDGAR only while the SEC accepts filings; the rest in extended hours.
STALENESS_WINDOW_ET: dict[str, tuple[time, time]] = {
    "alpaca_stocks": (REGULAR_OPEN, REGULAR_CLOSE),
    "alpaca_account": (REGULAR_OPEN, REGULAR_CLOSE),
    "edgar": (EDGAR_ACCEPTS_FROM_ET, EDGAR_ACCEPTS_UNTIL_ET),
}
STALENESS_WINDOW_DEFAULT_ET: tuple[time, time] = (PREMARKET_OPEN, AFTERHOURS_CLOSE)
WATCHDOG_INTERVAL_S = 30.0
QUEUE_MAXSIZE = 10_000
SHUTDOWN_GRACE_S = 5.0  # for the consumer to drain the queue (rules only; no network)
SHUTDOWN_DRAIN_S = 30.0  # for in-flight classification / deliveries to finish before they are cancelled
PIPELINE_WORKERS = 8  # concurrent classify+deliver tasks for P0-P2; P3 never waits for a slot
AUDIT_PATH_DEFAULT = "data/alerts.jsonl"
REPLAY_FILE_DEFAULT = "tests/fixtures/monitor/replay_events.jsonl"
