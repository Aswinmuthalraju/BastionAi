import styles from "./RiskMeter.module.css";

function severityColor(value: number, max: number): string {
  const ratio = value / max;
  if (ratio >= 0.8) return "var(--interlock)";
  if (ratio >= 0.5) return "var(--caution)";
  return "var(--verified)";
}

export function RiskMeterRow({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = Math.round((value / max) * 100);
  return (
    <div className={styles.row}>
      <span className={styles.label}>{label}</span>
      <div className={styles.track} role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max} aria-label={label}>
        <div className={styles.fill} style={{ width: `${pct}%`, background: severityColor(value, max) }} />
      </div>
      <span className={styles.value}>
        {value} / {max}
      </span>
    </div>
  );
}
