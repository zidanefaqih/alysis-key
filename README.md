# alysis-key

Store and print [Alysis Code](https://alysiscode.com) gateway keys (`slk_...`)
via the device flow — **without installing the official `alysis` CLI**.

Pure Python standard library. No dependencies, no install step required.

## What it does

```
alysis-key url        # login -> key saved as ~/.config/alysis-code/key1.txt
alysis-key url        # next login -> key2.txt, key3.txt, ... (never overwrites)
alysis-key key        # print the newest key
alysis-key key 2      # print key2
alysis-key list       # list every stored key
alysis-key revoke 2   # revoke key2 on the server + delete it locally
```

Each login gets its own numbered file, so a second account **never clobbers**
the key of the first one. If the server hands back a key that is already
stored, nothing is written and the existing file is reported instead.

## Install

```bash
# uv
uv tool install git+https://github.com/zidanefaqih/alysis-key

# or pipx
pipx install git+https://github.com/zidanefaqih/alysis-key
```

Or just run it directly — it is a single file:

```bash
python3 alysis_key.py url
```

## Usage

1. `alysis-key url` prints a one-time code and the approval link
   (`https://alysiscode.com/activate?code=...`). It does **not** open a
   browser — use `alysis-key url --open` if you want that.
2. Log in and approve the device.
3. The key is written to `~/.config/alysis-code/keyN.txt` (mode `600`, dir `700`).
4. Print it any time:

```bash
export ALYSIS_API_KEY=$(alysis-key key)
```

- **Base URL:** `https://vzigujbcjjmpntxhmyvr.supabase.co/functions/v1/llm/v1`
- **Remaining credit:** [alysiscode.com/account](https://alysiscode.com/account)
  (the gateway has no status endpoint)

## How the keys work (verified live)

- `slk_` keys are **long-lived** — no expiry. Access only ends when a key is
  revoked (server-side logout).
- What gets metered is **account credit**, not key lifetime:
  - 50 free credits, refilled every 30 days from the last refill.
  - Unused credits expire — no carry-over.
  - Burst limits: max 10 credits / 5 hours, 25 credits / 7 days.

## Storage

```
~/.config/alysis-code/
  key1.txt     # first login
  key2.txt     # second login
  ...
```

Override the directory with `ALYSIS_KEY_DIR` (handy for testing).
Files that do not match `keyN.txt` — including keys created by the old
`alysis-login` script — are **left untouched** and only mentioned by
`alysis-key list`.

## Security notes

- The Supabase anon key inside the script is **public** — it ships bundled with
  the Alysis Code website and carries no privileges beyond the anonymous role.
- Your personal `slk_` keys are stored locally with restrictive permissions
  (`600`) and travel only to the gateway and the revoke endpoint.
- `alysis-key url` polls for approval; a browser/DNS blip is retried instead of
  aborting the 15-minute wait.

## Requirements

- Python 3.10+
- No browser automation: `url` just prints the link (`--open` to launch one)

## License

MIT
