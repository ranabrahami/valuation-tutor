# Adding a sector

A sector is a folder under `src/valuation_tutor/sectors/` plus one line in
`config/tutor.yaml`. The core (charts, explanations, learning path, tutor) does
not change. `tests/fake_sector.py` is a complete, minimal example, and
`tests/test_core_is_sector_agnostic.py` runs the whole core against it.

## What a sector provides

Implement `core.sector.SectorModule`:

| Member | What it is | SaaS example |
|---|---|---|
| `id`, `name` | Short id and display name | `"saas"`, "US software (SaaS)" |
| `currency`, `accounting_standard` | ISO currency, standard used in the filings | `"USD"`, `"US GAAP"` |
| `data_as_of` | Date of the market data, shown to learners | `"2026-10-18"` |
| `companies()` | The universe, as `CompanyRef`s with a profile (peer subgroup) | 18 companies in 4 profiles |
| `company_data(ticker)` | History, snapshot, peers, optional fitted line and valuation; **every number a `Fact` with a source** | from the saas-valuation-engine |
| `metrics()` | Each metric's label, unit, plain definition, formula, and the concept it teaches | gross margin → `gross_margin` |
| `charts()` | Which core chart kinds to show, with roles filled by the sector's metrics, plus sector notes | `trend` with `bar=revenue, growth=revenue_growth` |
| `concepts()` | Sector-only concepts, ids namespaced `<sector>.<id>`, prerequisites on core concepts | `saas.sbc` |
| `path_changes()` | Steps to insert, replace or remove in the core learning path, each with its lesson text and questions | "Pay in shares" after margins |
| `teaching_examples()` | The best company to teach each chart or concept with | `profit_vs_cash → DDOG` |
| `headline_metrics()` | 3-4 metric ids shown as key numbers at the top of a company page | revenue, growth, free cash flow, price |
| `accounting_notes()` | Context the tutor needs to explain this sector's numbers | "SBC is treated as an expense" |

## Rules

1. **Only an adapter imports the sector's engine.** Wrap the data source in one
   `adapter.py`; turn its output into core types in `module.py`.
2. **Every number is a `Fact`** with a source a learner can follow. A missing value
   is a `Fact` with `value=None` and a `note` saying why: never a guess.
3. **Use core concept ids for universal ideas** (`revenue`, `margin`, `multiple`,
   `dcf`...). That's what carries a learner's mastery across sectors. Only genuinely
   sector-specific ideas get a new, namespaced concept.
4. **Words live in locale files** (`sectors/<id>/locales/<locale>.yaml`), not in code.
5. **Reuse chart kinds.** If the sector needs a picture no kind can draw, add a new
   kind to `core/charts/` (it then works for every sector) rather than drawing it
   inside the sector.

## Checklist

- [ ] `sectors/<id>/adapter.py`, `module.py`, `locales/en.yaml`
- [ ] A data snapshot for deploying (see `scripts/export_snapshot.py` for SaaS)
- [ ] Check every chart kind and every path step resolves (the core drops steps a sector has no chart for)
- [ ] One line in `config/tutor.yaml`
- [ ] Tests like `tests/test_saas_sector.py`: numbers match the engine, every Fact
      has a source, every chart works for every company, teaching examples hold
- [ ] `pytest` passes, including the sector-agnostic tests

## Notes for Israeli retail (planned)

- Data: Israel Securities Authority (MAGNA) filings, IFRS, shekels.
- IFRS 16 puts store leases on the balance sheet and lifts EBITDA: an accounting
  note, plus a path step replacing "pay in shares" (SaaS) with "leases".
- Value drivers: same-store sales (as the `growth` role of the `trend` chart),
  thin margins, inventory and working capital.
- Small peer group: the `peers` chart works from two companies; a fitted line
  (`peer_fit`) may not be meaningful and can simply be left out.
- Hebrew: add `he.yaml` locale files; `meta.direction: rtl` switches the layout.
