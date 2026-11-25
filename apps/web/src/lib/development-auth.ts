/** Server-only policy shared by session issuance, inspection and proxying. */
export function developmentAuthEnabled(): boolean {
  return (
    ["development", "test"].includes(process.env.APP_ENV || "") &&
    process.env.NODE_ENV !== "production" &&
    process.env.AUTH_MODE === "development" &&
    process.env.NEXT_PUBLIC_AUTH_MODE === "development" &&
    (process.env.DEV_AUTH_TOKEN?.length || 0) >= 32
  );
}
