import { Link, type LinkProps } from "react-router";

import { useBusinessPath } from "../business-context";

export function BusinessLink({ to, ...props }: LinkProps) {
  const businessPath = useBusinessPath();
  const target = typeof to === "string" && to.startsWith("/")
    ? businessPath(to)
    : to;
  return <Link to={target} {...props} />;
}
