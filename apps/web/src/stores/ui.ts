import { create } from "zustand";
type Notice = { message: string; kind: "success" | "error" };
export const useUI = create<{
  notice: Notice | null;
  notify: (message: string, kind?: Notice["kind"]) => void;
  dismiss: () => void;
}>((set) => ({
  notice: null,
  notify: (message, kind = "success") => set({ notice: { message, kind } }),
  dismiss: () => set({ notice: null }),
}));
