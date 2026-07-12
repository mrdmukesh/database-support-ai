import { useEffect, useId, useRef } from "react";
interface Props { open: boolean; title: string; message: string; confirmLabel?: string; cancelLabel?: string; onConfirm: () => void; onCancel: () => void }
export function ConfirmationDialog({ open, title, message, confirmLabel="Confirm", cancelLabel="Cancel", onConfirm, onCancel }: Props) {
  const titleId=useId(), descriptionId=useId(), cancelRef=useRef<HTMLButtonElement>(null), priorFocus=useRef<HTMLElement|null>(null);
  useEffect(()=>{ if(!open)return; priorFocus.current=document.activeElement as HTMLElement; cancelRef.current?.focus(); function keydown(event:KeyboardEvent){if(event.key==="Escape"){event.preventDefault();onCancel();}} document.addEventListener("keydown",keydown); return()=>{document.removeEventListener("keydown",keydown);priorFocus.current?.focus();};},[open,onCancel]);
  if (!open) return null;
  return <div role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId}><h2 id={titleId}>{title}</h2><p id={descriptionId}>{message}</p><button ref={cancelRef} type="button" onClick={onCancel}>{cancelLabel}</button><button type="button" onClick={onConfirm}>{confirmLabel}</button></div>;
}
