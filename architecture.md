# Architecture — Living IP Vault

## Storage: Single TreeMap Pattern

All state lives in one TreeMap[str, str] with prefixed keys.
This is required because GenLayer only supports one storage object
per contract class.

Key namespaces:
  "admin"            -> admin address
  "dao_jury"         -> DAO jury address
  "oracle:{addr}"    -> "true"/"false" authorization flag
  "ip_count"         -> total IPs registered
  "ip:{id}"          -> JSON IP asset record
  "policy:{id}"      -> JSON creator policy (keyed by ip_id)
  "license_count"    -> total licenses issued
  "license:{id}"     -> JSON license record
  "job_count"        -> total consensus jobs
  "job:{id}"         -> JSON evaluation result record
  "balance:{addr}"   -> str int, withdrawable earnings
  "dispute:{lid}"    -> JSON dispute record

## The Schema Error Fix

The original draft had unannotated class-body assignments:

  class LivingIPVault(gl.Contract):
      state: TreeMap[str, str]

      VALID_CLASSES = [...]          <- unannotated class attribute
      STATE_ACTIVE  = "Active"       <- unannotated class attribute

GenVM's schema compiler scans every class-body line to build the
storage layout. An unannotated assignment is not a valid storage
annotation (no ": Type" form), not a method, not a docstring.
Rather than a clean Python error, this crashes schema generation
with the misleading "absent_runner_comment" VM error.

Fix: remove all class-level constants entirely; inline their values
as literal strings wherever they were used.

## AI Consensus: One Call Per Review

The original design split usage verification across two separate
transactions (request_usage_verification + execute_consensus_callback),
requiring an off-chain oracle daemon to sleep 5 seconds between them.
This was simplified into one method (review_license_usage) that runs
the web fetch and LLM judgment inside a single strict_eq call:

  def run_evaluation() -> typing.Any:
      evidence = gl.nondet.web.render(url, mode="text")[:2500]
      result = gl.nondet.exec_prompt(prompt)...
      return json.loads(result)   <- parsed dict

  parsed = gl.eq_principle.strict_eq(run_evaluation)

The oracle only needs one transaction per review cycle.

## Dynamic Pricing Formula

  if demand_score > 0.65 or context_class == "commercial_viral":
      multiplier = min(1.0 + (demand_score * 1.5), 3.0)
      asset["current_fee"] = int(asset["base_fee"] * multiplier)

Maximum 3x the base fee, triggered by organic demand signals.

## Dispute Flow

  Active -> Suspended (on policy breach, via review_license_usage)
  Suspended -> Under_Appeal (on lodge_appeal, bond escrowed)
  Under_Appeal -> Active (if dao_jury calls resolve_dispute(True))
  Under_Appeal -> Terminated (if dao_jury calls resolve_dispute(False))

Bond goes to licensee on restoration, to IP creator on termination.

## Type Constraints

  Class annotations : TreeMap[str, str] only (single instance)
  Method parameters  : str, u256, bool   (NOT float, dict, Address)
  Write returns      : typing.Any
  View returns        : str              (NOT dict, list)

All float values (risk_score, demand_score, fee multiplier) are
computed and stored inside JSON blobs, never as raw TreeMap values.
