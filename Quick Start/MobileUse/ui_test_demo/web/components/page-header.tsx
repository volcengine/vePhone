import type { ReactNode } from "react";

import { BusinessLink as Link } from "./business-link";

export type BreadcrumbItem = {
  label: string;
  to?: string;
};

function ChevronRightIcon() {
  return (
    <svg
      className="breadcrumb-sep"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  breadcrumbs: BreadcrumbItem[];
  actions?: ReactNode;
  className?: string;
}) {
  const classes = ["page-header", "unified-page-header", className]
    .filter(Boolean)
    .join(" ");

  return (
    <header className={classes}>
      <div className="page-title-area">
        <nav className="breadcrumb" aria-label="面包屑">
          {breadcrumbs.map((item, index) => (
            <span className="breadcrumb-item" key={`${item.label}-${index}`}>
              {index > 0 && <ChevronRightIcon />}
              {item.to ? (
                <Link to={item.to} className="breadcrumb-link">
                  {item.label}
                </Link>
              ) : (
                <span className="breadcrumb-current">{item.label}</span>
              )}
            </span>
          ))}
        </nav>
        <h1 className="page-title">{title}</h1>
        {description && <p className="page-subtitle">{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}
