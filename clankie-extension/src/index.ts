import type { GameExtension, GameExtensionModuleHost, GameExtensionModuleProjection } from "@clankie/extension";
import { RivalsService, type RivalsRuntime, type RivalsStart } from "./service.ts";

/**
 * Clankie's Rivals game extension. Clankie loads this module from the owner's
 * `gameplay.extensions` setting (`clankie games extensions add PATH url=ORIGIN`)
 * and supplies every runtime capability through its host; this module imports
 * only types from Clankie. See ../README.md.
 */
export const gameExtensionApis = [1] as const;

export interface RivalsOptions {
  /** The session server's HTTP(S) origin, e.g. `http://127.0.0.1:4330/`. */
  readonly url?: string;
}

export const gameExtension: GameExtension<RivalsStart, void, RivalsOptions, GameExtensionModuleHost> & {
  create(host: GameExtensionModuleHost): RivalsRuntime;
} = {
  contractVersion: 1,
  id: "rivals",
  connector: { kind: "skill", sessionServer: "rivals-agent" },
  skill: { name: "rivals", path: "clankie-extension/skill/SKILL.md" },
  settings: {
    key: "gameplay.extensions",
    schema: {
      parse(input: unknown): RivalsOptions {
        const url = (input as { url?: unknown } | null)?.url;
        if (url !== undefined && typeof url !== "string") throw new Error("rivals_url_invalid");
        return url === undefined ? {} : { url };
      },
    },
  },
  activity: null,
  create(host) {
    return new RivalsService(host).createRuntime();
  },
};

export function projectGameExtension(runtime: RivalsRuntime): GameExtensionModuleProjection {
  runtime.service.attach(runtime);
  return runtime.service.projection();
}
