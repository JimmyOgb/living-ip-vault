# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *

import json
import typing


class LivingIPVault(gl.Contract):
    # Single TreeMap — keys are prefixed strings:
    #   "admin"                    -> admin address
    #   "dao_jury"                 -> DAO jury address (caller of resolve_dispute)
    #   "oracle:{addr}"            -> "true" if authorized oracle
    #   "ip_count"                 -> total IP assets registered
    #   "ip:{id}"                  -> JSON IP asset record
    #   "policy:{id}"              -> JSON creator policy record (keyed by ip_id)
    #   "license_count"            -> total licenses issued
    #   "license:{id}"             -> JSON license record
    #   "job_count"                -> total consensus jobs created
    #   "job:{id}"                 -> JSON consensus job record
    #   "balance:{addr}"           -> str int, withdrawable vault balance
    #   "dispute:{license_id}"     -> JSON active dispute record
    state: TreeMap[str, str]

    def __init__(self):
        self.state = TreeMap()
        self.state["admin"]         = str(gl.message.sender_address)
        self.state["dao_jury"]      = str(gl.message.sender_address)
        self.state["ip_count"]      = "0"
        self.state["license_count"] = "0"
        self.state["job_count"]     = "0"

    # ── helpers ────────────────────────────────────────────────────────

    def _is_admin(self) -> bool:
        return str(gl.message.sender_address) == self.state["admin"]

    def _is_dao_jury(self) -> bool:
        return str(gl.message.sender_address) == self.state["dao_jury"]

    def _is_authorized_oracle(self) -> bool:
        k = "oracle:" + str(gl.message.sender_address)
        return k in self.state and self.state[k] == "true"

    def _balance_key(self, addr: str) -> str:
        return "balance:" + addr

    def _get_balance(self, addr: str) -> int:
        k = self._balance_key(addr)
        return int(self.state[k]) if k in self.state else 0

    def _add_balance(self, addr: str, amount: int) -> None:
        current = self._get_balance(addr)
        self.state[self._balance_key(addr)] = str(current + amount)

    # ── admin / oracle management ─────────────────────────────────────

    @gl.public.write
    def set_oracle_authorization(self, oracle_address: str, authorized: bool) -> typing.Any:
        """Admin-only: authorize or revoke an oracle address."""
        if not self._is_admin():
            raise Exception("Auth: Admin only.")
        self.state["oracle:" + oracle_address] = "true" if authorized else "false"
        return "Oracle " + oracle_address + " authorization set to " + str(authorized)

    @gl.public.write
    def set_dao_jury(self, new_jury_address: str) -> typing.Any:
        """Admin-only: update the DAO jury address that resolves disputes."""
        if not self._is_admin():
            raise Exception("Auth: Admin only.")
        self.state["dao_jury"] = new_jury_address
        return "DAO jury updated to " + new_jury_address

    # ── IP registration ────────────────────────────────────────────────

    @gl.public.write
    def register_ip(
        self,
        title: str,
        base_fee: str,
        max_risk_threshold: str,
        policy_json: str,
    ) -> typing.Any:
        """
        Registers a new IP asset with a licensing policy.

        Args:
            title:               Human-readable title of the IP asset.
            base_fee:             Base license fee (as a string, e.g. "100").
            max_risk_threshold:   0.0-1.0 risk tolerance (as a string, e.g. "0.5").
            policy_json:          JSON string with optional keys allow_political,
                                  allow_gambling, allow_adult, allow_ai_training (bools).

        Returns:
            The new IP asset's integer ID.
        """
        fee   = int(base_fee)
        risk  = float(max_risk_threshold)
        if fee < 0:
            raise Exception("Bounds: Fee error.")
        if not (0.0 <= risk <= 1.0):
            raise Exception("Bounds: Threshold error.")

        parsed_policy = json.loads(policy_json) if policy_json else {}

        new_count = int(self.state["ip_count"]) + 1
        ip_id     = new_count
        creator   = str(gl.message.sender_address)

        ip_record = {
            "id":           ip_id,
            "creator":      creator,
            "title":        title,
            "base_fee":     fee,
            "current_fee":  fee,
            "status":       "Active",
        }
        self.state["ip:" + str(ip_id)] = json.dumps(ip_record)

        policy_record = {
            "max_risk_threshold": risk,
            "violation_count":    0,
            "demand_multiplier":  1.0,
            "allow_political":    bool(parsed_policy.get("allow_political", False)),
            "allow_gambling":     bool(parsed_policy.get("allow_gambling", False)),
            "allow_adult":        bool(parsed_policy.get("allow_adult", False)),
            "allow_ai_training":  bool(parsed_policy.get("allow_ai_training", True)),
        }
        self.state["policy:" + str(ip_id)] = json.dumps(policy_record)

        self.state["ip_count"] = str(new_count)
        return ip_id

    # ── licensing ──────────────────────────────────────────────────────

    @gl.public.write
    def purchase_license(self, ip_id: u256, payment_amount: str) -> typing.Any:
        """
        Purchases a license for an IP asset. Payment is recorded as an
        explicit on-chain amount (this contract does not custody native
        value transfers — payment bookkeeping is handled in state).

        Args:
            ip_id:           The IP asset to license.
            payment_amount:  Amount being paid (must be >= current_fee).

        Returns:
            The new license's integer ID.
        """
        iid = int(ip_id)
        k   = "ip:" + str(iid)
        if k not in self.state:
            raise Exception("State: Asset unavailable.")

        asset = json.loads(self.state[k])
        if asset["status"] != "Active":
            raise Exception("State: Asset unavailable.")

        payment = int(payment_amount)
        if payment < asset["current_fee"]:
            raise Exception("Value: Insufficient payment.")

        new_count  = int(self.state["license_count"]) + 1
        license_id = new_count
        licensee   = str(gl.message.sender_address)

        license_record = {
            "id":               license_id,
            "ip_id":            iid,
            "licensee":         licensee,
            "status":           "Active",
            "last_risk_score":  0.0,
            "last_demand_score":0.0,
            "context_class":    "neutral",
        }
        self.state["license:" + str(license_id)] = json.dumps(license_record)

        self._add_balance(asset["creator"], payment)
        self.state["license_count"] = str(new_count)

        return license_id

    @gl.public.write
    def withdraw_earnings(self) -> typing.Any:
        """Withdraws the caller's accumulated vault balance."""
        addr   = str(gl.message.sender_address)
        amount = self._get_balance(addr)
        if amount <= 0:
            raise Exception("Finances: Balance zero.")

        self.state[self._balance_key(addr)] = "0"
        return "Withdrawn: " + str(amount) + " for " + addr

    # ── usage verification + AI consensus review ──────────────────────

    @gl.public.write
    def review_license_usage(
        self,
        license_id: u256,
        external_usage_url: str,
    ) -> typing.Any:
        """
        Oracle-only. Combines usage verification and AI consensus review
        into a single transaction: five validator nodes independently
        fetch the usage evidence and judge it against the creator's
        policy, with full agreement required before state is committed.

        Args:
            license_id:          The license to review.
            external_usage_url:  URL where the IP is allegedly being used.

        Returns:
            Evaluation summary string.
        """
        if not self._is_authorized_oracle():
            raise Exception("Auth: Oracle only.")

        lk = "license:" + str(int(license_id))
        if lk not in self.state:
            raise Exception("State: Missing license.")

        license_data = json.loads(self.state[lk])
        if license_data["status"] != "Active":
            raise Exception("State: License not active.")

        ip_id  = license_data["ip_id"]
        policy = json.loads(self.state["policy:" + str(ip_id)])
        asset  = json.loads(self.state["ip:" + str(ip_id)])

        title           = asset["title"]
        url             = external_usage_url
        allow_political = policy["allow_political"]
        allow_gambling  = policy["allow_gambling"]
        allow_adult     = policy["allow_adult"]
        allow_ai        = policy["allow_ai_training"]

        def run_evaluation() -> typing.Any:
            try:
                evidence = gl.nondet.web.render(url, mode="text")[:2500]
            except Exception:
                evidence = "Usage evidence page unavailable."

            prompt = f"""
You are an onchain GenLayer validator analyzing the contextual placement
of a licensed IP asset titled "{title}", reportedly active at: {url}

Live page evidence:
{evidence}

Evaluate against these explicit creator policy preferences:
- Political placement allowed: {allow_political}
- Gambling/wagering alignment allowed: {allow_gambling}
- Adult content/themes allowed: {allow_adult}
- AI training content scraping allowed: {allow_ai}

Respond with the following JSON format:
{{
    "risk_score": float,            // 0.0-1.0, high if a policy rule is violated
    "demand_score": float,          // 0.0-1.0, based on organic virality/commercial reach
    "context_classification": str,  // "neutral", "commercial_viral", "sensitive", or "controversial"
    "policy_breached": bool         // true if an explicit policy flag was broken
}}
It is mandatory that you respond only using the JSON format above,
nothing else. Don't include any other words or characters,
your output must be only JSON without any formatting prefix or suffix.
This result should be perfectly parsable by a JSON parser without errors.
"""
            result = (
                gl.nondet.exec_prompt(prompt)
                .replace("```json", "")
                .replace("```", "")
            )
            print(result)
            return json.loads(result)

        parsed = gl.eq_principle.strict_eq(run_evaluation)

        risk_score      = max(0.0, min(1.0, float(parsed.get("risk_score", 0.0))))
        demand_score    = max(0.0, min(1.0, float(parsed.get("demand_score", 0.0))))
        context_class   = str(parsed.get("context_classification", "neutral")).lower()
        policy_breached = bool(parsed.get("policy_breached", False))

        if context_class not in ["neutral", "commercial_viral", "sensitive", "controversial"]:
            context_class = "neutral"

        new_job_id = int(self.state["job_count"]) + 1
        job_record = {
            "id":                 new_job_id,
            "license_id":         int(license_id),
            "evidence_url":       url,
            "risk_score":         risk_score,
            "demand_score":       demand_score,
            "context_class":      context_class,
            "policy_breached":    policy_breached,
        }
        self.state["job:" + str(new_job_id)] = json.dumps(job_record)
        self.state["job_count"] = str(new_job_id)

        suspended = False
        if policy_breached or risk_score > policy["max_risk_threshold"] or context_class == "controversial":
            if license_data["status"] == "Active":
                license_data["status"] = "Suspended"
                policy["violation_count"] += 1
                suspended = True

        if context_class == "commercial_viral" or demand_score > 0.65:
            final_multiplier = min(1.0 + (demand_score * 1.5), 3.0)
            policy["demand_multiplier"] = final_multiplier
            asset["current_fee"] = int(asset["base_fee"] * final_multiplier)

        license_data["last_risk_score"]   = risk_score
        license_data["last_demand_score"] = demand_score
        license_data["context_class"]     = context_class

        self.state[lk]                       = json.dumps(license_data)
        self.state["ip:" + str(ip_id)]       = json.dumps(asset)
        self.state["policy:" + str(ip_id)]   = json.dumps(policy)

        return (
            "Job #" + str(new_job_id)
            + " | risk=" + str(round(risk_score, 2))
            + " | demand=" + str(round(demand_score, 2))
            + " | class=" + context_class
            + " | " + ("SUSPENDED" if suspended else "no action")
        )

    # ── disputes / appeals ─────────────────────────────────────────────

    @gl.public.write
    def lodge_appeal(self, license_id: u256, job_id: u256, bond_amount: str) -> typing.Any:
        """
        Licensee-only. Lodges an appeal against a suspension, posting an
        anti-spam bond.

        Args:
            license_id:   The suspended license being appealed.
            job_id:       The consensus job that triggered the suspension.
            bond_amount:  Anti-spam bond amount (must be >= 1).
        """
        lid = int(license_id)
        jid = int(job_id)
        lk  = "license:" + str(lid)
        jk  = "job:" + str(jid)

        if lk not in self.state:
            raise Exception("State: Missing license.")
        if jk not in self.state:
            raise Exception("State: Evidence mismatch.")

        license_data = json.loads(self.state[lk])
        job_evidence = json.loads(self.state[jk])

        if license_data["licensee"] != str(gl.message.sender_address):
            raise Exception("Auth: Invalid caller.")
        if license_data["status"] != "Suspended":
            raise Exception("State: Not suspended.")
        if job_evidence["license_id"] != lid:
            raise Exception("State: Evidence mismatch.")

        bond = int(bond_amount)
        if bond < 1:
            raise Exception("Value: Anti-spam bond required.")

        dispute_record = {
            "license_id":           lid,
            "licensee":             str(gl.message.sender_address),
            "escrow_bond":          bond,
            "status":               "Under_Review",
            "evidence_url":         job_evidence["evidence_url"],
            "flagged_risk_score":   job_evidence.get("risk_score", 0.0),
            "flagged_context_class":job_evidence.get("context_class", "unknown"),
            "consensus_job_id":     jid,
        }
        self.state["dispute:" + str(lid)] = json.dumps(dispute_record)

        license_data["status"] = "Under_Appeal"
        self.state[lk] = json.dumps(license_data)

        return "Appeal lodged for license #" + str(lid) + ". Bond: " + str(bond)

    @gl.public.write
    def resolve_dispute(self, license_id: u256, override_suspension: bool) -> typing.Any:
        """
        DAO-jury-only. Resolves an active dispute, either restoring the
        license (bond refunded to licensee) or confirming termination
        (bond goes to the IP creator).

        Args:
            license_id:            The disputed license.
            override_suspension:   True to restore, False to terminate.
        """
        if not self._is_dao_jury():
            raise Exception("Auth: Jury access only.")

        lid = int(license_id)
        dk  = "dispute:" + str(lid)
        if dk not in self.state:
            raise Exception("State: Case inactive.")

        dispute = json.loads(self.state[dk])
        if dispute["status"] != "Under_Review":
            raise Exception("State: Case inactive.")

        lk = "license:" + str(lid)
        license_data = json.loads(self.state[lk])
        ip_id = license_data["ip_id"]
        asset = json.loads(self.state["ip:" + str(ip_id)])

        if override_suspension:
            license_data["status"] = "Active"
            self._add_balance(dispute["licensee"], dispute["escrow_bond"])
            resolution = "AI_OVERRIDDEN_LICENSE_RESTORED"
        else:
            license_data["status"] = "Terminated"
            self._add_balance(asset["creator"], dispute["escrow_bond"])
            resolution = "AI_CONFIRMED_LICENSE_TERMINATED"

        self.state[lk] = json.dumps(license_data)

        dispute["status"] = "Settled"
        self.state[dk] = json.dumps(dispute)

        return "Dispute for license #" + str(lid) + " resolved: " + resolution

    # ── view methods ───────────────────────────────────────────────────

    @gl.public.view
    def get_ip(self, ip_id: u256) -> str:
        """Returns the full IP asset record as JSON."""
        k = "ip:" + str(int(ip_id))
        return self.state[k] if k in self.state else '{"error": "IP not found."}'

    @gl.public.view
    def get_license(self, license_id: u256) -> str:
        """Returns the full license record as JSON."""
        k = "license:" + str(int(license_id))
        return self.state[k] if k in self.state else '{"error": "License not found."}'

    @gl.public.view
    def get_job(self, job_id: u256) -> str:
        """Returns the full consensus job record as JSON."""
        k = "job:" + str(int(job_id))
        return self.state[k] if k in self.state else '{"error": "Job not found."}'

    @gl.public.view
    def get_dispute(self, license_id: u256) -> str:
        """Returns the active/settled dispute record for a license as JSON."""
        k = "dispute:" + str(int(license_id))
        return self.state[k] if k in self.state else '{"error": "Dispute not found."}'

    @gl.public.view
    def get_balance(self, address: str) -> str:
        """Returns the withdrawable vault balance for an address."""
        return str(self._get_balance(address))

    @gl.public.view
    def get_total_ips(self) -> str:
        """Returns total IP assets registered."""
        return self.state["ip_count"]

    @gl.public.view
    def get_total_licenses(self) -> str:
        """Returns total licenses issued."""
        return self.state["license_count"]

    @gl.public.view
    def get_admin(self) -> str:
        """Returns the contract admin address."""
        return self.state["admin"]
