import type { ReactNode } from "react";

export function Modal({ children, onClose, title }: { children: ReactNode; onClose?: () => void; title?: ReactNode }) {
  return (
    <div className="k-modal" role="dialog" aria-modal onClick={onClose}>
      <div className="k-modal__box kintsugi" onClick={(e) => e.stopPropagation()}>
        {title && <h2 className="k-modal__title brush">{title}</h2>}
        {children}
      </div>
    </div>
  );
}

/** 下から出るシート（編成のキャラ選択など） */
export function Sheet({ children, onClose, title }: { children: ReactNode; onClose: () => void; title?: ReactNode }) {
  return (
    <div className="k-sheet" role="dialog" aria-modal onClick={onClose}>
      <div className="k-sheet__box" onClick={(e) => e.stopPropagation()}>
        <div className="k-sheet__head">
          {title && <h2 className="brush">{title}</h2>}
          <button className="k-icon-btn" onClick={onClose} aria-label="閉じる">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
