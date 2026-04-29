# extractor/config.py
# SharePoint and Azure sections removed
# Files are read directly from quotes/ folder in repository

import os
from dotenv import load_dotenv

load_dotenv()

# ── AI — Groq (Free) ─────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# ── PDF Parsing — LlamaCloud (Free tier) ──
LLAMA_API_KEY = os.environ.get("LLAMA_API_KEY", "")

# ── GitHub ────────────────────────────────
GITHUB_TOKEN = os.environ.get("G_TOKEN", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "")

# ── Output ────────────────────────────────
OUTPUT_FILE    = "catalog_data.json"
ERROR_LOG_FILE = "extraction_errors.json"

# ── Folder to Category Mapping ────────────
# Keys must match subfolder names in quotes/
FOLDER_TO_CATEGORY = {
    "Cybersecurity":             "Cybersecurity",
    "Hosting":                   "Hosting",
    "Network & Telecom":         "Network & Telecom",
    "Service Management (SNow)": "Service Management (SNow)",
    "IdAM":                      "IdAM",
    "M365 & Power Platform":     "M365 & Power Platform",
    "MSP":                       "MSP",
    "Summaries & Reporting":     "Summaries & Reporting",
}

# ── Supported File Extensions ─────────────
SUPPORTED_EXTENSIONS = {
    ".pdf":  "pdf",
    ".xlsx": "excel",
    ".xls":  "excel",
    ".csv":  "csv",
    ".txt":  "text",
    ".docx": "word",
    ".doc":  "word",
}

# ── Known Vendors ─────────────────────────
KNOWN_VENDORS = [
    "NTT Data", "NTT DOCOMO", "TrendMicro", "KnowBe4",
    "SHI", "PC Connection", "CDW", "Equinix", "Quest",
    "Proquire LLC", "ServiceNow", "Microsoft", "Copeland LP",
    "Thrive", "Ricoh", "Honeywell", "Cisco", "Palo Alto",
    "CrowdStrike", "Zscaler", "CyberArk", "Forescout",
    "SolarWinds", "VMware", "NetApp", "Oracle", "IBM",
    "HPE", "Red Hat", "Pure Storage", "SailPoint", "Okta",
    "Resonant Clinical Solutions",
]

# ── Known Services ────────────────────────
KNOWN_SERVICES = [
    "Microsoft 365 E3",
    "Microsoft 365 E5",
    "Microsoft 365 F3",
    "Microsoft Teams Essentials",
    "Microsoft 365 Audio Conferencing",
    "Microsoft 365 Copilot",
    "Power BI Premium",
    "Power Apps Per User",
    "Microsoft Defender",
    "Trend Vision One Endpoint Security",
    "Apex One SaaS",
    "Trend Micro Email Security Advanced",
    "KnowBe4 PhishER Subscription",
    "Security Awareness Training",
    "CyberArk Privileged Access Management",
    "Forescout Network Access Control",
    "Zscaler ZIA Transformation Edition",
    "Palo Alto NGFW Firewall",
    "Cisco Catalyst C8300",
    "Cisco Catalyst 9800-L",
    "Cisco SMARTnet",
    "SolarWinds NPM",
    "Equinix Network Interconnect",
    "VMware Cloud Foundation",
    "NetApp AFF A30 HA System",
    "Oracle Database Enterprise Edition",
    "HPE ProLiant DL380 Gen12",
    "Red Hat Enterprise Linux",
    "Quest On-Demand Migration Suite",
    "ServiceNow ITSM Professional",
    "ServiceNow App Engine Enterprise",
    "ServiceNow Software Asset Management",
]

# ── LlamaCloud Settings ───────────────────
LLAMA_TIER   = "agentic"
LLAMA_EXPAND = ["markdown_full"]

# ── Price Validation ──────────────────────
MIN_VALID_PRICE =       0.01
MAX_VALID_PRICE = 50_000_000

# ── Rate Limiting ─────────────────────────
DELAY_BETWEEN_FILES   = 1
DELAY_BETWEEN_FOLDERS = 2
MAX_RETRIES           = 3
