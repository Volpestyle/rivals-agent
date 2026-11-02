import { test } from "node:test";
import assert from "node:assert/strict";
import { createRivalsClient } from "../src/client.ts";

const key = "a".repeat(32);
const origin = "http://rivals.test/";

for (const publishing of ["absent", "unavailable", "requested"] as const) {
  test(`Discord share retains the watch URL when Go Live is ${publishing}`, async () => {
    const published: unknown[] = [];
    const calls: unknown[] = [];
    const client = createRivalsClient({
      host: {
        options: { url: origin },
        credential: async () => "fixture-credential",
        ...(publishing === "absent"
          ? {}
          : {
              goLive: async (input: unknown) => {
                published.push(input);
                return publishing === "requested";
              },
            }),
      },
      fetchImpl: async (input, init) => {
        calls.push({ url: String(input), body: JSON.parse(String(init?.body)) });
        return Response.json({ watchPath: `/watch?key=${key}`, framePath: `/frame.png?key=${key}` });
      },
    });
    const result = await client.call({
      action: "share",
      sessionId: "b".repeat(32),
      guildId: "123",
      channelId: "456",
    });
    assert.deepEqual(result, {
      outcome: "watch",
      watchUrl: `${origin}watch?key=${key}`,
      publishing: publishing === "requested" ? "requested" : "unavailable",
    });
    assert.deepEqual(calls, [{ url: `${origin}v1/share`, body: { sessionId: "b".repeat(32) } }]);
    assert.deepEqual(
      published,
      publishing === "absent"
        ? []
        : [{ guildId: "123", channelId: "456", snapshotUrl: `${origin}frame.png?key=${key}` }],
    );
  });
}
