"""
StockRadar India - Backend API v4.0 (FAST)
Key improvements over v3:
 - Background cache warmer pre-loads ALL stocks on startup
 - yfinance download() used for bulk fetching (10x faster than Ticker loop)
 - Self keep-alive ping prevents Render free tier sleep
 - /api/quotes/all returns everything in one shot — no pagination needed
 - Smart refresh: only re-fetches stale data
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import threading
import requests
import time
import os
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("stockradar")

app = Flask(__name__)
CORS(app)

# ─── Config ────────────────────────────────────────────────────────────────────
CACHE_TTL        = 60       # seconds before a quote is considered stale
REFRESH_INTERVAL = 55       # background loop interval (slightly under TTL)
BULK_CHUNK       = 50       # how many symbols to download at once via yf.download
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")
GROQ_URL         = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL       = "llama3-70b-8192"
SELF_URL         = os.environ.get("RENDER_EXTERNAL_URL", "")  # auto-set by Render

# ─── In-memory store ───────────────────────────────────────────────────────────
_quotes   = {}   # symbol → quote dict
_quotes_lock = threading.Lock()
_fund     = {}   # symbol → fundamentals dict  (longer cache)
_fund_lock   = threading.Lock()
_news_cache  = {}
_hist_cache  = {}
_hist_lock   = threading.Lock()
_boot_done   = False   # True once first full load is complete

# ─── Complete Nifty 500 list ───────────────────────────────────────────────────
NIFTY500 = [
    ("RELIANCE","Reliance Industries","Energy"),
    ("TCS","Tata Consultancy Services","IT"),
    ("HDFCBANK","HDFC Bank","Banking"),
    ("BHARTIARTL","Bharti Airtel","Telecom"),
    ("ICICIBANK","ICICI Bank","Banking"),
    ("INFOSYS","Infosys","IT"),
    ("SBIN","State Bank of India","Banking"),
    ("HINDUNILVR","Hindustan Unilever","FMCG"),
    ("ITC","ITC","FMCG"),
    ("LT","Larsen & Toubro","Infrastructure"),
    ("KOTAKBANK","Kotak Mahindra Bank","Banking"),
    ("HCLTECH","HCL Technologies","IT"),
    ("BAJFINANCE","Bajaj Finance","NBFC"),
    ("AXISBANK","Axis Bank","Banking"),
    ("ASIANPAINT","Asian Paints","Chemicals"),
    ("MARUTI","Maruti Suzuki","Auto"),
    ("SUNPHARMA","Sun Pharmaceutical","Pharma"),
    ("TITAN","Titan Company","Consumer"),
    ("NESTLEIND","Nestle India","FMCG"),
    ("WIPRO","Wipro","IT"),
    ("ULTRACEMCO","UltraTech Cement","Cement"),
    ("POWERGRID","Power Grid Corporation","Power"),
    ("NTPC","NTPC","Power"),
    ("ONGC","ONGC","Oil & Gas"),
    ("M&M","Mahindra & Mahindra","Auto"),
    ("TATAMOTORS","Tata Motors","Auto"),
    ("ADANIGREEN","Adani Green Energy","Renewable Energy"),
    ("ADANIPORTS","Adani Ports","Infrastructure"),
    ("BAJAJFINSV","Bajaj Finserv","NBFC"),
    ("JSWSTEEL","JSW Steel","Metal"),
    ("TATASTEEL","Tata Steel","Metal"),
    ("COALINDIA","Coal India","Mining"),
    ("HINDALCO","Hindalco Industries","Metal"),
    ("GRASIM","Grasim Industries","Diversified"),
    ("BRITANNIA","Britannia Industries","FMCG"),
    ("DRREDDY","Dr Reddys Laboratories","Pharma"),
    ("CIPLA","Cipla","Pharma"),
    ("DIVISLAB","Divis Laboratories","Pharma"),
    ("TECHM","Tech Mahindra","IT"),
    ("BPCL","Bharat Petroleum","Oil & Gas"),
    ("INDUSINDBK","IndusInd Bank","Banking"),
    ("SBILIFE","SBI Life Insurance","Insurance"),
    ("HDFCLIFE","HDFC Life Insurance","Insurance"),
    ("BAJAJ-AUTO","Bajaj Auto","Auto"),
    ("EICHERMOT","Eicher Motors","Auto"),
    ("HEROMOTOCO","Hero MotoCorp","Auto"),
    ("APOLLOHOSP","Apollo Hospitals","Healthcare"),
    ("DABUR","Dabur India","FMCG"),
    ("GODREJCP","Godrej Consumer Products","FMCG"),
    ("TATACONSUM","Tata Consumer Products","FMCG"),
    ("UPL","UPL","Chemicals"),
    ("SHREECEM","Shree Cement","Cement"),
    ("DMART","Avenue Supermarts","Retail"),
    ("ICICIPRULI","ICICI Prudential Life","Insurance"),
    ("MARICO","Marico","FMCG"),
    ("PIDILITIND","Pidilite Industries","Chemicals"),
    ("BERGEPAINT","Berger Paints","Chemicals"),
    ("HAVELLS","Havells India","Electricals"),
    ("SIEMENS","Siemens","Capital Goods"),
    ("ABB","ABB India","Capital Goods"),
    ("BOSCHLTD","Bosch","Auto Ancillary"),
    ("MCDOWELL-N","United Spirits","Consumer"),
    ("ADANIENT","Adani Enterprises","Diversified"),
    ("VEDL","Vedanta","Metal"),
    ("BANKBARODA","Bank of Baroda","Banking"),
    ("CANBK","Canara Bank","Banking"),
    ("PNB","Punjab National Bank","Banking"),
    ("UNIONBANK","Union Bank of India","Banking"),
    ("LICHSGFIN","LIC Housing Finance","NBFC"),
    ("CHOLAFIN","Cholamandalam Investment","NBFC"),
    ("MUTHOOTFIN","Muthoot Finance","NBFC"),
    ("SHRIRAMFIN","Shriram Finance","NBFC"),
    ("RECLTD","REC","NBFC"),
    ("PFC","Power Finance Corporation","NBFC"),
    ("IRFC","Indian Railway Finance Corp","NBFC"),
    ("NHPC","NHPC","Power"),
    ("SJVN","SJVN","Power"),
    ("TORNTPOWER","Torrent Power","Power"),
    ("CESC","CESC","Power"),
    ("TATAPOWER","Tata Power","Power"),
    ("JSWENERGY","JSW Energy","Power"),
    ("ADANITRANS","Adani Transmission","Power"),
    ("JINDALSTEL","Jindal Steel & Power","Metal"),
    ("SAIL","Steel Authority of India","Metal"),
    ("NMDC","NMDC","Mining"),
    ("NATIONALUM","National Aluminium","Metal"),
    ("HINDZINC","Hindustan Zinc","Metal"),
    ("APLAPOLLO","APL Apollo Tubes","Metal"),
    ("RATNAMANI","Ratnamani Metals Tubes","Metal"),
    ("GPIL","Godawari Power Ispat","Metal"),
    ("WELCORP","Welspun Corp","Metal"),
    ("JINDALSAW","Jindal Saw","Metal"),
    ("GODREJPROP","Godrej Properties","Real Estate"),
    ("DLF","DLF","Real Estate"),
    ("OBEROIRLTY","Oberoi Realty","Real Estate"),
    ("PHOENIXLTD","Phoenix Mills","Real Estate"),
    ("PRESTIGE","Prestige Estates","Real Estate"),
    ("BRIGADE","Brigade Enterprises","Real Estate"),
    ("SOBHA","Sobha","Real Estate"),
    ("SUNTV","Sun TV Network","Media"),
    ("ZEEL","Zee Entertainment","Media"),
    ("PVRINOX","PVR INOX","Media"),
    ("SAREGAMA","Saregama India","Media"),
    ("NETWORK18","Network18 Media","Media"),
    ("TV18BRDCST","TV18 Broadcast","Media"),
    ("KANSAINER","Kansai Nerolac","Chemicals"),
    ("INDIGOPNTS","Indigo Paints","Chemicals"),
    ("DEEPAKNTR","Deepak Nitrite","Chemicals"),
    ("NAVINFLUOR","Navin Fluorine","Chemicals"),
    ("CLEAN","Clean Science Technology","Chemicals"),
    ("ATUL","Atul","Chemicals"),
    ("VINATIORGA","Vinati Organics","Chemicals"),
    ("TATACHEM","Tata Chemicals","Chemicals"),
    ("GNFC","Gujarat Narmada Fertilizers","Chemicals"),
    ("CHAMBLFERT","Chambal Fertilisers","Chemicals"),
    ("FINEORG","Fine Organic Industries","Chemicals"),
    ("ROSSARI","Rossari Biotech","Chemicals"),
    ("ALKYLAMINE","Alkyl Amines Chemicals","Chemicals"),
    ("ASTRAL","Astral","Plastics"),
    ("SUPREMEIND","Supreme Industries","Plastics"),
    ("FINPIPE","Finolex Industries","Plastics"),
    ("POLYCAB","Polycab India","Electricals"),
    ("CROMPTON","Crompton Greaves Consumer","Electricals"),
    ("VOLTAS","Voltas","Electricals"),
    ("BLUESTARCO","Blue Star","Electricals"),
    ("HAVELLS","Havells India","Electricals"),
    ("FINOLEX","Finolex Cables","Electricals"),
    ("BATAINDIA","Bata India","Consumer"),
    ("RELAXO","Relaxo Footwears","Consumer"),
    ("TRENT","Trent","Retail"),
    ("DMART","Avenue Supermarts","Retail"),
    ("SHOPERSTOP","Shoppers Stop","Retail"),
    ("ABFRL","Aditya Birla Fashion","Retail"),
    ("MANYAVAR","Vedant Fashions","Retail"),
    ("PAGEIND","Page Industries","Textile"),
    ("RAYMOND","Raymond","Textile"),
    ("WELSPUNIND","Welspun India","Textile"),
    ("TRIDENT","Trident","Textile"),
    ("ARVIND","Arvind","Textile"),
    ("KPRMILL","KPR Mill","Textile"),
    ("MOTHERSON","Samvardhana Motherson","Auto Ancillary"),
    ("BALKRISIND","Balkrishna Industries","Auto Ancillary"),
    ("MRF","MRF","Auto Ancillary"),
    ("APOLLOTYRE","Apollo Tyres","Auto Ancillary"),
    ("CEATLTD","CEAT","Auto Ancillary"),
    ("ENDURANCE","Endurance Technologies","Auto Ancillary"),
    ("SUNDRMFAST","Sundram Fasteners","Auto Ancillary"),
    ("SCHAEFFLER","Schaeffler India","Auto Ancillary"),
    ("EXIDEIND","Exide Industries","Auto Ancillary"),
    ("AMARAJABAT","Amara Raja Energy","Auto Ancillary"),
    ("MINDA","Uno Minda","Auto Ancillary"),
    ("CRAFTSMAN","Craftsman Automation","Auto Ancillary"),
    ("SANSERA","Sansera Engineering","Auto Ancillary"),
    ("JKTYRE","JK Tyre","Auto Ancillary"),
    ("SUPRAJIT","Suprajit Engineering","Auto Ancillary"),
    ("LUPIN","Lupin","Pharma"),
    ("TORNTPHARM","Torrent Pharmaceuticals","Pharma"),
    ("BIOCON","Biocon","Pharma"),
    ("AUROPHARMA","Aurobindo Pharma","Pharma"),
    ("IPCALAB","IPCA Laboratories","Pharma"),
    ("GRANULES","Granules India","Pharma"),
    ("ALKEM","Alkem Laboratories","Pharma"),
    ("ABBOTINDIA","Abbott India","Pharma"),
    ("ZYDUSLIFE","Zydus Lifesciences","Pharma"),
    ("JBCHEPHARM","JB Chemicals Pharma","Pharma"),
    ("GLAND","Gland Pharma","Pharma"),
    ("LAURUS","Laurus Labs","Pharma"),
    ("NATCOPHARM","Natco Pharma","Pharma"),
    ("AJANTPHARM","Ajanta Pharma","Pharma"),
    ("STRIDES","Strides Pharma","Pharma"),
    ("ERIS","Eris Lifesciences","Pharma"),
    ("CAPLIPOINT","Caplin Point Laboratories","Pharma"),
    ("METROPOLIS","Metropolis Healthcare","Healthcare"),
    ("LALPATHLAB","Dr Lal PathLabs","Healthcare"),
    ("FORTIS","Fortis Healthcare","Healthcare"),
    ("MAXHEALTH","Max Healthcare","Healthcare"),
    ("APOLLOHOSP","Apollo Hospitals","Healthcare"),
    ("NHLIND","Narayana Hrudayalaya","Healthcare"),
    ("ASTER","Aster DM Healthcare","Healthcare"),
    ("RAINBOW","Rainbow Childrens Medicare","Healthcare"),
    ("THYROCARE","Thyrocare Technologies","Healthcare"),
    ("AAVAS","Aavas Financiers","NBFC"),
    ("HOMEFIRST","Home First Finance","NBFC"),
    ("APTUS","Aptus Value Housing","NBFC"),
    ("MANAPPURAM","Manappuram Finance","NBFC"),
    ("SPANDANA","Spandana Sphoorty Financial","NBFC"),
    ("CREDITACC","CreditAccess Grameen","NBFC"),
    ("SBFC","SBFC Finance","NBFC"),
    ("IIFL","IIFL Finance","NBFC"),
    ("AUBANK","AU Small Finance Bank","Banking"),
    ("EQUITASBNK","Equitas Small Finance Bank","Banking"),
    ("UJJIVANSFB","Ujjivan Small Finance Bank","Banking"),
    ("BANDHANBNK","Bandhan Bank","Banking"),
    ("IDFCFIRSTB","IDFC First Bank","Banking"),
    ("FEDERALBNK","Federal Bank","Banking"),
    ("RBLBANK","RBL Bank","Banking"),
    ("KARURVYSYA","Karur Vysya Bank","Banking"),
    ("CSBBANK","CSB Bank","Banking"),
    ("DCBBANK","DCB Bank","Banking"),
    ("IDBI","IDBI Bank","Banking"),
    ("KPITTECH","KPIT Technologies","IT"),
    ("PERSISTENT","Persistent Systems","IT"),
    ("COFORGE","Coforge","IT"),
    ("MPHASIS","Mphasis","IT"),
    ("LTTS","L&T Technology Services","IT"),
    ("LTIM","LTIMindtree","IT"),
    ("OFSS","Oracle Financial Services","IT"),
    ("TATAELXSI","Tata Elxsi","IT"),
    ("INTELLECT","Intellect Design Arena","IT"),
    ("TANLA","Tanla Platforms","IT"),
    ("ROUTE","Route Mobile","IT"),
    ("NEWGEN","Newgen Software Technologies","IT"),
    ("MASTEK","Mastek","IT"),
    ("CYIENT","Cyient","IT"),
    ("ZENSAR","Zensar Technologies","IT"),
    ("BIRLASOFT","Birlasoft","IT"),
    ("SONATSOFTW","Sonata Software","IT"),
    ("ZOMATO","Zomato","Consumer Tech"),
    ("NYKAA","FSN E-Commerce Nykaa","Consumer Tech"),
    ("PAYTM","One 97 Communications Paytm","Fintech"),
    ("POLICYBZR","PB Fintech PolicyBazaar","Fintech"),
    ("DELHIVERY","Delhivery","Logistics"),
    ("INDIAMART","IndiaMART InterMESH","Consumer Tech"),
    ("NAUKRI","Info Edge India","Consumer Tech"),
    ("JUSTDIAL","Just Dial","Consumer Tech"),
    ("AFFLE","Affle India","Consumer Tech"),
    ("RATEGAIN","RateGain Travel Technologies","Consumer Tech"),
    ("MAPMYINDIA","C E Info Systems MapmyIndia","Consumer Tech"),
    ("CARTRADE","CarTrade Tech","Consumer Tech"),
    ("EASEMYTRIP","Easy Trip Planners","Travel"),
    ("IRCTC","IRCTC","Travel"),
    ("INDIGO","IndiGo Airlines","Aviation"),
    ("SPICEJET","SpiceJet","Aviation"),
    ("CONCOR","Container Corporation","Logistics"),
    ("BLUEDART","Blue Dart Express","Logistics"),
    ("ALLCARGO","Allcargo Logistics","Logistics"),
    ("TCI","Transport Corp India","Logistics"),
    ("GATI","GATI","Logistics"),
    ("MAHLOG","Mahindra Logistics","Logistics"),
    ("HINDPETRO","Hindustan Petroleum","Oil & Gas"),
    ("IOC","Indian Oil Corporation","Oil & Gas"),
    ("GAIL","GAIL India","Oil & Gas"),
    ("OIL","Oil India","Oil & Gas"),
    ("MGL","Mahanagar Gas","Oil & Gas"),
    ("IGL","Indraprastha Gas","Oil & Gas"),
    ("GUJGASLTD","Gujarat Gas","Oil & Gas"),
    ("PETRONET","Petronet LNG","Oil & Gas"),
    ("MRPL","Mangalore Refinery","Oil & Gas"),
    ("COROMANDEL","Coromandel International","Agri"),
    ("PIIND","PI Industries","Agri"),
    ("RALLIS","Rallis India","Agri"),
    ("KSCL","Kaveri Seed Company","Agri"),
    ("BAYER","Bayer CropScience","Agri"),
    ("SUMICHEM","Sumitomo Chemical India","Agri"),
    ("HERANBA","Heranba Industries","Agri"),
    ("SHARDACROP","Sharda Cropchem","Agri"),
    ("JKCEMENT","JK Cement","Cement"),
    ("RAMCOCEM","Ramco Cements","Cement"),
    ("DALMIABJR","Dalmia Bharat","Cement"),
    ("BIRLACORPN","Birla Corporation","Cement"),
    ("HEIDELBERG","HeidelbergCement India","Cement"),
    ("STARCEMENT","Star Cement","Cement"),
    ("NUVOCO","Nuvoco Vistas","Cement"),
    ("JKLAKSHMI","JK Lakshmi Cement","Cement"),
    ("KAJARIACER","Kajaria Ceramics","Building Materials"),
    ("CERA","Cera Sanitaryware","Building Materials"),
    ("CUMMINSIND","Cummins India","Capital Goods"),
    ("BHEL","Bharat Heavy Electricals","Capital Goods"),
    ("SIEMENS","Siemens","Capital Goods"),
    ("ABB","ABB India","Capital Goods"),
    ("THERMAX","Thermax","Capital Goods"),
    ("ELGIEQUIP","Elgi Equipments","Capital Goods"),
    ("JYOTICNC","Jyoti CNC Automation","Capital Goods"),
    ("AIAENG","AIA Engineering","Capital Goods"),
    ("CARBORUNIV","Carborundum Universal","Capital Goods"),
    ("PRAJIND","Praj Industries","Capital Goods"),
    ("BEL","Bharat Electronics","Defence"),
    ("HAL","Hindustan Aeronautics","Defence"),
    ("MAZAGON","Mazagon Dock Shipbuilders","Defence"),
    ("COCHINSHIP","Cochin Shipyard","Defence"),
    ("GMRINFRA","GMR Airports Infrastructure","Infrastructure"),
    ("IRB","IRB Infrastructure","Infrastructure"),
    ("KNRCON","KNR Constructions","Infrastructure"),
    ("PNCINFRA","PNC Infratech","Infrastructure"),
    ("NCC","NCC","Infrastructure"),
    ("HGINFRA","H G Infra Engineering","Infrastructure"),
    ("LICI","Life Insurance Corporation","Insurance"),
    ("GICRE","General Insurance Corporation","Insurance"),
    ("NIACL","New India Assurance","Insurance"),
    ("STARHEALTH","Star Health Insurance","Insurance"),
    ("GODIGIT","Go Digit General Insurance","Insurance"),
    ("MFSL","Max Financial Services","Insurance"),
    ("HDFCAMC","HDFC AMC","Asset Management"),
    ("NAM-INDIA","Nippon Life India AMC","Asset Management"),
    ("UTIAMC","UTI AMC","Asset Management"),
    ("ABSLAMC","Aditya Birla Sun Life AMC","Asset Management"),
    ("360ONE","360 ONE WAM","Wealth Management"),
    ("ANGELONE","Angel One","Broking"),
    ("MOTILALOFS","Motilal Oswal Financial","Broking"),
    ("CDSL","CDSL","Financial Services"),
    ("BSE","BSE","Financial Services"),
    ("MCX","Multi Commodity Exchange","Financial Services"),
    ("CAMS","Computer Age Management","Financial Services"),
    ("KFINTECH","KFin Technologies","Financial Services"),
    ("TATAINVEST","Tata Investment Corp","Financial Services"),
    ("ABCAPITAL","Aditya Birla Capital","Financial Services"),
    ("PIRAMALENT","Piramal Enterprises","Diversified"),
    ("BAJAJHLDNG","Bajaj Holdings Investment","Diversified"),
    ("GODREJIND","Godrej Industries","Diversified"),
    ("JSWHLDING","JSW Holdings","Diversified"),
    ("DCMSHRIRAM","DCM Shriram","Diversified"),
    ("KESORAMIND","Kesoram Industries","Diversified"),
    ("VBL","Varun Beverages","Beverages"),
    ("RADICO","Radico Khaitan","Beverages"),
    ("GLOBUSSPI","Globus Spirits","Beverages"),
    ("JUBLFOOD","Jubilant FoodWorks","QSR"),
    ("DEVYANI","Devyani International","QSR"),
    ("WESTLIFE","Westlife Foodworld","QSR"),
    ("SAPPHIRE","Sapphire Foods","QSR"),
    ("COLPAL","Colgate-Palmolive India","FMCG"),
    ("EMAMILTD","Emami","FMCG"),
    ("JYOTHYLAB","Jyothy Labs","FMCG"),
    ("PGHH","Procter Gamble Hygiene","FMCG"),
    ("BIKAJI","Bikaji Foods","FMCG"),
    ("BAJAJCON","Bajaj Consumer Care","FMCG"),
    ("MARICO","Marico","FMCG"),
    ("HFCL","HFCL","Telecom"),
    ("TATACOMM","Tata Communications","Telecom"),
    ("RAILTEL","RailTel Corporation","Telecom"),
    ("KALYANKJIL","Kalyan Jewellers","Jewellery"),
    ("RAJESHEXPO","Rajesh Exports","Jewellery"),
    ("SENCO","Senco Gold","Jewellery"),
    ("THANGAMEDL","Thangamayil Jewellery","Jewellery"),
    ("INDHOTEL","Indian Hotels Taj","Hotels"),
    ("LEMONTREE","Lemon Tree Hotels","Hotels"),
    ("TVSMOTORS","TVS Motor Company","Auto"),
    ("ESCORTS","Escorts Kubota","Auto"),
    ("FORCEMOT","Force Motors","Auto"),
    ("HYUNDAI","Hyundai Motor India","Auto"),
    ("KAYNES","Kaynes Technology","Electronics"),
    ("DIXON","Dixon Technologies","Electronics"),
    ("AMBER","Amber Enterprises","Electronics"),
    ("SYRMA","Syrma SGS Technology","Electronics"),
    ("NAZARA","Nazara Technologies","Gaming"),
    ("JAGRAN","Jagran Prakashan","Media"),
    ("TVTODAY","TV Today Network","Media"),
    ("TIPSINDLTD","Tips Industries","Media"),
    ("SARDAEN","Sarda Energy Minerals","Metal"),
    ("SHYAMMET","Shyam Metalics","Metal"),
    ("JKPAPER","JK Paper","Paper"),
    ("TNPL","Tamil Nadu Newsprint","Paper"),
    ("QUESS","Quess Corp","HR Services"),
    ("TEAMLEASE","TeamLease Services","HR Services"),
    ("GESHIP","Great Eastern Shipping","Shipping"),
    ("GPPL","Gujarat Pipavav Port","Ports"),
    ("VSTIND","VST Industries","Tobacco"),
    ("IXIGO","Le Travenues ixigo","Consumer Tech"),
    ("SAGILITY","Sagility India","Healthcare IT"),
    ("GRINDWELL","Grindwell Norton","Industrial"),
]

# Remove duplicates
_seen_s = set()
_uniq = []
for _s in NIFTY500:
    if _s[0] not in _seen_s:
        _seen_s.add(_s[0])
        _uniq.append(_s)
NIFTY500 = _uniq

SYMBOL_META = {s[0]: {"name": s[1], "sector": s[2]} for s in NIFTY500}
ALL_SYMBOLS  = [s[0] for s in NIFTY500]

_YF_MAP = {
    "M&M":        "M&M.NS",
    "BAJAJ-AUTO": "BAJAJ-AUTO.NS",
    "MCDOWELL-N": "MCDOWELL-N.NS",
    "GUJGASLTD":  "GUJGAS.NS",
    "NAM-INDIA":  "NAM-INDIA.NS",
    "360ONE":     "360ONE.NS",
}

def yf_sym(s):
    return _YF_MAP.get(s, f"{s}.NS")

def ns_sym(yfs):
    """Reverse map: RELIANCE.NS → RELIANCE"""
    base = yfs.replace(".NS","").replace(".BO","")
    return base

# ─── BULK QUOTE FETCHER (the fast way) ─────────────────────────────────────────
def fetch_bulk_quotes(symbols):
    """
    Use yf.download() to fetch OHLCV for a list of symbols in ONE network call.
    Much faster than calling Ticker() for each symbol individually.
    Returns dict: symbol → quote
    """
    yf_syms = [yf_sym(s) for s in symbols]
    results  = {}
    try:
        # Download last 5 days so we can compute prev_close
        df = yf.download(
            tickers   = " ".join(yf_syms),
            period    = "5d",
            interval  = "1d",
            group_by  = "ticker",
            auto_adjust = True,
            progress  = False,
            threads   = True,
        )
        if df.empty:
            return results

        for orig_sym, yfs in zip(symbols, yf_syms):
            try:
                # Handle single vs multi-ticker dataframe structure
                if len(yf_syms) == 1:
                    sub = df
                else:
                    if yfs not in df.columns.get_level_values(0):
                        continue
                    sub = df[yfs]

                sub = sub.dropna(subset=["Close"])
                if sub.empty:
                    continue

                close_today = float(sub["Close"].iloc[-1])
                close_prev  = float(sub["Close"].iloc[-2]) if len(sub) >= 2 else close_today
                open_p      = float(sub["Open"].iloc[-1])
                high_p      = float(sub["High"].iloc[-1])
                low_p       = float(sub["Low"].iloc[-1])
                vol         = int(sub["Volume"].iloc[-1])
                change      = close_today - close_prev
                change_pct  = (change / close_prev * 100) if close_prev else 0

                results[orig_sym] = {
                    "symbol":     orig_sym,
                    "name":       SYMBOL_META.get(orig_sym, {}).get("name", orig_sym),
                    "sector":     SYMBOL_META.get(orig_sym, {}).get("sector", ""),
                    "price":      round(close_today, 2),
                    "prevClose":  round(close_prev,  2),
                    "change":     round(change,      2),
                    "changePct":  round(change_pct,  2),
                    "open":       round(open_p,  2),
                    "high":       round(high_p,  2),
                    "low":        round(low_p,   2),
                    "volume":     vol,
                    "marketCap":  0,   # filled by fundamentals later
                    "week52High": 0,
                    "week52Low":  0,
                    "pe":         0,
                    "ok":         True,
                    "ts":         time.time(),
                }
            except Exception as e:
                log.debug(f"parse error {orig_sym}: {e}")
    except Exception as e:
        log.warning(f"bulk download error: {e}")

    return results


def fetch_fast_info(symbols):
    """
    Fetch market cap, 52w high/low, P/E via fast_info for a list of symbols.
    Run in threads for speed.
    """
    out = {}
    lock = threading.Lock()

    def worker(sym):
        try:
            t = yf.Ticker(yf_sym(sym))
            fi = t.fast_info
            info = {}
            try: info["marketCap"]  = float(fi.market_cap or 0)
            except: info["marketCap"] = 0
            try: info["week52High"] = round(float(fi.year_high or 0), 2)
            except: info["week52High"] = 0
            try: info["week52Low"]  = round(float(fi.year_low  or 0), 2)
            except: info["week52Low"] = 0
            with lock:
                out[sym] = info
        except Exception as e:
            log.debug(f"fast_info {sym}: {e}")

    threads = [threading.Thread(target=worker, args=(s,)) for s in symbols]
    for t in threads: t.start()
    for t in threads: t.join(timeout=10)
    return out


# ─── BACKGROUND CACHE WARMER ────────────────────────────────────────────────────
def warm_cache():
    """
    Runs once on startup, then every REFRESH_INTERVAL seconds.
    Fetches all stocks in bulk chunks, stores in _quotes.
    """
    global _boot_done
    log.info(f"Cache warmer starting — {len(ALL_SYMBOLS)} symbols")

    # Process in chunks of BULK_CHUNK
    chunks = [ALL_SYMBOLS[i:i+BULK_CHUNK] for i in range(0, len(ALL_SYMBOLS), BULK_CHUNK)]

    for i, chunk in enumerate(chunks):
        try:
            log.info(f"  Fetching chunk {i+1}/{len(chunks)} ({len(chunk)} stocks)...")
            quotes = fetch_bulk_quotes(chunk)
            with _quotes_lock:
                _quotes.update(quotes)
            log.info(f"  → Got {len(quotes)} quotes (total cached: {len(_quotes)})")
        except Exception as e:
            log.warning(f"  Chunk {i+1} failed: {e}")
        time.sleep(1)  # small pause between chunks to avoid rate limiting

    _boot_done = True
    log.info(f"✅ Initial cache warm complete — {len(_quotes)} stocks loaded")

    # Now enrich with fast_info (market cap, 52w) in background
    threading.Thread(target=enrich_fast_info, daemon=True).start()


def enrich_fast_info():
    """Adds market cap and 52W data to cached quotes — runs after initial load"""
    log.info("Enriching with fast_info (market cap, 52W)...")
    # Process in chunks of 20 (fast_info is per-ticker, use threads)
    chunk_size = 20
    for i in range(0, len(ALL_SYMBOLS), chunk_size):
        chunk = ALL_SYMBOLS[i:i+chunk_size]
        fi_data = fetch_fast_info(chunk)
        with _quotes_lock:
            for sym, fi in fi_data.items():
                if sym in _quotes:
                    _quotes[sym].update(fi)
        time.sleep(0.5)
    log.info("✅ fast_info enrichment complete")


def refresh_loop():
    """Runs forever — refreshes all quotes every REFRESH_INTERVAL seconds"""
    while True:
        time.sleep(REFRESH_INTERVAL)
        log.info("Refreshing all quotes...")
        warm_cache()


def keep_alive_loop():
    """Pings self every 14 minutes to prevent Render free tier sleep"""
    if not SELF_URL:
        log.info("RENDER_EXTERNAL_URL not set — keep-alive disabled")
        return
    ping_url = SELF_URL.rstrip("/") + "/api/health"
    log.info(f"Keep-alive pinging {ping_url} every 14 min")
    while True:
        time.sleep(14 * 60)
        try:
            requests.get(ping_url, timeout=10)
            log.info("Keep-alive ping sent")
        except:
            pass


# ─── ROUTES ────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return jsonify({
        "status":      "StockRadar India API v4.0",
        "stocks":      len(NIFTY500),
        "cached":      len(_quotes),
        "boot_done":   _boot_done,
        "ai_enabled":  bool(GROQ_API_KEY),
    })


@app.route("/api/health")
def health():
    return jsonify({
        "status":    "ok",
        "stocks":    len(NIFTY500),
        "cached":    len(_quotes),
        "boot_done": _boot_done,
        "ai_enabled": bool(GROQ_API_KEY),
        "ts":        time.time(),
    })


@app.route("/api/stocks")
def get_stocks():
    return jsonify([
        {"symbol": s[0], "name": s[1], "sector": s[2]}
        for s in NIFTY500
    ])


@app.route("/api/quotes/all")
def get_all_quotes():
    """
    Returns ALL cached quotes in one shot.
    Frontend calls this once on load — no pagination, no batching needed.
    """
    with _quotes_lock:
        data = dict(_quotes)
    return jsonify({
        "quotes":    list(data.values()),
        "count":     len(data),
        "boot_done": _boot_done,
        "ok":        True,
    })


@app.route("/api/quote/<symbol>")
def get_quote(symbol):
    sym = symbol.upper()
    with _quotes_lock:
        cached = _quotes.get(sym)

    # Return cached if fresh
    if cached and time.time() - cached.get("ts", 0) < CACHE_TTL:
        return jsonify(cached)

    # Else fetch fresh
    try:
        result = fetch_bulk_quotes([sym])
        if sym in result:
            with _quotes_lock:
                _quotes[sym] = result[sym]
            return jsonify(result[sym])
        return jsonify({"symbol": sym, "ok": False, "error": "No data"})
    except Exception as e:
        return jsonify({"symbol": sym, "ok": False, "error": str(e)})


@app.route("/api/quotes/batch")
def get_quotes_batch():
    symbols = [s.strip().upper() for s in request.args.get("symbols","").split(",") if s.strip()][:50]
    if not symbols:
        return jsonify({})

    result = {}
    missing = []

    with _quotes_lock:
        for sym in symbols:
            if sym in _quotes and time.time() - _quotes[sym].get("ts", 0) < CACHE_TTL:
                result[sym] = _quotes[sym]
            else:
                missing.append(sym)

    if missing:
        fresh = fetch_bulk_quotes(missing)
        with _quotes_lock:
            _quotes.update(fresh)
        result.update(fresh)

    return jsonify(result)


@app.route("/api/indices")
def get_indices():
    idx_map = {
        "NIFTY50":      "^NSEI",
        "SENSEX":       "^BSESN",
        "BANKNIFTY":    "^NSEBANK",
        "NIFTYIT":      "^CNXIT",
        "NIFTYMIDCAP":  "^CNXMIDCAP",
        "NIFTYSMALLCAP":"^CNXSC",
    }
    cache_key = "indices"
    with _hist_lock:
        if cache_key in _hist_cache and time.time() - _hist_cache[cache_key]["ts"] < 60:
            return jsonify(_hist_cache[cache_key]["data"])

    result = {}
    for name, ticker_sym in idx_map.items():
        try:
            t = yf.Ticker(ticker_sym)
            fi = t.fast_info
            price = float(getattr(fi, "last_price",  None) or 0)
            prev  = float(getattr(fi, "previous_close", None) or price)
            chg   = price - prev
            pct   = (chg / prev * 100) if prev else 0
            result[name] = {"price": round(price,2), "change": round(chg,2), "changePct": round(pct,2), "ok": True}
        except:
            result[name] = {"price": 0, "change": 0, "changePct": 0, "ok": False}

    with _hist_lock:
        _hist_cache[cache_key] = {"data": result, "ts": time.time()}

    return jsonify(result)


@app.route("/api/fundamentals/<symbol>")
def get_fundamentals(symbol):
    sym = symbol.upper()
    with _fund_lock:
        cached = _fund.get(sym)
    if cached and time.time() - cached.get("_ts", 0) < 300:
        return jsonify(cached)

    try:
        info = yf.Ticker(yf_sym(sym)).info
        data = {
            "symbol":               sym,
            "pe":                   round(float(info.get("trailingPE")            or 0), 2),
            "forwardPE":            round(float(info.get("forwardPE")             or 0), 2),
            "pb":                   round(float(info.get("priceToBook")           or 0), 2),
            "eps":                  round(float(info.get("trailingEps")           or 0), 2),
            "roe":                  round(float(info.get("returnOnEquity")        or 0)*100, 2),
            "roa":                  round(float(info.get("returnOnAssets")        or 0)*100, 2),
            "debtToEquity":         round(float(info.get("debtToEquity")          or 0), 2),
            "dividendYield":        round(float(info.get("dividendYield")         or 0)*100, 2),
            "payoutRatio":          round(float(info.get("payoutRatio")           or 0)*100, 2),
            "grossMargins":         round(float(info.get("grossMargins")          or 0)*100, 2),
            "operatingMargins":     round(float(info.get("operatingMargins")      or 0)*100, 2),
            "profitMargins":        round(float(info.get("profitMargins")         or 0)*100, 2),
            "currentRatio":         round(float(info.get("currentRatio")          or 0), 2),
            "quickRatio":           round(float(info.get("quickRatio")            or 0), 2),
            "beta":                 round(float(info.get("beta")                  or 1), 2),
            "heldPercentInsiders":  round(float(info.get("heldPercentInsiders")   or 0)*100, 2),
            "heldPercentInstitutions": round(float(info.get("heldPercentInstitutions") or 0)*100, 2),
            "week52High":           float(info.get("fiftyTwoWeekHigh")  or 0),
            "week52Low":            float(info.get("fiftyTwoWeekLow")   or 0),
            "ma50":                 float(info.get("fiftyDayAverage")   or 0),
            "ma200":                float(info.get("twoHundredDayAverage") or 0),
            "enterpriseValue":      float(info.get("enterpriseValue")   or 0),
            "evToRevenue":          round(float(info.get("enterpriseToRevenue")  or 0), 2),
            "evToEbitda":           round(float(info.get("enterpriseToEbitda")   or 0), 2),
            "pegRatio":             round(float(info.get("pegRatio")             or 0), 2),
            "revenueGrowth":        round(float(info.get("revenueGrowth")        or 0)*100, 2),
            "earningsGrowth":       round(float(info.get("earningsGrowth")       or 0)*100, 2),
            "marketCap":            float(info.get("marketCap")         or 0),
            "revenue":              float(info.get("totalRevenue")      or 0),
            "netIncome":            float(info.get("netIncomeToCommon") or 0),
            "bookValue":            round(float(info.get("bookValue")   or 0), 2),
            "longName":             info.get("longName") or sym,
            "sector":               info.get("sector")   or "",
            "industry":             info.get("industry") or "",
            "website":              info.get("website")  or "",
            "description":          info.get("longBusinessSummary") or "",
            "employees":            int(info.get("fullTimeEmployees") or 0),
            "ok":  True,
            "_ts": time.time(),
        }
        with _fund_lock:
            _fund[sym] = data
        # Also update market cap in quotes
        with _quotes_lock:
            if sym in _quotes:
                _quotes[sym]["marketCap"]  = data["marketCap"]
                _quotes[sym]["week52High"] = data["week52High"]
                _quotes[sym]["week52Low"]  = data["week52Low"]
                _quotes[sym]["pe"]         = data["pe"]
        return jsonify(data)
    except Exception as e:
        return jsonify({"symbol": sym, "ok": False, "error": str(e)})


@app.route("/api/history/<symbol>")
def get_history(symbol):
    sym      = symbol.upper()
    period   = request.args.get("period",   "1y")
    interval = request.args.get("interval", "1d")

    valid_p = ["1d","5d","1mo","3mo","6mo","1y","2y","5y","ytd","max"]
    valid_i = ["1m","5m","15m","30m","1h","1d","1wk","1mo"]
    if period not in valid_p:   period   = "1y"
    if interval not in valid_i: interval = "1d"

    cache_key = f"hist_{sym}_{period}_{interval}"
    ttl = 60 if interval in ["1m","5m","15m"] else 300
    with _hist_lock:
        if cache_key in _hist_cache and time.time() - _hist_cache[cache_key]["ts"] < ttl:
            return jsonify(_hist_cache[cache_key]["data"])

    try:
        hist = yf.Ticker(yf_sym(sym)).history(period=period, interval=interval)
        rows = []
        for idx, row in hist.iterrows():
            rows.append({
                "date":   idx.strftime("%Y-%m-%d %H:%M"),
                "open":   round(float(row["Open"]),   2),
                "high":   round(float(row["High"]),   2),
                "low":    round(float(row["Low"]),    2),
                "close":  round(float(row["Close"]),  2),
                "volume": int(row["Volume"]),
            })
        data = {"symbol": sym, "data": rows, "ok": True}
        with _hist_lock:
            _hist_cache[cache_key] = {"data": data, "ts": time.time()}
        return jsonify(data)
    except Exception as e:
        return jsonify({"symbol": sym, "ok": False, "error": str(e), "data": []})


@app.route("/api/financials/<symbol>")
def get_financials(symbol):
    sym = symbol.upper()
    cache_key = f"fin_{sym}"
    with _hist_lock:
        if cache_key in _hist_cache and time.time() - _hist_cache[cache_key]["ts"] < 3600:
            return jsonify(_hist_cache[cache_key]["data"])

    try:
        t  = yf.Ticker(yf_sym(sym))
        quarterly, annual, bs_data = [], [], []

        qf = t.quarterly_financials
        if qf is not None and not qf.empty:
            for col in qf.columns[:8]:
                q = {"period": str(col)[:10]}
                for m in ["Total Revenue","Net Income","Operating Income","Gross Profit","EBITDA"]:
                    if m in qf.index:
                        try: q[m.replace(" ","_").lower()] = float(qf[col].get(m) or 0)
                        except: q[m.replace(" ","_").lower()] = None
                quarterly.append(q)

        af = t.financials
        if af is not None and not af.empty:
            for col in af.columns[:5]:
                a = {"period": str(col)[:10]}
                for m in ["Total Revenue","Net Income","Operating Income","Gross Profit"]:
                    if m in af.index:
                        try: a[m.replace(" ","_").lower()] = float(af[col].get(m) or 0)
                        except: a[m.replace(" ","_").lower()] = None
                annual.append(a)

        data = {"symbol": sym, "quarterly": quarterly, "annual": annual, "balanceSheet": bs_data, "ok": True}
        with _hist_lock:
            _hist_cache[cache_key] = {"data": data, "ts": time.time()}
        return jsonify(data)
    except Exception as e:
        return jsonify({"symbol": sym, "ok": False, "error": str(e), "quarterly": [], "annual": []})


@app.route("/api/news/<symbol>")
def get_news(symbol):
    sym = symbol.upper()
    cache_key = f"news_{sym}"
    if cache_key in _news_cache and time.time() - _news_cache[cache_key]["ts"] < 600:
        return jsonify(_news_cache[cache_key]["data"])
    try:
        news = yf.Ticker(yf_sym(sym)).news or []
        items = []
        for n in news[:15]:
            c = n.get("content", {})
            items.append({
                "title":     c.get("title","")     or n.get("title",""),
                "link":      (c.get("canonicalUrl",{}) or {}).get("url","") or n.get("link",""),
                "publisher": (c.get("provider",{})     or {}).get("displayName","") or n.get("publisher",""),
                "published": c.get("pubDate","")   or str(n.get("providerPublishTime","")),
                "summary":   c.get("summary","")   or n.get("summary",""),
            })
        data = {"symbol": sym, "news": items, "ok": True}
        _news_cache[cache_key] = {"data": data, "ts": time.time()}
        return jsonify(data)
    except Exception as e:
        return jsonify({"symbol": sym, "ok": False, "error": str(e), "news": []})


@app.route("/api/market-news")
def get_market_news():
    if "mkt_news" in _news_cache and time.time() - _news_cache["mkt_news"]["ts"] < 600:
        return jsonify(_news_cache["mkt_news"]["data"])
    try:
        news = yf.Ticker("^NSEI").news or []
        items = []
        for n in news[:20]:
            c = n.get("content", {})
            items.append({
                "title":     c.get("title","")     or n.get("title",""),
                "link":      (c.get("canonicalUrl",{}) or {}).get("url","") or n.get("link",""),
                "publisher": (c.get("provider",{})     or {}).get("displayName","") or n.get("publisher",""),
                "published": c.get("pubDate","")   or str(n.get("providerPublishTime","")),
            })
        data = {"news": items, "ok": True}
        _news_cache["mkt_news"] = {"data": data, "ts": time.time()}
        return jsonify(data)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "news": []})


# ─── FREE AI ────────────────────────────────────────────────────────────────────
def call_groq(messages, system="", max_tokens=1500):
    if not GROQ_API_KEY:
        return None
    try:
        payload = {"model": GROQ_MODEL, "max_tokens": max_tokens, "messages": []}
        if system:
            payload["messages"].append({"role": "system", "content": system})
        payload["messages"].extend(messages)
        r = requests.post(GROQ_URL, json=payload,
                          headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                                   "Content-Type": "application/json"},
                          timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log.warning(f"Groq error: {e}")
        return None


def rule_based_analysis(d):
    pe = d.get("pe", 0); roe = d.get("roe", 0); rsi = d.get("rsi", 50)
    pct = d.get("changePct", 0); debt = d.get("debtToEquity", 0)
    npm = d.get("profitMargins", 0); rg = d.get("revenueGrowth", 0)
    bull, bear = [], []
    if roe > 20:  bull.append(f"Strong ROE of {roe:.1f}% shows efficient capital use")
    if pe > 0 and pe < 20: bull.append(f"Attractive P/E of {pe:.1f}x — reasonable valuation")
    if rsi < 40:  bull.append(f"RSI at {rsi:.0f} — oversold, potential reversal candidate")
    if npm > 15:  bull.append(f"Healthy net margin of {npm:.1f}%")
    if rg  > 10:  bull.append(f"Strong revenue growth of {rg:.1f}%")
    if pe > 60 and pe > 0: bear.append(f"Stretched P/E of {pe:.1f}x — limited margin of safety")
    if debt > 1.5: bear.append(f"High debt/equity of {debt:.1f}x — leverage risk")
    if rsi > 70:  bear.append(f"RSI at {rsi:.0f} — overbought, watch for pullback")
    if rg  < 0:   bear.append(f"Negative revenue growth of {rg:.1f}%")
    verdict = "STRONG BUY" if len(bull)>=4 and len(bear)<=1 else "BUY" if len(bull)>=3 else "SELL" if len(bear)>=3 else "HOLD"
    return f"""VERDICT: {verdict}

BULL CASE:
{chr(10).join("• "+b for b in bull) or "• Limited bullish signals from available data"}

BEAR CASE:
{chr(10).join("• "+b for b in bear) or "• No major red flags from available data"}

VALUATION ASSESSMENT:
• {"Stock looks attractively valued" if pe > 0 and pe < 20 else "Premium valuation — needs strong growth to justify" if pe > 40 else "Fair valuation relative to Indian market averages"}

NOTE: Connect GROQ_API_KEY on backend for full AI-powered reports (free at console.groq.com)"""


@app.route("/api/ai/analyze", methods=["POST"])
def ai_analyze():
    d = request.get_json() or {}
    sym  = d.get("symbol", "")
    data = d.get("stockData", {})
    if not sym:
        return jsonify({"ok": False, "error": "Symbol required"})

    system = """You are a senior Indian equity research analyst (CFA Level 3) with 20 years on NSE/BSE.
You write institutional-quality research for retail investors.
Use Indian context: SEBI, RBI policy, FII/DII flows, sector tailwinds.
Use ₹ for prices and Cr for crores. Be data-driven and concise."""

    prompt = f"""Analyze {data.get('name', sym)} ({sym}.NS) | Sector: {data.get('sector','N/A')}

PRICE: ₹{data.get('price',0):,.2f} | Change: {data.get('changePct',0):+.2f}%
52W: ₹{data.get('week52Low',0):,.0f} – ₹{data.get('week52High',0):,.0f}

VALUATION: P/E {data.get('pe','N/A')} | P/B {data.get('pb','N/A')} | EV/EBITDA {data.get('evToEbitda','N/A')}
Mkt Cap: ₹{data.get('marketCap',0)/1e7:,.0f} Cr

QUALITY: ROE {data.get('roe','N/A')}% | Net Margin {data.get('profitMargins','N/A')}%
Revenue Growth {data.get('revenueGrowth','N/A')}% | Debt/Equity {data.get('debtToEquity','N/A')}

TECHNICALS: RSI {data.get('rsi','N/A')} | MACD {data.get('macdSignal','N/A')}
MA50 ₹{data.get('ma50',0):,.0f} | MA200 ₹{data.get('ma200',0):,.0f}

Provide:
1. VERDICT: [STRONG BUY/BUY/HOLD/SELL/STRONG SELL] — one sentence rationale
2. BULL CASE: 3–4 key positives
3. BEAR CASE: 3–4 key risks
4. VALUATION ASSESSMENT: cheap/fair/expensive vs sector
5. TECHNICAL VIEW: momentum, key levels
6. 12-MONTH PRICE TARGET: range with rationale
7. IDEAL INVESTOR: growth/value/dividend/momentum"""

    text  = call_groq([{"role":"user","content":prompt}], system=system)
    model = "llama3-70b (Groq)" if GROQ_API_KEY else "Rule-Based Engine"
    if not text:
        text = rule_based_analysis(data)
    return jsonify({"ok": True, "analysis": text, "model": model})


@app.route("/api/ai/chat", methods=["POST"])
def ai_chat():
    d        = request.get_json() or {}
    messages = d.get("messages", [])
    ctx      = d.get("marketContext", "")
    if not messages:
        return jsonify({"ok": False, "error": "Messages required"})

    system = f"""You are an expert Indian stock market analyst (CFA Level 3) with 20 years on NSE/BSE.
Help retail investors with market analysis, stock research, and investment strategy.
Use ₹ for prices, Cr for crores. Be practical. Add risk disclaimers for investment advice.
Market context: {ctx}"""

    text = call_groq(messages[-10:], system=system, max_tokens=800)
    if not text:
        text = "AI is offline (GROQ_API_KEY not configured on backend). Visit console.groq.com for a free key."
    return jsonify({"ok": True, "response": text})


# ─── STARTUP ────────────────────────────────────────────────────────────────────
def start_background_tasks():
    # 1. Warm cache immediately on startup (in background so server starts fast)
    threading.Thread(target=warm_cache, daemon=True).start()
    # 2. Keep refreshing every minute
    threading.Thread(target=refresh_loop, daemon=True).start()
    # 3. Keep-alive ping (prevents Render free tier sleep)
    threading.Thread(target=keep_alive_loop, daemon=True).start()
    log.info("Background tasks started")


start_background_tasks()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
