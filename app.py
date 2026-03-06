"""
StockRadar India - Production Backend API v3.0
Real live data from Yahoo Finance for all Nifty 500 stocks
Free AI analysis via Groq (free tier) or HuggingFace
Deploy FREE on: Render.com, Railway.app, or Fly.io
"""

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import yfinance as yf
import json
import time
import threading
import requests
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ─── Cache layer ───────────────────────────────────────────────────────────────
_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 60  # 60 seconds for live prices

def get_cached(key, fetch_fn, ttl=CACHE_TTL):
    with _cache_lock:
        now = time.time()
        if key in _cache and now - _cache[key]['ts'] < ttl:
            return _cache[key]['data']
    try:
        data = fetch_fn()
    except Exception as e:
        data = {"ok": False, "error": str(e)}
    with _cache_lock:
        _cache[key] = {'data': data, 'ts': time.time()}
    return data

# ─── Complete Nifty 500 Stock List ────────────────────────────────────────────
NIFTY500_SYMBOLS = [
    # Large Cap / Nifty 50 core
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
    ("DRREDDY","Dr. Reddy's Laboratories","Pharma"),
    ("CIPLA","Cipla","Pharma"),
    ("DIVISLAB","Divi's Laboratories","Pharma"),
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
    # Mid Cap
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
    ("JINDALSTEL","Jindal Steel & Power","Metal"),
    ("SAIL","Steel Authority of India","Metal"),
    ("NMDC","NMDC","Mining"),
    ("NATIONALUM","National Aluminium","Metal"),
    ("HINDZINC","Hindustan Zinc","Metal"),
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
    ("KANSAINER","Kansai Nerolac","Chemicals"),
    ("ASTRAL","Astral","Plastics"),
    ("SUPREMEIND","Supreme Industries","Plastics"),
    ("POLYCAB","Polycab India","Electricals"),
    ("CROMPTON","Crompton Greaves Consumer","Electricals"),
    ("VOLTAS","Voltas","Electricals"),
    ("BLUESTARCO","Blue Star","Electricals"),
    ("BATAINDIA","Bata India","Consumer"),
    ("RELAXO","Relaxo Footwears","Consumer"),
    ("TRENT","Trent","Retail"),
    ("ABFRL","Aditya Birla Fashion","Retail"),
    ("MANYAVAR","Vedant Fashions","Retail"),
    ("PAGEIND","Page Industries","Textile"),
    ("RAYMOND","Raymond","Textile"),
    ("WELSPUNIND","Welspun India","Textile"),
    ("TRIDENT","Trident","Textile"),
    ("ARVIND","Arvind","Textile"),
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
    ("LUPIN","Lupin","Pharma"),
    ("TORNTPHARM","Torrent Pharmaceuticals","Pharma"),
    ("BIOCON","Biocon","Pharma"),
    ("AUROPHARMA","Aurobindo Pharma","Pharma"),
    ("IPCALAB","IPCA Laboratories","Pharma"),
    ("GRANULES","Granules India","Pharma"),
    ("ALKEM","Alkem Laboratories","Pharma"),
    ("ABBOTINDIA","Abbott India","Pharma"),
    ("PFIZER","Pfizer","Pharma"),
    ("GLAXO","GlaxoSmithKline Pharma","Pharma"),
    ("ZYDUSLIFE","Zydus Lifesciences","Pharma"),
    ("JBCHEPHARM","JB Chemicals & Pharma","Pharma"),
    ("GLAND","Gland Pharma","Pharma"),
    ("SUVENPHAR","Suven Pharmaceuticals","Pharma"),
    ("ERIS","Eris Lifesciences","Pharma"),
    ("AAVAS","Aavas Financiers","NBFC"),
    ("HOMEFIRST","Home First Finance","NBFC"),
    ("APTUS","Aptus Value Housing","NBFC"),
    ("MANAPPURAM","Manappuram Finance","NBFC"),
    ("AUBANK","AU Small Finance Bank","Banking"),
    ("EQUITASBNK","Equitas Small Finance Bank","Banking"),
    ("UJJIVANSFB","Ujjivan Small Finance Bank","Banking"),
    ("KPITTECH","KPIT Technologies","IT"),
    ("PERSISTENT","Persistent Systems","IT"),
    ("COFORGE","Coforge","IT"),
    ("MPHASIS","Mphasis","IT"),
    ("LTTS","L&T Technology Services","IT"),
    ("LTIM","LTIMindtree","IT"),
    ("OFSS","Oracle Financial Services","IT"),
    ("INTELLECT","Intellect Design Arena","IT"),
    ("TANLA","Tanla Platforms","IT"),
    ("ZOMATO","Zomato","Consumer Tech"),
    ("NYKAA","FSN E-Commerce Nykaa","Consumer Tech"),
    ("PAYTM","One 97 Communications Paytm","Fintech"),
    ("POLICYBZR","PB Fintech PolicyBazaar","Fintech"),
    ("DELHIVERY","Delhivery","Logistics"),
    ("INDIAMART","IndiaMART InterMESH","Consumer Tech"),
    ("IRCTC","IRCTC","Travel"),
    ("CONCOR","Container Corporation","Logistics"),
    ("DEEPAKNTR","Deepak Nitrite","Chemicals"),
    ("NAVINFLUOR","Navin Fluorine","Chemicals"),
    ("CLEAN","Clean Science Technology","Chemicals"),
    ("ATUL","Atul","Chemicals"),
    ("VINATIORGA","Vinati Organics","Chemicals"),
    ("TATACHEM","Tata Chemicals","Chemicals"),
    ("GNFC","Gujarat Narmada Fertilizers","Chemicals"),
    ("CHAMBLFERT","Chambal Fertilisers","Chemicals"),
    ("COROMANDEL","Coromandel International","Agri"),
    ("PIIND","PI Industries","Agri"),
    ("RALLIS","Rallis India","Agri"),
    ("KSCL","Kaveri Seed Company","Agri"),
    ("JKCEMENT","JK Cement","Cement"),
    ("RAMCOCEM","Ramco Cements","Cement"),
    ("DALMIABJR","Dalmia Bharat","Cement"),
    ("BIRLACORPN","Birla Corporation","Cement"),
    ("KAJARIACER","Kajaria Ceramics","Building Materials"),
    ("CERA","Cera Sanitaryware","Building Materials"),
    ("CUMMINSIND","Cummins India","Capital Goods"),
    ("BHEL","Bharat Heavy Electricals","Capital Goods"),
    ("BEL","Bharat Electronics","Defence"),
    ("HAL","Hindustan Aeronautics","Defence"),
    ("MAZAGON","Mazagon Dock Shipbuilders","Defence"),
    ("COCHINSHIP","Cochin Shipyard","Defence"),
    ("METROPOLIS","Metropolis Healthcare","Healthcare"),
    ("LALPATHLAB","Dr Lal PathLabs","Healthcare"),
    ("FORTIS","Fortis Healthcare","Healthcare"),
    ("MAXHEALTH","Max Healthcare","Healthcare"),
    ("APOLLOHOSP","Apollo Hospitals","Healthcare"),
    ("THYROCARE","Thyrocare Technologies","Healthcare"),
    ("AFFLE","Affle India","Consumer Tech"),
    ("NAZARA","Nazara Technologies","Gaming"),
    ("HINDPETRO","Hindustan Petroleum","Oil & Gas"),
    ("IOC","Indian Oil Corporation","Oil & Gas"),
    ("GAIL","GAIL India","Oil & Gas"),
    ("OIL","Oil India","Oil & Gas"),
    ("MGL","Mahanagar Gas","Oil & Gas"),
    ("IGL","Indraprastha Gas","Oil & Gas"),
    ("GUJGASLTD","Gujarat Gas","Oil & Gas"),
    ("PETRONET","Petronet LNG","Oil & Gas"),
    ("APLAPOLLO","APL Apollo Tubes","Metal"),
    ("RATNAMANI","Ratnamani Metals Tubes","Metal"),
    ("GPIL","Godawari Power Ispat","Metal"),
    ("KALYANKJIL","Kalyan Jewellers","Jewellery"),
    ("RAJESHEXPO","Rajesh Exports","Jewellery"),
    ("LICI","Life Insurance Corporation","Insurance"),
    ("GICRE","General Insurance Corporation","Insurance"),
    ("NIACL","New India Assurance","Insurance"),
    ("STARHEALTH","Star Health Insurance","Insurance"),
    ("HDFCAMC","HDFC AMC","Asset Management"),
    ("NAM-INDIA","Nippon Life India AMC","Asset Management"),
    ("UTIAMC","UTI AMC","Asset Management"),
    ("360ONE","360 ONE WAM","Wealth Management"),
    ("ANGELONE","Angel One","Broking"),
    ("CDSL","CDSL","Financial Services"),
    ("BSE","BSE","Financial Services"),
    ("MCX","Multi Commodity Exchange","Financial Services"),
    ("CAMS","Computer Age Management","Financial Services"),
    ("VBL","Varun Beverages","Beverages"),
    ("RADICO","Radico Khaitan","Beverages"),
    ("JUBLFOOD","Jubilant FoodWorks","QSR"),
    ("DEVYANI","Devyani International","QSR"),
    ("WESTLIFE","Westlife Foodworld","QSR"),
    ("COLPAL","Colgate-Palmolive India","FMCG"),
    ("EMAMILTD","Emami","FMCG"),
    ("JYOTHYLAB","Jyothy Labs","FMCG"),
    ("PGHH","Procter & Gamble Hygiene","FMCG"),
    ("BIKAJI","Bikaji Foods","FMCG"),
    ("HFCL","HFCL","Telecom"),
    ("TATACOMM","Tata Communications","Telecom"),
    ("RAILTEL","RailTel Corporation","Telecom"),
    ("AIAENG","AIA Engineering","Capital Goods"),
    ("THERMAX","Thermax","Capital Goods"),
    ("ELGIEQUIP","Elgi Equipments","Capital Goods"),
    ("JYOTICNC","Jyoti CNC Automation","Capital Goods"),
    ("GMRINFRA","GMR Airports Infrastructure","Infrastructure"),
    ("IRB","IRB Infrastructure","Infrastructure"),
    ("KNRCON","KNR Constructions","Infrastructure"),
    ("PNCINFRA","PNC Infratech","Infrastructure"),
    ("NCC","NCC","Infrastructure"),
    ("GRINDWELL","Grindwell Norton","Industrial"),
    ("INDHOTEL","Indian Hotels Taj","Hotels"),
    ("LEMONTREE","Lemon Tree Hotels","Hotels"),
    ("MINDA","Uno Minda","Auto Ancillary"),
    ("MOTHERSON","Samvardhana Motherson","Auto Ancillary"),
    ("Gabriel","Gabriel India","Auto Ancillary"),
    ("SUPRAJIT","Suprajit Engineering","Auto Ancillary"),
    ("JKTYRE","JK Tyre","Auto Ancillary"),
    ("MAHINDCIE","Mahindra CIE Automotive","Auto Ancillary"),
    ("TATAINVEST","Tata Investment Corp","Financial Services"),
    ("SPANDANA","Spandana Sphoorty Financial","NBFC"),
    ("CREDITACC","CreditAccess Grameen","NBFC"),
    ("SBFC","SBFC Finance","NBFC"),
    ("NHLIND","Narayana Hrudayalaya","Healthcare"),
    ("ASTER","Aster DM Healthcare","Healthcare"),
    ("RAINBOW","Rainbow Children's Medicare","Healthcare"),
    ("FINOLEX","Finolex Cables","Electricals"),
    ("FINPIPE","Finolex Industries","Plastics"),
    ("SAREGAMA","Saregama India","Media"),
    ("NETWORK18","Network18 Media","Media"),
    ("HYUNDAI","Hyundai Motor India","Auto"),
    ("SAGILITY","Sagility India","Healthcare IT"),
    ("DELHIVERY","Delhivery","Logistics"),
    ("BLUEDART","Blue Dart Express","Logistics"),
    ("SHOPERSTOP","Shoppers Stop","Retail"),
    ("VSTIND","VST Industries","Tobacco"),
    ("NAVINFLUOR","Navin Fluorine","Chemicals"),
    ("ROSSARI","Rossari Biotech","Chemicals"),
    ("ALKYLAMINE","Alkyl Amines Chemicals","Chemicals"),
    ("INDIGOPNTS","Indigo Paints","Chemicals"),
    ("HEIDELBERG","HeidelbergCement India","Cement"),
    ("STARCEMENT","Star Cement","Cement"),
    ("NUVOCO","Nuvoco Vistas","Cement"),
    ("JKLAKSHMI","JK Lakshmi Cement","Cement"),
    ("MANGLMCEM","Mangalam Cement","Cement"),
    ("ORIENTBELL","Orient Bell","Building Materials"),
    ("CAMPUSACTI","Campus Activewear","Consumer"),
    ("VIPIND","VIP Industries","Consumer"),
    ("MCDOWELL-N","United Spirits","Consumer"),
    ("GODIGIT","Go Digit General Insurance","Insurance"),
    ("IXIGO","Le Travenues ixigo","Consumer Tech"),
    ("RATEGAIN","RateGain Travel Technologies","Consumer Tech"),
    ("KAYNES","Kaynes Technology","Electronics"),
    ("DIXON","Dixon Technologies","Electronics"),
    ("AMBER","Amber Enterprises","Electronics"),
    ("SYRMA","Syrma SGS Technology","Electronics"),
    ("AVALON","Avalon Technologies","Electronics"),
    ("SENCO","Senco Gold","Jewellery"),
    ("THANGAMEDL","Thangamayil Jewellery","Jewellery"),
    ("GESHIP","Great Eastern Shipping","Shipping"),
    ("SCI","Shipping Corporation India","Shipping"),
    ("GPPL","Gujarat Pipavav Port","Ports"),
    ("KPRMILL","K P R Mill","Textile"),
    ("PAGEIND","Page Industries","Textile"),
    ("WELCORP","Welspun Corp","Metal"),
    ("JINDALSAW","Jindal Saw","Metal"),
    ("RATNAMANI","Ratnamani Metals","Metal"),
    ("BAYER","Bayer CropScience","Agri"),
    ("SUMICHEM","Sumitomo Chemical India","Agri"),
    ("PIIND","PI Industries","Agri"),
    ("ABSLAMC","Aditya Birla Sun Life AMC","Asset Management"),
    ("KFINTECH","KFin Technologies","Financial Services"),
    ("TV18BRDCST","TV18 Broadcast","Media"),
    ("TIPSINDLTD","Tips Industries","Media"),
    ("DELTACORP","Delta Corp","Gaming"),
    ("CAPLIPOINT","Caplin Point Laboratories","Pharma"),
    ("SOLARA","Solara Active Pharma","Pharma"),
    ("IDFCFIRSTB","IDFC First Bank","Banking"),
    ("FEDERALBNK","Federal Bank","Banking"),
    ("KARURVYSYA","Karur Vysya Bank","Banking"),
    ("SOUTHBANK","South Indian Bank","Banking"),
    ("CSBBANK","CSB Bank","Banking"),
    ("DCBBANK","DCB Bank","Banking"),
    ("LAKSHVILAS","Lakshmi Vilas Bank","Banking"),
    ("BANDHANBNK","Bandhan Bank","Banking"),
    ("RBLBANK","RBL Bank","Banking"),
    ("IDBI","IDBI Bank","Banking"),
    ("JSWENERGY","JSW Energy","Power"),
    ("ADANITRANS","Adani Transmission","Power"),
    ("TORNTPHARM","Torrent Pharmaceuticals","Pharma"),
    ("SUDARSCHEM","Sudarshan Chemical","Chemicals"),
    ("DOMS","DOMS Industries","Consumer"),
    ("PRAJIND","Praj Industries","Capital Goods"),
    ("CRAFTSMAN","Craftsman Automation","Auto Ancillary"),
    ("SANSERA","Sansera Engineering","Auto Ancillary"),
    ("TVSSRICHAK","TVS Srichakra","Auto Ancillary"),
    ("MNGLMCEM","Mangalam Cement","Cement"),
    ("WABCOINDIA","Wabco India","Auto Ancillary"),
    ("FINEORG","Fine Organic Industries","Chemicals"),
    ("LXCHEM","Laxmi Organic Industries","Chemicals"),
    ("TATACHEM","Tata Chemicals","Chemicals"),
    ("GHCL","GHCL","Chemicals"),
    ("TRONOX","Gujarat Fluorochemicals","Chemicals"),
    ("FLUOROCHEM","Gujarat Fluorochemicals","Chemicals"),
    ("GSFC","Gujarat State Fertilizers","Chemicals"),
    ("PARADEEP","Paradeep Phosphates","Chemicals"),
    ("FACT","Fertilisers and Chemicals Travancore","Chemicals"),
    ("NFL","National Fertilizers","Chemicals"),
    ("RCF","Rashtriya Chemicals Fertilizers","Chemicals"),
    ("IOLCP","IOL Chemicals Pharma","Pharma"),
    ("NEULANDLAB","Neuland Laboratories","Pharma"),
    ("DRREDDYS","Dr Reddys Laboratories","Pharma"),
    ("OPTIEMUS","Optiemus Infracom","Electronics"),
    ("NAUKRI","Info Edge India","Consumer Tech"),
    ("INFOEDGE","Info Edge India","Consumer Tech"),
    ("JUSTDIAL","Just Dial","Consumer Tech"),
    ("CARTRADE","CarTrade Tech","Consumer Tech"),
    ("EASEMYTRIP","Easy Trip Planners","Travel"),
    ("MAPMYINDIA","C E Info Systems MapmyIndia","Consumer Tech"),
    ("GLOBUSSPI","Globus Spirits","Beverages"),
    ("SAPPHIRE","Sapphire Foods","QSR"),
    ("BARBEQUE","Barbeque-Nation","QSR"),
    ("TCNSBRANDS","TCNS Clothing","Retail"),
    ("PRATAAP","Prataap Snacks","FMCG"),
    ("DFMFOODS","DFM Foods","FMCG"),
    ("BAJAJCON","Bajaj Consumer Care","FMCG"),
    ("JYOTHY","Jyothy Labs","FMCG"),
    ("VARUNBEV","Varun Beverages","Beverages"),
    ("ROUTE","Route Mobile","IT"),
    ("TANLA","Tanla Platforms","IT"),
    ("NEWGEN","Newgen Software Technologies","IT"),
    ("MASTEK","Mastek","IT"),
    ("CYIENT","Cyient","IT"),
    ("ZENSAR","Zensar Technologies","IT"),
    ("HEXAWARE","Hexaware Technologies","IT"),
    ("BIRLASOFT","Birlasoft","IT"),
    ("SONATSOFTW","Sonata Software","IT"),
    ("NIITLTD","NIIT","IT"),
    ("QUESS","Quess Corp","HR Services"),
    ("TEAMLEASE","TeamLease Services","HR Services"),
    ("SIS","SIS","Services"),
    ("MAHLOG","Mahindra Logistics","Logistics"),
    ("ALLCARGO","Allcargo Logistics","Logistics"),
    ("TCI","Transport Corp India","Logistics"),
    ("GATI","GATI","Logistics"),
    ("TVTODAY","TV Today Network","Media"),
    ("JAGRAN","Jagran Prakashan","Media"),
    ("HINDMEDIA","Hindustan Media Ventures","Media"),
    ("DCMSHRIRAM","DCM Shriram","Diversified"),
    ("KESORAMIND","Kesoram Industries","Diversified"),
    ("JKPAPER","JK Paper","Paper"),
    ("TNPL","Tamil Nadu Newsprint","Paper"),
    ("NATH","Nath Bio-Genes","Agri"),
    ("RSWM","RSWM","Textile"),
    ("FILATEX","Filatex India","Textile"),
    ("NITIN","Nitin Spinners","Textile"),
    ("SPICEJET","SpiceJet","Aviation"),
    ("INDIGO","IndiGo Airlines","Aviation"),
    ("GMRINFRA","GMR Airports","Infrastructure"),
    ("AHLUWALIA","Ahluwalia Contracts","Infrastructure"),
    ("HGINFRA","H G Infra Engineering","Infrastructure"),
    ("SARDAEN","Sarda Energy Minerals","Metal"),
    ("SHYAMMET","Shyam Metalics","Metal"),
    ("JSWHLDING","JSW Holdings","Diversified"),
    ("PIRAMALENT","Piramal Enterprises","Diversified"),
    ("TATAINVEST","Tata Investment Corp","Financial Services"),
    ("MOTILALOFS","Motilal Oswal Financial","Broking"),
    ("IIFL","IIFL Finance","NBFC"),
    ("MFSL","Max Financial Services","Insurance"),
    ("ABCAPITAL","Aditya Birla Capital","Financial Services"),
    ("BAJAJHLDNG","Bajaj Holdings Investment","Diversified"),
    ("GODREJIND","Godrej Industries","Diversified"),
    ("TATAELXSI","Tata Elxsi","IT"),
    ("INTELLECT","Intellect Design Arena","IT"),
    ("NAUKRI","Info Edge India","Consumer Tech"),
    ("LAURUS","Laurus Labs","Pharma"),
    ("WOCKPHARMA","Wockhardt","Pharma"),
    ("SUNPHARMA","Sun Pharma","Pharma"),
    ("NATCOPHARM","Natco Pharma","Pharma"),
    ("AJANTPHARM","Ajanta Pharma","Pharma"),
    ("LAURUSLABS","Laurus Labs","Pharma"),
    ("STRIDES","Strides Pharma","Pharma"),
    ("SEQUENT","SeQuent Scientific","Pharma"),
    ("HERANBA","Heranba Industries","Agri"),
    ("SHARDACROP","Sharda Cropchem","Agri"),
    ("TATAMTRDVR","Tata Motors DVR","Auto"),
    ("TVSMOTORS","TVS Motor Company","Auto"),
    ("FORCEMOT","Force Motors","Auto"),
    ("ESCORTS","Escorts Kubota","Auto"),
    ("MAHINDCIE","Mahindra CIE","Auto Ancillary"),
    ("SETCO","Setco Automotive","Auto Ancillary"),
    ("SUBROS","Subros","Auto Ancillary"),
    ("FIEM","FIEM Industries","Auto Ancillary"),
    ("MINDA","Minda Corporation","Auto Ancillary"),
    ("SANDHAR","Sandhar Technologies","Auto Ancillary"),
    ("LUMAXTECH","Lumax Technologies","Auto Ancillary"),
    ("LUMAXIND","Lumax Industries","Auto Ancillary"),
    ("IDFCFIRSTB","IDFC First Bank","Banking"),
    ("FINOLEXIND","Finolex Industries","Plastics"),
]

# Remove duplicates preserving order
_seen = set()
_unique = []
for item in NIFTY500_SYMBOLS:
    if item[0] not in _seen:
        _seen.add(item[0])
        _unique.append(item)
NIFTY500_SYMBOLS = _unique

# YF symbol mapping (special cases)
_YF_MAP = {
    "M&M": "M&M.NS",
    "BAJAJ-AUTO": "BAJAJ-AUTO.NS",
    "MCDOWELL-N": "MCDOWELL-N.NS",
    "GUJGASLTD": "GUJGAS.NS",
    "NAM-INDIA": "NAM-INDIA.NS",
    "360ONE": "360ONE.NS",
    "FINOLEXIND": "FINPIPE.NS",
    "FLUOROCHEM": "FLUOROCHEM.NS",
}

def get_yf_symbol(sym):
    return _YF_MAP.get(sym, f"{sym}.NS")


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return jsonify({
        "status": "StockRadar India API v3.0",
        "stocks": len(NIFTY500_SYMBOLS),
        "endpoints": ["/api/stocks", "/api/quote/<sym>", "/api/quotes/batch",
                      "/api/fundamentals/<sym>", "/api/history/<sym>",
                      "/api/financials/<sym>", "/api/news/<sym>",
                      "/api/indices", "/api/market-news", "/api/ai/analyze",
                      "/api/ai/chat", "/api/health"]
    })


@app.route('/api/stocks')
def get_stock_list():
    return jsonify([
        {"symbol": s[0], "name": s[1], "sector": s[2], "yf": get_yf_symbol(s[0])}
        for s in NIFTY500_SYMBOLS
    ])


@app.route('/api/quote/<symbol>')
def get_quote(symbol):
    def fetch():
        try:
            yf_sym = get_yf_symbol(symbol.upper())
            ticker = yf.Ticker(yf_sym)
            info = ticker.fast_info
            hist = ticker.history(period="2d", interval="1d")

            price = float(info.last_price or 0)
            prev_close = float(info.previous_close or 0)
            if len(hist) >= 2:
                prev_close = float(hist['Close'].iloc[-2])
            elif len(hist) == 1:
                prev_close = float(hist['Close'].iloc[0])

            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0

            return {
                "symbol": symbol.upper(),
                "price": round(price, 2),
                "prevClose": round(prev_close, 2),
                "change": round(change, 2),
                "changePct": round(change_pct, 2),
                "open": round(float(getattr(info, 'open', None) or price), 2),
                "high": round(float(getattr(info, 'day_high', None) or price), 2),
                "low": round(float(getattr(info, 'day_low', None) or price), 2),
                "volume": int(getattr(info, 'three_month_average_volume', None) or 0),
                "marketCap": float(getattr(info, 'market_cap', None) or 0),
                "week52High": round(float(getattr(info, 'year_high', None) or 0), 2),
                "week52Low": round(float(getattr(info, 'year_low', None) or 0), 2),
                "ok": True
            }
        except Exception as e:
            return {"symbol": symbol.upper(), "ok": False, "error": str(e)}

    data = get_cached(f"quote_{symbol.upper()}", fetch, CACHE_TTL)
    return jsonify(data)


@app.route('/api/quotes/batch')
def get_quotes_batch():
    symbols_param = request.args.get('symbols', '')
    symbols = [s.strip().upper() for s in symbols_param.split(',') if s.strip()][:25]

    results = {}
    threads = []

    def fetch_one(sym):
        def _fetch():
            try:
                yf_sym = get_yf_symbol(sym)
                ticker = yf.Ticker(yf_sym)
                info = ticker.fast_info
                price = float(getattr(info, 'last_price', None) or 0)
                prev = float(getattr(info, 'previous_close', None) or price)
                change = price - prev
                pct = (change / prev * 100) if prev else 0
                return {
                    "symbol": sym,
                    "price": round(price, 2),
                    "prevClose": round(prev, 2),
                    "change": round(change, 2),
                    "changePct": round(pct, 2),
                    "open": round(float(getattr(info, 'open', None) or price), 2),
                    "high": round(float(getattr(info, 'day_high', None) or price), 2),
                    "low": round(float(getattr(info, 'day_low', None) or price), 2),
                    "volume": int(getattr(info, 'three_month_average_volume', None) or 0),
                    "marketCap": float(getattr(info, 'market_cap', None) or 0),
                    "week52High": round(float(getattr(info, 'year_high', None) or 0), 2),
                    "week52Low": round(float(getattr(info, 'year_low', None) or 0), 2),
                    "ok": True
                }
            except Exception as e:
                return {"symbol": sym, "ok": False, "error": str(e)}
        return get_cached(f"quote_{sym}", _fetch, CACHE_TTL)

    # Threaded fetching for batch
    lock = threading.Lock()
    def worker(sym):
        r = fetch_one(sym)
        with lock:
            results[sym] = r

    for sym in symbols:
        t = threading.Thread(target=worker, args=(sym,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join(timeout=15)

    return jsonify(results)


@app.route('/api/fundamentals/<symbol>')
def get_fundamentals(symbol):
    def fetch():
        try:
            yf_sym = get_yf_symbol(symbol.upper())
            ticker = yf.Ticker(yf_sym)
            info = ticker.info

            return {
                "symbol": symbol.upper(),
                "pe": round(float(info.get('trailingPE') or 0), 2),
                "forwardPE": round(float(info.get('forwardPE') or 0), 2),
                "pb": round(float(info.get('priceToBook') or 0), 2),
                "eps": round(float(info.get('trailingEps') or 0), 2),
                "roe": round(float(info.get('returnOnEquity') or 0) * 100, 2),
                "roa": round(float(info.get('returnOnAssets') or 0) * 100, 2),
                "debtToEquity": round(float(info.get('debtToEquity') or 0), 2),
                "dividendYield": round(float(info.get('dividendYield') or 0) * 100, 2),
                "dividendRate": float(info.get('dividendRate') or 0),
                "payoutRatio": round(float(info.get('payoutRatio') or 0) * 100, 2),
                "revenue": float(info.get('totalRevenue') or 0),
                "netIncome": float(info.get('netIncomeToCommon') or 0),
                "grossMargins": round(float(info.get('grossMargins') or 0) * 100, 2),
                "operatingMargins": round(float(info.get('operatingMargins') or 0) * 100, 2),
                "profitMargins": round(float(info.get('profitMargins') or 0) * 100, 2),
                "bookValue": round(float(info.get('bookValue') or 0), 2),
                "currentRatio": round(float(info.get('currentRatio') or 0), 2),
                "quickRatio": round(float(info.get('quickRatio') or 0), 2),
                "beta": round(float(info.get('beta') or 1), 2),
                "sharesOutstanding": float(info.get('sharesOutstanding') or 0),
                "heldPercentInsiders": round(float(info.get('heldPercentInsiders') or 0) * 100, 2),
                "heldPercentInstitutions": round(float(info.get('heldPercentInstitutions') or 0) * 100, 2),
                "week52High": float(info.get('fiftyTwoWeekHigh') or 0),
                "week52Low": float(info.get('fiftyTwoWeekLow') or 0),
                "ma50": float(info.get('fiftyDayAverage') or 0),
                "ma200": float(info.get('twoHundredDayAverage') or 0),
                "enterpriseValue": float(info.get('enterpriseValue') or 0),
                "evToRevenue": round(float(info.get('enterpriseToRevenue') or 0), 2),
                "evToEbitda": round(float(info.get('enterpriseToEbitda') or 0), 2),
                "pegRatio": round(float(info.get('pegRatio') or 0), 2),
                "revenueGrowth": round(float(info.get('revenueGrowth') or 0) * 100, 2),
                "earningsGrowth": round(float(info.get('earningsGrowth') or 0) * 100, 2),
                "longName": info.get('longName') or symbol,
                "sector": info.get('sector') or '',
                "industry": info.get('industry') or '',
                "website": info.get('website') or '',
                "description": info.get('longBusinessSummary') or '',
                "employees": int(info.get('fullTimeEmployees') or 0),
                "city": info.get('city') or '',
                "ok": True
            }
        except Exception as e:
            return {"symbol": symbol.upper(), "ok": False, "error": str(e)}

    data = get_cached(f"fund_{symbol.upper()}", fetch, 300)
    return jsonify(data)


@app.route('/api/history/<symbol>')
def get_history(symbol):
    period = request.args.get('period', '1y')
    interval = request.args.get('interval', '1d')

    # Validate inputs
    valid_periods = ['1d','5d','1mo','3mo','6mo','1y','2y','5y','10y','ytd','max']
    valid_intervals = ['1m','5m','15m','30m','1h','1d','1wk','1mo']
    if period not in valid_periods: period = '1y'
    if interval not in valid_intervals: interval = '1d'

    cache_ttl = 60 if interval in ['1m','5m','15m'] else 300

    def fetch():
        try:
            yf_sym = get_yf_symbol(symbol.upper())
            ticker = yf.Ticker(yf_sym)
            hist = ticker.history(period=period, interval=interval)

            data = []
            for idx, row in hist.iterrows():
                data.append({
                    "date": idx.strftime('%Y-%m-%d %H:%M'),
                    "open": round(float(row['Open']), 2),
                    "high": round(float(row['High']), 2),
                    "low": round(float(row['Low']), 2),
                    "close": round(float(row['Close']), 2),
                    "volume": int(row['Volume'])
                })
            return {"symbol": symbol.upper(), "data": data, "ok": True}
        except Exception as e:
            return {"symbol": symbol.upper(), "ok": False, "error": str(e), "data": []}

    data = get_cached(f"hist_{symbol.upper()}_{period}_{interval}", fetch, cache_ttl)
    return jsonify(data)


@app.route('/api/financials/<symbol>')
def get_financials(symbol):
    def fetch():
        try:
            yf_sym = get_yf_symbol(symbol.upper())
            ticker = yf.Ticker(yf_sym)

            quarterly = []
            qf = ticker.quarterly_financials
            if qf is not None and not qf.empty:
                for col in qf.columns[:8]:
                    q = {"period": str(col)[:10]}
                    for metric in ['Total Revenue','Net Income','Operating Income','Gross Profit','EBITDA']:
                        if metric in qf.index:
                            val = qf[col].get(metric)
                            try:
                                q[metric.replace(' ','_').lower()] = float(val) if val is not None else None
                            except:
                                q[metric.replace(' ','_').lower()] = None
                    quarterly.append(q)

            annual = []
            af = ticker.financials
            if af is not None and not af.empty:
                for col in af.columns[:5]:
                    a = {"period": str(col)[:10]}
                    for metric in ['Total Revenue','Net Income','Operating Income','Gross Profit']:
                        if metric in af.index:
                            val = af[col].get(metric)
                            try:
                                a[metric.replace(' ','_').lower()] = float(val) if val is not None else None
                            except:
                                a[metric.replace(' ','_').lower()] = None
                    annual.append(a)

            # Balance sheet
            bs = []
            qbs = ticker.quarterly_balance_sheet
            if qbs is not None and not qbs.empty:
                for col in qbs.columns[:4]:
                    b = {"period": str(col)[:10]}
                    for metric in ['Total Assets','Total Liabilities Net Minority Interest','Stockholders Equity','Total Debt','Cash And Cash Equivalents']:
                        if metric in qbs.index:
                            val = qbs[col].get(metric)
                            try:
                                b[metric.replace(' ','_').lower()] = float(val) if val is not None else None
                            except:
                                b[metric.replace(' ','_').lower()] = None
                    bs.append(b)

            return {
                "symbol": symbol.upper(),
                "quarterly": quarterly,
                "annual": annual,
                "balanceSheet": bs,
                "ok": True
            }
        except Exception as e:
            return {"symbol": symbol.upper(), "ok": False, "error": str(e),
                    "quarterly": [], "annual": [], "balanceSheet": []}

    data = get_cached(f"fin_{symbol.upper()}", fetch, 3600)
    return jsonify(data)


@app.route('/api/news/<symbol>')
def get_news(symbol):
    def fetch():
        try:
            yf_sym = get_yf_symbol(symbol.upper())
            ticker = yf.Ticker(yf_sym)
            news = ticker.news or []
            return {
                "symbol": symbol.upper(),
                "news": [{
                    "title": n.get('content',{}).get('title','') or n.get('title',''),
                    "link": n.get('content',{}).get('canonicalUrl',{}).get('url','') or n.get('link',''),
                    "publisher": n.get('content',{}).get('provider',{}).get('displayName','') or n.get('publisher',''),
                    "published": n.get('content',{}).get('pubDate','') or str(n.get('providerPublishTime','')),
                    "summary": n.get('content',{}).get('summary','') or n.get('summary',''),
                } for n in news[:15] if n],
                "ok": True
            }
        except Exception as e:
            return {"symbol": symbol.upper(), "ok": False, "error": str(e), "news": []}

    data = get_cached(f"news_{symbol.upper()}", fetch, 600)
    return jsonify(data)


@app.route('/api/market-news')
def get_market_news():
    def fetch():
        try:
            t = yf.Ticker("^NSEI")
            news = t.news or []
            return {"news": [{
                "title": n.get('content',{}).get('title','') or n.get('title',''),
                "link": n.get('content',{}).get('canonicalUrl',{}).get('url','') or n.get('link',''),
                "publisher": n.get('content',{}).get('provider',{}).get('displayName','') or n.get('publisher',''),
                "published": n.get('content',{}).get('pubDate','') or str(n.get('providerPublishTime','')),
            } for n in news[:20] if n], "ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e), "news": []}

    data = get_cached("market_news", fetch, 600)
    return jsonify(data)


@app.route('/api/indices')
def get_indices():
    def fetch():
        indices = {
            "NIFTY50": "^NSEI",
            "SENSEX": "^BSESN",
            "BANKNIFTY": "^NSEBANK",
            "NIFTYIT": "^CNXIT",
            "NIFTYMIDCAP": "^CNXMIDCAP",
            "NIFTYSMALLCAP": "^CNXSC",
        }
        result = {}
        for name, sym in indices.items():
            try:
                t = yf.Ticker(sym)
                info = t.fast_info
                price = float(getattr(info, 'last_price', None) or 0)
                prev = float(getattr(info, 'previous_close', None) or price)
                change = price - prev
                pct = (change / prev * 100) if prev else 0
                result[name] = {
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "changePct": round(pct, 2),
                    "ok": True
                }
            except:
                result[name] = {"ok": False, "price": 0, "change": 0, "changePct": 0}
        return result

    data = get_cached("indices", fetch, 60)
    return jsonify(data)


# ─── FREE AI ENDPOINTS ─────────────────────────────────────────────────────────
# Uses Groq (free tier) - sign up at console.groq.com - or falls back to rule-based

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-70b-8192"  # Free on Groq


def call_groq(messages, system="", max_tokens=1500):
    """Call Groq free API (llama3-70b)"""
    if not GROQ_API_KEY:
        return None

    payload = {
        "model": GROQ_MODEL,
        "max_tokens": max_tokens,
        "messages": []
    }
    if system:
        payload["messages"].append({"role": "system", "content": system})
    payload["messages"].extend(messages)

    try:
        r = requests.post(GROQ_URL, json=payload,
                          headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                                   "Content-Type": "application/json"},
                          timeout=30)
        r.raise_for_status()
        data = r.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return None


def rule_based_analysis(stock_data):
    """Fallback when no AI key: rule-based analysis"""
    pe = stock_data.get('pe', 0)
    roe = stock_data.get('roe', 0)
    rsi = stock_data.get('rsi', 50)
    pct = stock_data.get('changePct', 0)
    debt_eq = stock_data.get('debtToEquity', 0)
    prof_margin = stock_data.get('profitMargins', 0)
    rev_growth = stock_data.get('revenueGrowth', 0)

    verdict = "HOLD"
    bull = []
    bear = []

    if roe > 20: bull.append(f"Strong ROE of {roe:.1f}% indicates efficient capital use")
    if pe > 0 and pe < 25: bull.append(f"Reasonable P/E of {pe:.1f}x — not overly expensive")
    if rsi < 40: bull.append(f"RSI at {rsi:.0f} — stock may be oversold, potential reversal")
    if prof_margin > 15: bull.append(f"Healthy net margin of {prof_margin:.1f}%")
    if rev_growth > 10: bull.append(f"Strong revenue growth of {rev_growth:.1f}%")
    if pct > 2: bull.append("Positive momentum today")

    if pe > 60 and pe > 0: bear.append(f"High P/E of {pe:.1f}x — premium valuation, limited margin of safety")
    if debt_eq > 1.5: bear.append(f"Elevated debt/equity ratio of {debt_eq:.1f}x — leverage risk")
    if rsi > 70: bear.append(f"RSI at {rsi:.0f} — potentially overbought, watch for pullback")
    if rev_growth < 0: bear.append(f"Revenue growth negative at {rev_growth:.1f}%")
    if roe < 10 and roe > 0: bear.append(f"Weak ROE of {roe:.1f}% — capital efficiency concerns")

    bull_count = len(bull)
    bear_count = len(bear)

    if bull_count >= 3 and bear_count <= 1:
        verdict = "BUY"
    elif bear_count >= 3 and bull_count <= 1:
        verdict = "SELL"
    elif bull_count >= 4:
        verdict = "STRONG BUY"

    analysis = f"""VERDICT: {verdict}

BULL CASE (Positives):
{chr(10).join('• ' + b for b in bull) if bull else '• Limited positive signals from current data'}

BEAR CASE (Risks):
{chr(10).join('• ' + b for b in bear) if bear else '• No major red flags from current data'}

VALUATION ASSESSMENT:
{'• Stock appears attractively valued based on P/E and growth metrics' if pe > 0 and pe < 20 else '• Valuation appears stretched at current levels' if pe > 50 else '• Valuation is in a fair range relative to typical Indian market multiples'}
• Compare with sector peers for relative valuation context

TECHNICAL VIEW:
• RSI at {rsi:.0f} — {'oversold territory, watch for bounce' if rsi < 30 else 'overbought, potential consolidation' if rsi > 70 else 'neutral momentum zone'}
• Today's move: {pct:+.2f}%

NOTE: This is a rule-based analysis. Add GROQ_API_KEY environment variable on your backend for full AI-powered research reports.
"""
    return analysis


@app.route('/api/ai/analyze', methods=['POST'])
def ai_analyze():
    """AI-powered stock analysis — uses Groq free tier, falls back to rules"""
    data = request.get_json() or {}
    symbol = data.get('symbol', '')
    stock_data = data.get('stockData', {})

    if not symbol:
        return jsonify({"ok": False, "error": "Symbol required"})

    system = """You are a senior Indian equity research analyst (CFA Level 3) with 20+ years experience on NSE/BSE. 
You provide institutional-quality research reports for retail investors.
Use Indian market context: SEBI regulations, FII/DII flows, RBI policy, sector dynamics.
Use ₹ for prices, Cr for crores. Be data-driven, concise, and actionable."""

    prompt = f"""Analyze this Indian stock comprehensively:

COMPANY: {stock_data.get('name', symbol)} ({symbol}.NS) | SECTOR: {stock_data.get('sector', 'N/A')}

PRICE & MOMENTUM:
- Price: ₹{stock_data.get('price', 0):,.2f} | Change: {stock_data.get('changePct', 0):+.2f}%
- 52W Range: ₹{stock_data.get('week52Low', 0):,.0f} — ₹{stock_data.get('week52High', 0):,.0f}
- From 52W High: {((stock_data.get('week52High',1) - stock_data.get('price',1))/max(stock_data.get('week52High',1),1)*100):.1f}% below

VALUATION:
- P/E: {stock_data.get('pe', 'N/A')} | Forward P/E: {stock_data.get('forwardPE', 'N/A')} | P/B: {stock_data.get('pb', 'N/A')}
- EV/EBITDA: {stock_data.get('evToEbitda', 'N/A')} | PEG: {stock_data.get('pegRatio', 'N/A')}
- Market Cap: ₹{stock_data.get('marketCap', 0)/1e7:,.0f} Cr

PROFITABILITY:
- ROE: {stock_data.get('roe', 'N/A')}% | ROA: {stock_data.get('roa', 'N/A')}%
- Net Margin: {stock_data.get('profitMargins', 'N/A')}% | Gross Margin: {stock_data.get('grossMargins', 'N/A')}%
- Revenue Growth: {stock_data.get('revenueGrowth', 'N/A')}% | Earnings Growth: {stock_data.get('earningsGrowth', 'N/A')}%

BALANCE SHEET:
- Debt/Equity: {stock_data.get('debtToEquity', 'N/A')} | Current Ratio: {stock_data.get('currentRatio', 'N/A')}
- Dividend Yield: {stock_data.get('dividendYield', 'N/A')}%

TECHNICALS:
- RSI(14): {stock_data.get('rsi', 'N/A')} | MACD: {stock_data.get('macdSignal', 'N/A')}
- MA50: ₹{stock_data.get('ma50', 0):,.0f} | MA200: ₹{stock_data.get('ma200', 0):,.0f}
- Trend: {stock_data.get('trend', 'N/A')} | Volatility: {stock_data.get('volatility', 'N/A')}%

Provide:
1. VERDICT: [STRONG BUY / BUY / HOLD / SELL / STRONG SELL] — one-line rationale
2. BULL CASE: 3-4 key positives (bullet points)
3. BEAR CASE: 3-4 key risks (bullet points)
4. VALUATION ASSESSMENT: cheap/fair/expensive vs sector, target P/E or EV/EBITDA
5. TECHNICAL VIEW: key levels, momentum assessment
6. 12-MONTH PRICE TARGET: range with rationale
7. IDEAL INVESTOR: type of investor this suits (growth/value/dividend/momentum)"""

    # Try Groq first
    ai_text = call_groq([{"role": "user", "content": prompt}], system=system)

    # Fallback to rule-based
    if not ai_text:
        ai_text = rule_based_analysis(stock_data)

    return jsonify({"ok": True, "analysis": ai_text, "model": "llama3-70b (Groq)" if GROQ_API_KEY else "Rule-Based Engine"})


@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    """AI market chat — uses Groq free tier"""
    data = request.get_json() or {}
    messages = data.get('messages', [])
    market_context = data.get('marketContext', '')

    if not messages:
        return jsonify({"ok": False, "error": "Messages required"})

    system = f"""You are an expert Indian stock market analyst (CFA Level 3) with 20+ years experience on NSE/BSE.
You help retail investors understand markets, analyze stocks, and make informed decisions.
Use Indian market context: SEBI regulations, FII/DII flows, RBI policy, sector dynamics.
Use ₹ for prices, Cr for crores. Be practical and actionable. Add appropriate risk disclaimers.

CURRENT MARKET CONTEXT:
{market_context}"""

    ai_text = call_groq(messages, system=system, max_tokens=800)

    if not ai_text:
        ai_text = """I'm currently running in offline mode (no AI API key configured on the backend).

To enable full AI chat:
1. Sign up for a FREE Groq API key at console.groq.com
2. Set GROQ_API_KEY environment variable on your backend
3. Restart the server

Meanwhile, I can provide rule-based analysis on individual stocks via the stock detail panel."""

    return jsonify({"ok": True, "response": ai_text})


@app.route('/api/health')
def health():
    return jsonify({
        "status": "ok",
        "timestamp": time.time(),
        "stocks": len(NIFTY500_SYMBOLS),
        "ai_enabled": bool(GROQ_API_KEY),
        "cache_size": len(_cache)
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, port=port, host='0.0.0.0')
