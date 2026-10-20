# Read the Numbers (Valuation Tutor)

An educational tool that teaches people with little or no investing experience to read
the charts and numbers behind a company's valuation, with an adaptive AI tutor.

> Status: milestone 3 of 4 (adaptive AI tutor). Full README comes with milestone 4.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ../saas-valuation-engine      # the SaaS sector's data engine
pip install -e ".[dev,ai]"
streamlit run app/main.py
pytest
```

See [docs/PLAN.md](docs/PLAN.md) and [docs/ADDING_A_SECTOR.md](docs/ADDING_A_SECTOR.md).
