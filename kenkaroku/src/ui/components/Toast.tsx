import { useEffect, useState } from "react";
import { useGame } from "../../state/store";

export function Toast() {
  const toast = useGame((s) => s.toast);
  const [shown, setShown] = useState<typeof toast>(null);
  useEffect(() => {
    if (!toast) return;
    setShown(toast);
    const t = setTimeout(() => setShown(null), 2200);
    return () => clearTimeout(t);
  }, [toast]);
  if (!shown) return null;
  return (
    <div className="k-toast" role="status" key={shown.id}>
      {shown.text}
    </div>
  );
}
