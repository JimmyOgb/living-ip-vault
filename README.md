# ◈ Living IP Vault

> A GenLayer Intelligent Contract that autonomously enforces IP licensing terms — monitoring real-world usage via AI consensus, dynamically adjusting fees with demand, and routing disputes to a DAO jury. No human intermediary, no centralized rights management platform.

[![GenLayer Studio](https://img.shields.io/badge/GenLayer_Studio-Open_Contract-c9a14a?style=for-the-badge&logoColor=black)](https://studio.genlayer.com/?import-contract=0x639b7335022B0B7BafEddc5872E95AeB1dF097b8)
[![Network](https://img.shields.io/badge/Network-GenLayer_Studionet-60a5fa?style=for-the-badge)](https://studio.genlayer.com)
[![License](https://img.shields.io/badge/License-MIT-4ade80?style=for-the-badge)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Live Deployment](#-live-deployment)
- [How It Works](#-how-it-works)
- [Contract Architecture](#-contract-architecture)
- [Methods](#-methods)
- [Frontend](#-frontend)
- [Getting Started](#-getting-started)
- [Project Structure](#-project-structure)
- [Tech Stack](#-tech-stack)

---

## 🌐 Overview

**Living IP Vault** is a GenLayer Intelligent Contract that makes IP licensing self-governing. A creator registers an asset with a plain-rule policy (no political placement, no gambling, no adult content, allow AI training). A licensee purchases a license. An authorized oracle later discovers the asset being used somewhere on the web and triggers an AI consensus review — five independent validator nodes fetch the usage evidence and judge it against the creator's policy. If they agree there's a violation, the license is automatically suspended and the fee is adjusted to reflect demand. The licensee can appeal to a DAO jury.

**What makes this "living":**
- Licensing fees **self-adjust** with commercial demand (up to 3x base fee)
- Licenses **self-enforce** — violations auto-suspend without human review
- The policy is stored on-chain in plain booleans, not a legal PDF
- Every evaluation is AI-consensus-backed and permanently auditable

---

## 🚀 Live Deployment

| Resource | Link |
|---|---|
| **Contract on GenLayer Studio** | [0x639b7335022B0B7BafEddc5872E95AeB1dF097b8](https://studio.genlayer.com/?import-contract=0x639b7335022B0B7BafEddc5872E95AeB1dF097b8) |
| **Network** | GenLayer Studionet |
| **Contract Address** | `0x639b7335022B0B7BafEddc5872E95AeB1dF097b8` |

---

## ⚙️ How It Works

```
register_ip(title, base_fee, max_risk_threshold, policy_json)
        │
        └── IP asset + policy stored on-chain, status = "Active"

purchase_license(ip_id, payment_amount)
        │
        └── license stored, creator's vault balance credited

review_license_usage(license_id, external_usage_url)  [oracle only]
        │
        └── run_evaluation() inner function
                │
                ├── gl.nondet.web.render(url, mode="text")[:2500]
                │   each validator independently fetches live evidence
                │
                ├── gl.nondet.exec_prompt(prompt)
                │   judges evidence against creator policy:
                │   · risk_score (0-1)
                │   · demand_score (0-1)
                │   · context_classification
                │   · policy_breached (bool)
                │
                └── gl.eq_principle.strict_eq()
                    All 5 nodes must agree on all four fields
                            │
            policy_breached OR risk > threshold OR "controversial"
                    │                       │
            license → Suspended        no action
            violation_count++
                    │
            demand_score > 0.65 OR "commercial_viral"
                    │
            current_fee *= min(1 + demand*1.5, 3.0)

lodge_appeal(license_id, job_id, bond_amount)
        │
        └── license → Under_Appeal, bond escrowed

resolve_dispute(license_id, override_suspension)  [dao_jury only]
        │
        ├── True  → license → Active, bond refunded to licensee
        └── False → license → Terminated, bond to IP creator
```

---

## 🏗️ Contract Architecture

```python
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

class LivingIPVault(gl.Contract):
    state: TreeMap[str, str]
```

### Storage Design

Single `TreeMap[str, str]` with prefixed keys:

| Key | Value | Description |
|---|---|---|
| `"admin"` | `"0xAdmin…"` | Contract admin |
| `"dao_jury"` | `"0xJury…"` | DAO jury address |
| `"oracle:{addr}"` | `"true"/"false"` | Oracle authorization |
| `"ip_count"` | `"4"` | Total IP assets |
| `"ip:{id}"` | JSON string | IP asset record |
| `"policy:{id}"` | JSON string | Creator policy (keyed by ip_id) |
| `"license_count"` | `"12"` | Total licenses |
| `"license:{id}"` | JSON string | License record |
| `"job_count"` | `"8"` | Total consensus jobs |
| `"job:{id}"` | JSON string | Consensus job + evaluation result |
| `"balance:{addr}"` | `"500"` | Withdrawable vault balance |
| `"dispute:{license_id}"` | JSON string | Active/settled dispute |

### Why Class-Level Constants Were Removed

The original draft declared `VALID_CLASSES = [...]` and `STATE_ACTIVE = "Active"` as unannotated class-body assignments. GenVM's schema compiler scans every class-body declaration to build the storage layout — an unannotated attribute doesn't fit any recognized pattern (it's not a `: Type` annotation, not a method, not a docstring) and crashes schema generation with `absent_runner_comment`. The fix was to remove all class-level constants and inline their values as literal strings throughout the methods.

---

## 📌 Methods

### Write Methods

#### `register_ip(title, base_fee, max_risk_threshold, policy_json) → str`
Registers an IP asset with a policy. Returns the IP asset ID.

#### `purchase_license(ip_id, payment_amount) → str`
Issues a license and credits the creator's vault balance.

#### `review_license_usage(license_id, external_usage_url) → str`
**Oracle-only.** Fetches live evidence, runs 5-node AI consensus, auto-suspends on violation, adjusts fee for demand.

#### `lodge_appeal(license_id, job_id, bond_amount) → str`
**Licensee-only.** Posts anti-spam bond and opens a dispute.

#### `resolve_dispute(license_id, override_suspension) → str`
**DAO jury-only.** Restores or terminates the license, allocates the bond accordingly.

#### `withdraw_earnings() → str`
Withdraws the caller's accumulated vault balance.

#### `set_oracle_authorization(oracle_address, authorized) → str`
**Admin-only.** Grants or revokes oracle authorization.

#### `set_dao_jury(new_jury_address) → str`
**Admin-only.** Updates the DAO jury address.

### View Methods

| Method | Returns |
|---|---|
| `get_ip(ip_id)` | Full IP asset + current fee JSON |
| `get_license(license_id)` | Full license record JSON |
| `get_job(job_id)` | Consensus job + evaluation result JSON |
| `get_dispute(license_id)` | Active/settled dispute JSON |
| `get_balance(address)` | Vault balance string |
| `get_total_ips()` | Total IP count |
| `get_total_licenses()` | Total license count |
| `get_admin()` | Admin address |

---

## 🖥️ Frontend

Luxury IP management aesthetic — dark charcoal with gold accents, serif headlines:

- **Five-tab layout** — Register IP, License, AI Review, Disputes, Vault
- **Register IP panel** — title, fee, risk threshold, policy checkboxes (political/gambling/adult/AI training)
- **Asset gallery** — registered IPs with live status and dynamic fee display
- **License panel** — purchase + query by ID
- **AI Review panel** — 5-node consensus animation, risk/demand/breach result card
- **Disputes panel** — appeal and DAO jury resolution side by side
- **Vault panel** — balance check and withdraw
- **Transaction log** — every call with status indicators

### Running locally

```bash
open frontend/index.html
npx serve frontend/
python3 -m http.server 8080 --directory frontend/
```

### Deploying

```bash
netlify deploy --prod --dir frontend/
vercel --prod
```

---

## 🏁 Getting Started

### 1. Open in GenLayer Studio
```
https://studio.genlayer.com/?import-contract=0x639b7335022B0B7BafEddc5872E95AeB1dF097b8
```

### 2. Register an IP Asset
```
title:               Summer Nights
base_fee:             100
max_risk_threshold:   0.5
policy_json:          {"allow_political":false,"allow_gambling":false,"allow_adult":false,"allow_ai_training":true}
```

### 3. Purchase a License
```
ip_id:          1
payment_amount: 100
```

### 4. Review Usage (Oracle)
```
review_license_usage("1", "https://tiktok.com/@lucky_casino/video/789123456")
```
Expected: policy_breached = true (gambling URL), license suspended.

### 5. Lodge Appeal
```
lodge_appeal("1", "1", "5")
```

### 6. Resolve (DAO Jury)
```
resolve_dispute("1", true)   # restore
resolve_dispute("1", false)  # terminate
```

---

## 📁 Project Structure

```
living-ip-vault/
├── contract/
│   └── living_ip_vault.py     # GenLayer Intelligent Contract
├── frontend/
│   └── index.html             # IP management dashboard
├── docs/
│   └── architecture.md        # Storage design, schema fix, consensus notes
├── .gitignore
├── LICENSE
├── package.json
└── README.md
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Blockchain** | GenLayer (L2, Studionet) |
| **Contract Language** | Python (GenLayer Intelligent Contract) |
| **AI Consensus** | `gl.eq_principle.strict_eq` — 5 validator nodes |
| **Web Data** | `gl.nondet.web.render` → live usage evidence |
| **LLM Execution** | `gl.nondet.exec_prompt` (multi-model via OpenRouter) |
| **Storage** | `TreeMap[str, str]` with prefixed key namespacing |
| **Frontend** | Vanilla HTML / CSS / JS — zero dependencies |
| **Fonts** | Cormorant Garamond · Inter · JetBrains Mono |

---

## 📜 License

MIT — see [LICENSE](LICENSE) for details.
