import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import styles from "./TopBar.module.css";

function Mark() {
  return (
    <svg className={styles.mark} viewBox="0 0 32 32" aria-hidden="true">
      <path
        d="M16 5 L26 9 V16 C26 22 21.5 26.5 16 28 C10.5 26.5 6 22 6 16 V9 Z"
        fill="none"
        stroke="var(--nominal)"
        strokeWidth="2"
      />
      <circle cx="16" cy="16" r="3.2" fill="var(--nominal)" />
    </svg>
  );
}

export function TopBar() {
  const { user, logout } = useAuth();
  if (!user) return null;

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `${styles.navLink} ${isActive ? styles.navLinkActive : ""}`;

  return (
    <header className={styles.bar}>
      <div className={styles.brand}>
        <Mark />
        <div>
          <div className={styles.name}>BASTION</div>
          <div className={styles.sub}>Sovereign Industrial Workbench</div>
        </div>
      </div>

      <nav className={styles.nav} aria-label="Primary">
        <NavLink to="/" end className={navClass}>
          Workbench
        </NavLink>
        <NavLink to="/documents" className={navClass}>
          Documents
        </NavLink>
        {user.role === "admin" && (
          <NavLink to="/console" className={navClass}>
            Console
          </NavLink>
        )}
      </nav>

      <div className={styles.right}>
        <div className={styles.user}>
          <div className={styles.userName}>{user.full_name}</div>
          <div className={styles.userRole}>{user.role}</div>
        </div>
        <button type="button" className={styles.logout} onClick={logout}>
          Sign out
        </button>
      </div>
    </header>
  );
}
