# Civic Reach

Behavioral Science × GenAI for Public Services

Civic Reach is a GovTech prototype designed to detect and reduce "Administrative Sludge" (frictions) in government documents. Built for the G7 GovAI Grand Challenge, it implements the OECD 2024 "Fixing Frictions" framework to quantify psychological costs in public communications and help citizens decipher them.

## Key Features
- For Officials: Quantifies "Sludge" (Search, Decision, Cognitive, Emotional costs) and auto-generates redesigned visual prototypes.
- For Citizens: Deciphers complex notices into plain language and drafts formal responses.
- Privacy: Stateless architecture (Zero-Retention Policy) suitable for public sector prototyping.

## Requirements
- Python 3.10+
- Google Gemini API Key

## Quick Start
1. Installation
```bash
git clone https://github.com/hrkzz/civic-reach.git
cd civic-reach
pip install -r requirements.txt
```

2. Configuration
Create .env file and put it in the repository root directory.
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

3. Run App
```bash
streamlit run app.py
```

## Methodology
This tool is not a generic wrapper. It implements specific scoring criteria derived from behavioral science. See [methodology.md](https://github.com/hrkzz/civic-reach/blob/main/methodology.md) for the detailed logic based on the OECD 2024 Report.

## Demo Video
[https://www.youtube.com/watch?v=YFiEwFR811U](https://www.youtube.com/watch?v=YFiEwFR811U)

## References
OECD (2024), Fixing Frictions: *‘Sludge audits’ around the world*, OECD Public Governance Policy Papers, OECD Publishing, Paris.[https://www.oecd.org/en/publications/fixing-frictions-sludge-audits-around-the-world_5e9bb35c-en.html](https://www.oecd.org/en/publications/fixing-frictions-sludge-audits-around-the-world_5e9bb35c-en.html)

## Disclaimer
This is a prototype developed for the G7 GovAI Grand Challenge. All outputs should be reviewed by human officials ("Human-in-the-loop").

