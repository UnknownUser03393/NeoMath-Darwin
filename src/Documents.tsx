import { useEffect, useRef, useState } from "react"
import { call, newNotebook, validNotebook, type Notebook } from "./backend"
import { useWorkspace } from "./workspace"
import { Chip, M } from "./ui"
import { transitionPage } from "./motion"

const examples = [
  {
    title: "Lost roots",
    note: "Dividing by a variable",
    lines: ["x*(x-1)=0", "x-1=0", "x=1"],
  },
  {
    title: "Squaring",
    note: "Adding a solution",
    lines: ["sqrt(x)=x-2", "x=(x-2)^2"],
  },
  {
    title: "Domain change",
    note: "Keep the original domain",
    lines: ["(x^2-1)/(x-1)=2", "x+1=2"],
  },
]
export default function Documents({
  onOpen,
  onSettings,
  onWriting,
}: {
  onOpen: () => void
  onSettings: () => void
  onWriting: (fileName: string) => void
}) {
  const workspace = useWorkspace()
  const [query, setQuery] = useState("")
  const [layout, setLayout] = useState<"list" | "grid">("list")
  const [busy, setBusy] = useState(false)
  const [writings, setWritings] = useState<import("./backend").FileMeta[]>([])
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => {
    void workspace.refresh()
    void call<{ files: import("./backend").FileMeta[] }>("listXdltDocuments").then(r => setWritings(r.files)).catch(e => workspace.setError(e.message))
  }, [])
  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    workspace.setError("")
    try {
      await action()
    } catch (e) {
      workspace.setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  const create = async (doc: Notebook) => {
    await workspace.save(doc)
    if (await workspace.open(doc)) onOpen()
  }
  const open = (name: string) =>
    run(async () => {
      const { document } = await call<{ document: Notebook }>("loadNotebook", {
        name,
      })
      if (!validNotebook(document))
        throw new Error("Unsupported or invalid notebook document")
      if (await workspace.open({ ...document, id: document.id || name, fileName: name })) onOpen()
    })
  const files = workspace.files
    .filter((f) => f.title.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => (b.updatedAt ?? 0) - (a.updatedAt ?? 0))
  return (
    <div className="flex h-dvh flex-col bg-canvas text-ink">
      <header className="material sticky top-0 z-30 flex min-h-[82px] flex-wrap items-center justify-end gap-1 border-b hairline px-3 py-4">
        <span className="mr-auto flex min-h-11 items-center px-2 text-[20px] font-semibold tracking-[-0.02em]">
          NeoMath
        </span>
        <button
          onClick={onSettings}
          className="press min-h-11 rounded-full px-3 font-medium text-accent"
        >
          Settings
        </button>
        <button
          disabled={busy}
          onClick={() => input.current?.click()}
          className="press min-h-11 rounded-full px-3 font-medium text-accent"
        >
          Import
        </button>
        <button
          disabled={busy}
          onClick={() =>
            void run(async () => {
              const name = `${crypto.randomUUID()}.xdlt`
              await call("saveXdltDocument", { name, source: "# Untitled writing\n\nWrite your mathematical document here.\n" })
              onWriting(name)
            })
          }
          className="press min-h-11 rounded-full bg-accent/10 px-4 font-medium text-accent"
        >
          New writing document
        </button>
        <button
          disabled={busy}
          onClick={() =>
            void run(() =>
              create(newNotebook("Untitled derivation", ["x = 1"])),
            )
          }
          className="press min-h-11 rounded-full bg-accent px-5 font-semibold text-onaccent"
        >
          New derivation
        </button>
        <input
          ref={input}
          type="file"
          accept=".nm,.json,.xdlt,.hw"
          className="hidden"
          aria-label="Import notebook"
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ""
            if (file)
              void run(async () => {
                if (/\.(xdlt|hw)$/i.test(file.name)) {
                  const name = `${crypto.randomUUID()}.xdlt`
                  await call("saveXdltDocument", { name, source: await file.text() }); onWriting(name); return
                }
                const doc: unknown = JSON.parse(await file.text())
                if (!validNotebook(doc))
                  throw new Error(
                    "Import requires a NeoMath .nm notebook with valid cells",
                  )
                await create({
                  ...doc,
                  id: crypto.randomUUID(),
                  fileName: `${crypto.randomUUID()}.nm`,
                  updatedAt: Date.now(),
                })
              })
          }}
        />
      </header>
      {workspace.error && (
        <div
          role="alert"
          className="flex items-center gap-3 bg-panel px-4 py-2 text-[13px] text-bad"
        >
          <span className="min-w-0 flex-1">{workspace.error}</span>
          <button
            className="min-h-11 px-3 text-accent"
            onClick={() => void workspace.refresh()}
          >
            Retry connection
          </button>
        </div>
      )}
      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 pb-16 pt-6 sm:px-6">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="mr-auto text-[28px] font-semibold tracking-[-0.02em]">
                Documents
              </h1>
              <Chip>
                {busy
                  ? "Working…"
                  : workspace.connected
                    ? "MathCore connected"
                    : "Connecting / offline"}
              </Chip>
            </div>
            <input
              aria-label="Search documents"
              placeholder="Search documents"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="min-h-11 w-full rounded-[12px] bg-subtle px-3 outline-none"
            />
          </div>
          <section className="space-y-3" aria-labelledby="examples-heading">
            <div className="px-1">
              <h2 id="examples-heading" className="text-[20px] font-semibold">
                Examples
              </h2>
              <p className="text-[13px] text-ink2">
                Open a new copy, then Check with MathCore.
              </p>
            </div>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
              {examples
                .filter((e) =>
                  e.title.toLowerCase().includes(query.toLowerCase()),
                )
                .map((example) => (
                  <button
                    key={example.title}
                    disabled={busy}
                    onClick={() =>
                      void run(() =>
                        create(newNotebook(example.title, example.lines)),
                      )
                    }
                    className="press flex flex-col gap-3 rounded-[18px] bg-panel p-4 text-left"
                  >
                    <div className="flex min-h-28 w-full flex-col justify-center gap-2 rounded-[12px] bg-subtle p-3">
                      {example.lines.map((line, i) => (
                        <M key={i} className="block text-[20px]">
                          {line}
                        </M>
                      ))}
                    </div>
                    <div>
                      <p className="font-semibold">{example.title}</p>
                      <p className="text-[13px] text-ink2">{example.note}</p>
                    </div>
                  </button>
                ))}
            </div>
          </section>
          <section className="space-y-3" aria-labelledby="writing-heading"><h2 id="writing-heading" className="text-[20px] font-semibold">Writing · XDLT</h2>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">{writings.filter(f => f.title.toLowerCase().includes(query.toLowerCase())).map(file => <button key={file.name} onClick={() => onWriting(file.fileName)} className="press rounded-[18px] bg-panel p-4 text-left"><p className="font-semibold">{file.title}</p><p className="text-[13px] text-ink2">Incremental compile and preview</p></button>)}</div>
          </section>
          <section className="space-y-3" aria-labelledby="recent-heading">
            <div className="flex items-center gap-2 px-1">
              <h2
                id="recent-heading"
                className="mr-auto text-[20px] font-semibold"
              >
                Recent
              </h2>
              <button
                onClick={() => void workspace.refresh()}
                className="press min-h-11 px-3 text-accent"
              >
                Refresh
              </button>
              <div className="flex rounded-[10px] bg-subtle p-1">
                {(["list", "grid"] as const).map((v) => (
                  <button
                    key={v}
                    aria-label={v === "list" ? "List" : "Grid"}
                    aria-pressed={layout === v}
                    className={`press min-h-11 rounded-[8px] px-3 capitalize ${
                      layout === v ? "bg-elevated" : "text-ink2"
                    }`}
                    onClick={() =>
                      transitionPage(() => setLayout(v), "forward", "content")
                    }
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
            {!files.length ? (
              <p className="px-1 text-ink2">
                {workspace.connected
                  ? "No documents found. Create a document or open an example."
                  : "Connect to NeoMath to load your workspace."}
              </p>
            ) : (
              <div
                className={
                  layout === "grid"
                    ? "grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3"
                    : "overflow-hidden rounded-[18px] bg-panel"
                }
              >
                {files.map((file) => (
                  <button
                    key={file.name}
                    disabled={busy}
                    onClick={() => void open(file.fileName)}
                    className={`press flex min-h-[76px] w-full items-center gap-3 p-4 text-left ${
                      layout === "grid"
                        ? "rounded-[18px] bg-panel"
                        : "border-b hairline"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-semibold">{file.title}</p>
                      <p className="text-[13px] text-ink2">
                        {file.updatedAt
                          ? new Date(file.updatedAt).toLocaleString()
                          : file.fileName}
                      </p>
                    </div>
                    <span className="text-ink3">›</span>
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}
