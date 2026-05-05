import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose } from "@/components/atomic/dialog";
import { Button } from "@/components/atomic/button";
import { Input } from "@/components/atomic/input"; // <-- your input component
import { type ReactNode, useState } from "react";

type ConfirmDialogProps = {
  trigger: ReactNode;
  title?: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmText?: string;       // The text user must type to enable confirm
  onConfirm: () => void;
};

export function ConfirmDialog({
  trigger,
  title = "Are you sure?",
  description = "This action cannot be undone.",
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  confirmText,
  onConfirm,
}: ConfirmDialogProps) {
  const [inputValue, setInputValue] = useState("");

  const isMatch = confirmText ? inputValue === confirmText : true;

  return (
    <Dialog>
      <DialogTrigger asChild>
        <div onClick={(e) => e.stopPropagation()}>{trigger}</div>
      </DialogTrigger>
      <DialogContent onClick={(e) => e.stopPropagation()}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {description}
            {confirmText && (
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                To confirm, type <span className="font-semibold text-destructive">{confirmText}</span> below:
              </p>
            )}
          </DialogDescription>
        </DialogHeader>

        {confirmText && (
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={`Type "${confirmText}"`}
            onClick={(e) => e.stopPropagation()}
            className="mt-2"
          />
        )}

        <DialogFooter>
          <DialogClose asChild>
            <Button
              variant="outline"
              onClick={(e) => e.stopPropagation()}
            >
              {cancelLabel}
            </Button>
          </DialogClose>
          <Button
            disabled={!isMatch}
            onClick={(e) => {
              e.stopPropagation();
              if (isMatch) onConfirm();
            }}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
