import vinext from "vinext";
import { defineConfig, type Plugin } from "vite";
import hostingConfig from "./.openai/hosting.json";
import { sites } from "./build/sites-vite-plugin";

const SITE_CREATOR_PLACEHOLDER_DATABASE_ID =
  "00000000-0000-4000-8000-000000000000";

const { d1, r2 } = hostingConfig;

// macOS Seatbelt blocks FSEvents, so Codex previews need polling for HMR.
const isCodexSeatbeltSandbox = process.env.CODEX_SANDBOX === "seatbelt";
const RSC_SERVER_EDGE = "react-server-dom-webpack/server.edge";

function stabilizeRscDependencyOptimization(): Plugin {
  return {
    name: "neomath:stabilize-rsc-dependency-optimization",
    enforce: "post",
    config(config) {
      // @vitejs/plugin-rsc force-includes server.edge after user config has
      // been merged. Remove that include so the exclusion below can take
      // effect during dependency discovery and HMR re-optimization.
      const rscOptimizeDeps = config.environments?.rsc?.optimizeDeps;
      if (rscOptimizeDeps?.include) {
        rscOptimizeDeps.include = rscOptimizeDeps.include.filter(
          (dependency) => dependency !== RSC_SERVER_EDGE,
        );
      }
    },
  };
}

const localBindingConfig = {
  main: "./worker/index.ts",
  compatibility_flags: ["nodejs_compat"],
  d1_databases: d1
    ? [
        {
          binding: d1,
          database_name: "site-creator-d1",
          database_id: SITE_CREATOR_PLACEHOLDER_DATABASE_ID,
        },
      ]
    : [],
  r2_buckets: r2
    ? [
        {
          binding: r2,
          bucket_name: "site-creator-r2",
        },
      ]
    : [],
};

export default defineConfig(async () => {
  // Keep Wrangler and Miniflare state project-local. These are non-secret tool
  // settings; application environment belongs in ignored `.env*` files.
  process.env.WRANGLER_WRITE_LOGS ??= "false";
  process.env.WRANGLER_LOG_PATH ??= ".wrangler/logs";
  process.env.MINIFLARE_REGISTRY_PATH ??= ".wrangler/registry";

  // Wrangler snapshots its log path while the Cloudflare plugin is imported.
  const { cloudflare } = await import("@cloudflare/vite-plugin");

  return {
    // Vite 8's RSC optimizer can invalidate this generated entry while the
    // Cloudflare runner still holds its versioned URL, producing ENOENT from
    // node_modules/.vite/deps_rsc during hot reloads. Let vinext resolve the
    // server entry directly instead of caching it as an optimized dependency.
    optimizeDeps: {
      exclude: [RSC_SERVER_EDGE],
    },
    server: isCodexSeatbeltSandbox
      ? { watch: { useFsEvents: false, usePolling: true } }
      : undefined,
    plugins: [
      vinext(),
      sites(),
      cloudflare({
        viteEnvironment: { name: "rsc", childEnvironments: ["ssr"] },
        config: localBindingConfig,
      }),
      stabilizeRscDependencyOptimization(),
    ],
  };
});
