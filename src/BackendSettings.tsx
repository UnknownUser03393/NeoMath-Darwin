import { useEffect, useState } from "react"
import { call } from "./backend"
interface Settings {
  qwenConfigured: boolean
  qwenModel: string
  autosaveSeconds: number
  dataDir: string
}
export default function BackendSettings() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    void call<Settings>("getSettings")
      .then(setSettings)
      .catch((e) => setMessage(e.message))
  }, [])
  return (
    <section className="space-y-3" aria-labelledby="backend-heading">
      <h2 id="backend-heading" className="px-1 text-[17px] font-semibold">
        NeoMath backend
      </h2>
      <form
        className="space-y-4 rounded-[18px] bg-panel p-5 text-[13px]"
        onSubmit={(e) => {
          e.preventDefault()
          if (!settings) return
          setBusy(true)
          setMessage("")
          void call<Settings>("saveSettings", {
            qwen_model: settings.qwenModel,
          })
            .then((result) => {
              setSettings(result)
              setMessage("Backend settings saved")
            })
            .catch((e) => setMessage(e.message))
            .finally(() => setBusy(false))
        }}
      >
        {settings && (
          <>
            <p className="break-all">Workspace: {settings.dataDir}</p>
            <p>
              AI: {settings.qwenConfigured ? "Configured" : "Offline fallback"}
            </p>
            <label className="block">
              AI model
              <input
                required
                value={settings.qwenModel}
                onChange={(e) =>
                  setSettings({ ...settings, qwenModel: e.target.value })
                }
                className="mt-2 min-h-11 w-full rounded-[10px] bg-subtle px-3"
              />
            </label>
            <button
              disabled={busy}
              className="press min-h-11 rounded-full bg-accent/10 px-4 text-accent"
            >
              Save backend settings
            </button>
          </>
        )}
        {message && <p role="status">{message}</p>}
      </form>
    </section>
  )
}
