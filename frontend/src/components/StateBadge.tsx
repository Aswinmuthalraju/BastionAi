import styles from "./StateBadge.module.css";

export type MachineState = "nominal" | "caution" | "interlock" | "verified" | "neutral";

export function StateBadge({ state, children }: { state: MachineState; children: React.ReactNode }) {
  return (
    <span className={`${styles.badge} ${styles[state]}`}>
      <span className={styles.dot} aria-hidden="true" />
      {children}
    </span>
  );
}

/** Maps backend autonomy tiers / outcomes to a MachineState so colour meaning stays consistent app-wide. */
export function autonomyTierToState(tier: string): MachineState {
  switch (tier) {
    case "auto_execute":
      return "verified";
    case "execute_and_verify":
      return "nominal";
    case "human_approval_required":
      return "caution";
    case "dual_approval_required":
      return "interlock";
    default:
      return "neutral";
  }
}

export function outcomeToState(outcome: string): MachineState {
  const o = outcome.toUpperCase();
  if (o === "SUCCESS") return "verified";
  if (o === "BLOCKED" || o === "FAILED") return "interlock";
  if (o === "DRIFT_DETECTED") return "caution";
  return "neutral";
}
