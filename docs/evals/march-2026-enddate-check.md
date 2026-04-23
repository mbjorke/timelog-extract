# March 2026 End-Date Check

Date: 2026-04-23  
Mode: `--invoice-mode calibrated-a` with `march_invoice_ground_truth.json`

## Commands

```bash
python3 timelog_extract.py report --from 2026-03-01 --to 2026-03-30 --format json --invoice-mode calibrated-a --invoice-ground-truth march_invoice_ground_truth.json > /tmp/march_to_30.json
python3 timelog_extract.py report --from 2026-03-01 --to 2026-03-31 --format json --invoice-mode calibrated-a --invoice-ground-truth march_invoice_ground_truth.json > /tmp/march_to_31.json
```

## Result

- Total hours (`to=2026-03-30`): `97.780h`
- Total hours (`to=2026-03-31`): `103.697h`
- Delta (`31 - 30`): `+5.917h`

Largest project deltas (`31 - 30`):

- Project names are intentionally anonymized in this markdown summary.
- Detailed project-level deltas should be reviewed in restricted JSON artifacts when needed.

## Invoice-critical note

Using `--to 2026-03-30` instead of `--to 2026-03-31` undercounts March materially.
For invoice runs, always use the final calendar date of the month.

