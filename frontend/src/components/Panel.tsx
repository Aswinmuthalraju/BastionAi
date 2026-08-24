import type { ReactNode } from "react";
import styles from "./Panel.module.css";

export function Panel({
  title,
  action,
  children,
  bodyClassName,
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  bodyClassName?: string;
}) {
  return (
    <section className={styles.panel}>
      {title && (
        <header className={styles.header}>
          <h2 className={styles.title}>{title}</h2>
          {action}
        </header>
      )}
      <div className={`${styles.body} ${bodyClassName ?? ""}`}>{children}</div>
    </section>
  );
}
