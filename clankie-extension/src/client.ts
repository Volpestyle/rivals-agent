import type { GameExtensionModuleHost } from "@clankie/extension";
import { RivalsCommandSchema, RivalsStatusSchema, type RivalsCommand } from "./protocol.ts";

const MAX_RESPONSE = 4 * 1024 * 1024;

/** Broker name for the session server's bearer (`/auth rivals-agent` in Clankie). */
export const RIVALS_CREDENTIAL = "rivals-agent";

/** An HTTP(S) origin without credentials, query or path, as the session server serves it. */
export function rivalsOrigin(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) &&
      !url.username &&
      !url.password &&
      !url.search &&
      !url.hash &&
      url.pathname === "/"
      ? url.href
      : undefined;
  } catch {
    return undefined;
  }
}

/** Bounded reads apply to images and JSON, including chunked replies. */
async function bytes(response: Response): Promise<Uint8Array> {
  if (!response.body) throw new Error("empty_response");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      size += next.value.length;
      if (size > MAX_RESPONSE) throw new Error("response_too_large");
      chunks.push(next.value);
    }
  } finally {
    await reader.cancel();
  }
  return Buffer.concat(chunks, size);
}

/** The session-server client. Redirects are refused and replies are bounded. */
export function createRivalsClient(options: {
  host: Pick<GameExtensionModuleHost, "options" | "credential"> &
    Partial<Pick<GameExtensionModuleHost, "goLive">>;
  fetchImpl?: typeof fetch;
}) {
  const fetchImpl = options.fetchImpl ?? fetch;
  return {
    /** The configured origin (`url` option); a sitting keeps the origin it started on. */
    configuredOrigin: () => rivalsOrigin(options.host.options.url),
    async call(
      input: RivalsCommand,
      guard?: () => Promise<void>,
      origin?: string,
    ): Promise<Record<string, unknown>> {
      const parsed = RivalsCommandSchema.safeParse(input);
      if (!parsed.success) return { outcome: "refused", reason: "invalid_request" };
      const command = parsed.data;
      if (command.action === "share" && Boolean(command.guildId) !== Boolean(command.channelId)) {
        return { outcome: "refused", reason: "guild_and_channel_required_together" };
      }
      const base = origin ?? rivalsOrigin(options.host.options.url);
      if (!base) return { outcome: "refused", reason: "rivals_not_configured" };
      const key = await options.host.credential(RIVALS_CREDENTIAL);
      if (key === undefined) return { outcome: "refused", reason: "rivals_credential_missing" };
      try {
        const { action, ...body } = command;
        const path = action === "observe" ? `/v1/frame?sessionId=${command.sessionId}` : `/v1/${action}`;
        await guard?.();
        const response = await fetchImpl(new URL(path, base), {
          method: action === "status" || action === "observe" ? "GET" : "POST",
          headers: { authorization: `Bearer ${key}`, "content-type": "application/json" },
          ...(action === "status" || action === "observe"
            ? {}
            : {
                body: JSON.stringify(action === "share" ? { sessionId: command.sessionId } : body),
              }),
          redirect: "error",
          signal: AbortSignal.timeout(5_000),
        });
        const data = await bytes(response);
        if (action !== "observe" && data.length > 64 * 1024) throw new Error("status_too_large");
        if (!response.ok) {
          let reason = "rivals_rejected";
          try {
            const rejected = JSON.parse(new TextDecoder().decode(data)) as { error?: unknown };
            if (typeof rejected.error === "string" && /^[a-z_]{1,80}$/u.test(rejected.error))
              reason = rejected.error;
          } catch {
            /* A non-JSON upstream failure still has an honest HTTP status. */
          }
          return { outcome: "refused", reason, status: response.status };
        }
        if (action === "observe") {
          if (
            response.headers.get("content-type") !== "image/png" ||
            !Buffer.from(data.subarray(0, 8)).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
          ) {
            throw new Error("invalid_frame");
          }
          return {
            outcome: "frame",
            sessionId: command.sessionId,
            mimeType: "image/png",
            data: Buffer.from(data).toString("base64"),
          };
        }
        const value: unknown = JSON.parse(new TextDecoder().decode(data));
        if (action !== "share") return { outcome: "ok", ...RivalsStatusSchema.parse(value) };
        const shared = value as { watchPath?: unknown; framePath?: unknown };
        if (
          typeof shared.watchPath !== "string" ||
          typeof shared.framePath !== "string" ||
          !/^\/watch\?key=[A-Za-z0-9_-]{32,128}$/u.test(shared.watchPath) ||
          !/^\/frame\.png\?key=[A-Za-z0-9_-]{32,128}$/u.test(shared.framePath)
        ) {
          throw new Error("invalid_share");
        }
        const watchUrl = new URL(shared.watchPath, base).href;
        if (!command.guildId || !command.channelId) return { outcome: "watch", watchUrl };
        if (!options.host.goLive) return { outcome: "watch", watchUrl, publishing: "unavailable" };
        await guard?.();
        const requested = await options.host.goLive({
          guildId: command.guildId,
          channelId: command.channelId,
          snapshotUrl: new URL(shared.framePath, base).href,
        });
        return { outcome: "watch", watchUrl, publishing: requested ? "requested" : "unavailable" };
      } catch {
        return { outcome: "refused", reason: "rivals_unavailable" };
      }
    },
  };
}
