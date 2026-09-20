# alysis-login

Standalone device-flow login for [Alysis Code](https://alysiscode.com) that gets you a gateway key (`slk_...`) **without installing the `alysis-code` CLI**.

Pure Python standard library — no dependencies, no install step.

## Why

Alysis Code's official CLI handles login, but if you just want the key (for scripts, CI, or another tool), installing a whole CLI is overkill. This script speaks the same device-flow endpoints directly.

## Usage

```bash
python3 alysis-login.py            # login / refresh key
python3 alysis-login.py --show     # print the stored key
python3 alysis-login.py --revoke   # revoke server-side + delete locally
```

1. Run the script — it prints a code and opens `https://alysiscode.com/activate?code=...` in your browser.
2. Log in and approve the device.
3. The key is saved to `~/.config/alysis-code/key.txt` (mode `600`, directory `700`).

Then use it:

```bash
export ALYSIS_API_KEY=$(cat ~/.config/alysis-code/key.txt)
```

- **Base URL:** `https://vzigujbcjjmpntxhmyvr.supabase.co/functions/v1/llm/v1`
- **Remaining credit:** check at [alysiscode.com/account](https://alysiscode.com/account) — the gateway has no status endpoint.

## How the keys work (verified live)

- `slk_` keys are **long-lived** — no expiry date. Access only ends when the key is revoked (server-side logout).
- What gets metered is **account credit**, not key lifetime:
  - 50 free credits, refilled every 30 days from the last refill.
  - Unused credits expire — no carry-over.
  - Burst limits: max 10 credits / 5 hours, 25 credits / 7 days.

## Security notes

- The Supabase anon key in this script is **public** — it ships bundled with the Alysis website itself and carries no privileges beyond the anonymous role.
- Your personal `slk_` key is stored locally with restrictive permissions (`600`) and is never sent anywhere except the gateway and the revoke endpoint.

## Requirements

- Python 3.10+ (uses `X | None` type syntax)
- Any OS with a browser for the approval step

## License

MIT
