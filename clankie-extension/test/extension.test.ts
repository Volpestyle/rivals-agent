/**
 * The extension inside a real Clankie core: its module loader, game registry,
 * durable play ledger, lease router and credential broker, from the sibling
 * Clankie checkout (`CLANKIE_ROOT`, default `../../clankie` from this folder).
 * The session server is an HTTP fixture with controllable cleanup receipts,
 * so these faults are injected offline: no game, no pad.
 */
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { randomUUID } from "node:crypto";
import { setTimeout as sleep } from "node:timers/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import type { RivalsStatus } from "../src/protocol.ts";

const here = fileURLToPath(new URL(".", import.meta.url));
const clankie = resolve(process.env.CLANKIE_ROOT ?? join(here, "../../../clankie"));
const core = async <T>(path: string): Promise<T> =>
  (await import(pathToFileURL(join(clankie, path)).href)) as T;
const extensionModule = join(here, "../src/index.ts");

type Identity = {
  conversationId: string;
  route?: { owner: { conversationId: string }; mode: "machine" | "social" };
  current: () => boolean;
  authorize: (resource: string, action: string) => Promise<boolean>;
};
type Projection = {
  paths: readonly string[];
  tools(turn: { bodyIdentity?: Identity }): {
    execute(id: string, input: unknown, ...rest: unknown[]): Promise<{ details: Record<string, unknown> }>;
  }[];
  routes(options: { settings: unknown; authorize(request: Request): Promise<Identity | undefined> }): {
    fetch(request: Request): Response | Promise<Response>;
  };
};
type Registry = {
  projections(): Projection[];
  catalog(): Promise<{ extensions: { id: string; connector: unknown; status: { state: string } }[] }>;
  unregister(id: string): Promise<void>;
};
type Leases = {
  acquire(resource: "play", conversationId: string, ttlMs: number): { outcome: string; lease?: unknown };
  release(lease: unknown): unknown;
  status(resource: "play"): { state: string } | undefined;
  close(): void;
};
type Installed = { id: string; close(): Promise<void> }[];

const { GameExtensionRegistry } = await core<{ GameExtensionRegistry: new () => Registry }>(
  "packages/game-extension/src/index.ts",
);
const { BodyLeaseStore } = await core<{ BodyLeaseStore: new (directory: string) => Leases }>(
  "apps/clankie/src/body-leases.ts",
);
const { BodyLeaseRouter } = await core<{
  BodyLeaseRouter: new (store: Leases) => {
    recover(
      identity: Identity,
      resource: "play",
      confirm: (guard: () => Promise<void>) => Promise<boolean>,
    ): Promise<Record<string, unknown>>;
  };
}>("apps/clankie/src/body-lease-router.ts");
const { loadGameExtensionModules, recoverExternalPlay } = await core<{
  loadGameExtensionModules(input: Record<string, unknown>): Promise<Installed>;
  recoverExternalPlay(
    games: Installed,
    registry: Registry,
    guard: () => Promise<void>,
  ): Promise<boolean | undefined>;
}>("apps/clankie/src/game-extension-modules.ts");
const { FileCredentialStore } = await core<{
  FileCredentialStore: new (path: string) => { set(name: string, value: unknown): Promise<void> };
}>("packages/credential-broker/src/index.ts");

const cleanups: (() => Promise<void>)[] = [];
afterEach(async () => {
  for (const cleanup of cleanups.splice(0).reverse()) await cleanup();
});

const owner = (conversationId = "owner"): Identity => ({
  conversationId,
  current: () => true,
  authorize: async () => true,
  route: { owner: { conversationId }, mode: "machine" },
});
const start = {
  action: "start" as const,
  requestId: "sitting",
  objective: { mode: "combat" as const, note: "retained prose" },
  maxSeconds: 60,
};

async function poll(read: () => Promise<unknown> | unknown, expected: unknown, timeoutMs = 5000) {
  const deadline = Date.now() + timeoutMs;
  let value = await read();
  while (value !== expected && Date.now() < deadline) {
    await sleep(25);
    value = await read();
  }
  assert.equal(value, expected);
}

/** Session-server fixture: real authenticated HTTP, controlled cleanup receipts, no game body. */
async function fixture() {
  const directory = await mkdtemp(join(tmpdir(), "rivals-extension-"));
  let status: RivalsStatus = {
    schemaVersion: 1,
    execution: "replay",
    modes: ["autonomous", "combat", "disengage"],
    noteApplied: false,
    session: null,
  };
  let denyStop = false;
  let unavailable = false;
  let lostStart = false;
  let heldStart = false;
  let cleanupOnStop = false;
  const calls: { path: string; input: Record<string, unknown> }[] = [];
  const bearer = randomUUID();
  const server: Server = createServer(async (request, response) => {
    if (request.headers.authorization !== `Bearer ${bearer}`) {
      response.writeHead(401).end();
      return;
    }
    const chunks: Buffer[] = [];
    for await (const chunk of request) chunks.push(Buffer.from(chunk));
    const input = chunks.length
      ? (JSON.parse(Buffer.concat(chunks).toString()) as Record<string, unknown>)
      : {};
    calls.push({ path: request.url!, input });
    if (unavailable) {
      response.destroy();
      return;
    }
    if (request.url === "/v1/start") {
      status.session = {
        id: randomUUID().replaceAll("-", ""),
        requestId: String(input.requestId),
        phase: "starting",
        objective: input.objective as NonNullable<RivalsStatus["session"]>["objective"],
        startedAt: Date.now() / 1000,
        maxSeconds: Number(input.maxSeconds),
        observation: null,
        summary: null,
        error: null,
      };
      if (lostStart) {
        response.destroy();
        return;
      }
      if (heldStart) return; // Real client deadline; the original sitting still exists.
    }
    if (request.url === "/v1/stop") {
      if (denyStop || input.sessionId !== status.session?.id) {
        response
          .writeHead(409, { "content-type": "application/json" })
          .end(JSON.stringify({ error: "session_mismatch" }));
        return;
      }
      status.session!.phase = "stopping";
      if (cleanupOnStop) stopped();
    }
    if (request.url === "/v1/objective")
      status.session!.objective = input.objective as NonNullable<RivalsStatus["session"]>["objective"];
    response.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(status));
  });
  await new Promise<void>((done) => server.listen(0, "127.0.0.1", done));
  let url = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
  const credentials = new FileCredentialStore(join(directory, "credentials.json"));
  await credentials.set("rivals-agent", { type: "api", key: bearer });
  let store = new BodyLeaseStore(join(directory, "body"));
  let registry = new GameExtensionRegistry();
  const failures: unknown[] = [];
  const install = () =>
    loadGameExtensionModules({
      entries: [{ module: extensionModule, options: { url } }],
      registry,
      leases: store,
      stateRoot: directory,
      credentials,
      onError: (_module: string, error: unknown) => failures.push(error),
    });
  let installed = await install();
  assert.deepEqual(failures, []);
  const state = async () => (await registry.catalog()).extensions[0]?.status.state;
  /** The sitting's local lifecycle has ended, confirmed or not. */
  const settled = async () => {
    const deadline = Date.now() + 10_000;
    while (!["idle", "uncertain", undefined].includes(await state()) && Date.now() < deadline) await sleep(25);
    await sleep(10);
  };
  function stopped() {
    status.session!.phase = "stopped";
    status.session!.endedAt = Date.now() / 1000;
  }
  cleanups.push(async () => {
    // Own fixture only: settle its native receipt or let failed transport retain recovery.
    unavailable = true;
    await settled();
    store.close();
    server.closeAllConnections();
    await new Promise<void>((done, reject) => server.close((error) => (error ? reject(error) : done())));
    await rm(directory, { recursive: true, force: true });
  });
  /** Clankie's own path: the `rivals` captain tool bound to the turn's identity. */
  const call = async (input: unknown, identity?: Identity) => {
    const tool = registry.projections().flatMap((projection) =>
      projection.tools(identity === undefined ? {} : { bodyIdentity: identity }),
    )[0];
    assert.ok(tool, "rivals tool is registered");
    return (await tool.execute("call", input, undefined, undefined, {})).details;
  };
  const recover = () =>
    new BodyLeaseRouter(store).recover(owner(), "play", async (guard) => {
      const result = await recoverExternalPlay(installed, registry, guard);
      return result ?? false;
    });
  return {
    directory,
    bearer,
    calls,
    call,
    recover,
    settled,
    state,
    status: () => status,
    stopped,
    store: () => store,
    registry: () => registry,
    denyStop: () => (denyStop = true),
    loseStart: () => (lostStart = true),
    holdStart: () => (heldStart = true),
    fail: () => (unavailable = true),
    available: () => (unavailable = false),
    cleanupOnStop: () => (cleanupOnStop = true),
    replace: () => {
      status.session = { ...status.session!, id: "b".repeat(32), requestId: "replacement" };
    },
    async restart(nextUrl?: string) {
      await settled();
      store.close();
      store = new BodyLeaseStore(join(directory, "body"));
      registry = new GameExtensionRegistry();
      if (nextUrl !== undefined) url = nextUrl;
      installed = await install();
    },
  };
}

test("registers inertly, reads replay status without starting, and excludes another game's play lease", async () => {
  const f = await fixture();
  const [entry] = (await f.registry().catalog()).extensions;
  assert.equal(entry?.id, "rivals");
  assert.deepEqual(entry?.connector, { kind: "skill", sessionServer: "rivals-agent" });
  assert.equal(entry?.status.state, "idle");
  assert.equal(f.calls.length, 0);
  const read = await f.call({ action: "status" });
  assert.equal(read.execution, "replay");
  assert.equal(read.session, null);
  assert.equal((await f.call(start)).outcome, "refused");
  assert.equal(f.store().status("play"), undefined);
  const pokemon = f.store().acquire("play", "pokemon", 30_000);
  assert.equal((await f.call(start, owner())).reason, "play_session_active");
  assert.equal(f.calls.filter((call) => call.path === "/v1/start").length, 0);
  f.store().release(pokemon.lease);
  const started = await f.call(start, owner());
  assert.equal(started.outcome, "ok");
  assert.equal(started.execution, "replay");
  assert.equal((started.session as { phase: string }).phase, "starting");
  assert.equal(f.store().acquire("play", "minecraft", 30_000).outcome, "busy");
  await assert.rejects(f.registry().unregister("rivals"), /game_extension_busy/u);
  f.stopped();
  await f.settled();
  assert.equal(f.store().status("play"), undefined);
  await f.registry().unregister("rivals");
  assert.deepEqual(f.registry().projections(), []);
});

test("scopes stop and steering to the authenticated original owner and waits for endedAt cleanup", async () => {
  const f = await fixture();
  await f.call(start, owner());
  const id = f.status().session!.id;
  f.status().session!.phase = "running";
  await poll(f.state, "running");
  assert.equal((await f.call({ action: "stop", sessionId: id }, owner("other"))).reason, "not_authorized");
  assert.equal(
    (await f.call({ action: "stop", sessionId: "b".repeat(32) }, owner())).reason,
    "not_authorized",
  );
  const steered = await f.call(
    { action: "objective", sessionId: id, objective: { mode: "disengage", note: "context" } },
    owner(),
  );
  assert.equal(steered.noteApplied, false);
  assert.equal((await f.call({ action: "stop", sessionId: id }, owner())).stop, "requested");
  await poll(() => f.calls.filter((call) => call.path === "/v1/stop").length, 1);
  // Native terminal phase alone precedes release; the lease must still exclude others.
  f.status().session!.phase = "stopped";
  await sleep(300);
  assert.equal(f.store().acquire("play", "pokemon", 30_000).outcome, "busy");
  f.stopped();
  await f.settled();
  assert.ok(f.calls.filter((call) => call.path === "/v1/stop").every((call) => call.input.sessionId === id));
  assert.equal(f.store().status("play"), undefined);
  const saved = await readFile(join(f.directory, "game-extensions", "rivals", "session.json"), "utf8");
  assert.ok(!saved.includes(f.bearer));
});

test("denied stop retains uncertainty; exact original receipt recovers after a real ledger restart", async () => {
  const f = await fixture();
  await f.call(start, owner());
  const id = f.status().session!.id;
  f.denyStop();
  await f.call({ action: "stop", sessionId: id }, owner());
  await f.settled();
  assert.equal(f.store().status("play")?.state, "recovery_required");
  await f.restart();
  assert.equal(await f.state(), "uncertain");
  assert.equal((await f.recover()).reason, "recovery_required");
  assert.equal(f.store().acquire("play", "minecraft", 30_000).outcome, "busy");
  f.stopped();
  assert.equal((await f.recover()).outcome, "released");
  assert.equal(await f.state(), "idle");
});

test("lost HTTP reply persists original nonce; recovery never starts again or stops a replacement", async () => {
  const f = await fixture();
  f.loseStart();
  assert.equal((await f.call(start, owner())).reason, "rivals_start_unconfirmed");
  await f.settled();
  await f.restart();
  f.replace();
  assert.equal((await f.recover()).reason, "recovery_required");
  assert.equal(f.calls.filter((call) => call.path === "/v1/stop").length, 0);
  assert.equal(f.calls.filter((call) => call.path === "/v1/start").length, 1);
  assert.equal(f.store().status("play")?.state, "recovery_required");
});

test("lost start reply can recover only its persisted original request and real cleanup receipt", async () => {
  const f = await fixture();
  f.loseStart();
  await f.call(start, owner());
  await f.settled();
  await f.restart();
  f.cleanupOnStop();
  assert.equal((await f.recover()).outcome, "released");
  assert.equal(f.calls.filter((call) => call.path === "/v1/start").length, 1);
});

test("an actual HTTP start deadline retains ownership until the original post-cleanup receipt", async () => {
  const f = await fixture();
  f.holdStart();
  assert.equal((await f.call(start, owner())).reason, "rivals_start_unconfirmed");
  await f.settled();
  assert.equal(f.store().status("play")?.state, "recovery_required");
  assert.equal(f.store().acquire("play", "pokemon", 30_000).outcome, "busy");
  await f.restart();
  f.stopped();
  assert.equal((await f.recover()).outcome, "released");
  assert.equal(f.calls.filter((call) => call.path === "/v1/start").length, 1);
});

test("failed cleanup and replay replacing the original live execution cannot release its claim", async () => {
  const f = await fixture();
  f.status().execution = "live";
  await f.call(start, owner());
  f.status().session!.phase = "failed";
  f.status().session!.error = "release_failed";
  f.status().session!.endedAt = Date.now() / 1000;
  await f.settled();
  await f.restart();
  assert.equal((await f.recover()).reason, "recovery_required");
  f.stopped();
  f.status().session!.error = null;
  f.status().execution = "replay";
  assert.equal((await f.recover()).reason, "recovery_required");
  assert.equal(f.store().status("play")?.state, "recovery_required");
});

test("changed configuration never redirects recovery; a revoked final dispatch sends no start", async () => {
  const f = await fixture();
  let current = true;
  const identity = {
    ...owner(),
    current: () => current,
    authorize: async () => {
      current = false;
      return true;
    },
  };
  assert.equal((await f.call(start, identity)).outcome, "refused");
  assert.equal(f.calls.length, 0);
  await f.call(start, owner());
  f.fail();
  await f.settled();
  f.available();
  await f.restart("http://127.0.0.1:1");
  f.stopped();
  assert.equal((await f.recover()).outcome, "released");
});

test("operator HTTP and captain tools bind the owner; removal removes both projections", async () => {
  const f = await fixture();
  const [projection] = f.registry().projections();
  assert.deepEqual(projection?.paths, ["/v1/rivals"]);
  const post = (input: unknown, identity?: Identity) =>
    projection!
      .routes({ settings: {}, authorize: async () => identity })
      .fetch(
        new Request("http://clankie.local/v1/rivals", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(input),
        }),
      );
  assert.equal((await post(start)).status, 401);
  assert.equal(f.calls.length, 0);
  assert.equal((await post({ action: "stop", sessionId: "wrong" }, owner())).status, 400);
  const result = (await (await post(start, owner())).json()) as { session: { id: string } };
  const stopped = await f.call({ action: "stop", sessionId: result.session.id }, owner("other"));
  assert.equal(stopped.reason, "not_authorized");
  f.stopped();
  await f.settled();
  await f.registry().unregister("rivals");
  assert.deepEqual(f.registry().projections(), []);
  assert.equal(f.store().status("play"), undefined);
});

test("the original captured grant survives its admitting turn but revoked authority retains ownership", async () => {
  const f = await fixture();
  let current = true;
  let allowed = true;
  const identity = { ...owner(), current: () => current, authorize: async () => allowed };
  await f.call(start, identity);
  current = false; // Admission turn is finished; the captured sitting remains owned.
  f.status().session!.phase = "running";
  await poll(f.state, "running");
  assert.equal(f.store().acquire("play", "minecraft", 30_000).outcome, "busy");
  allowed = false;
  await f.settled();
  assert.equal(f.store().status("play")?.state, "recovery_required");
  assert.equal(await f.state(), "uncertain");
});
