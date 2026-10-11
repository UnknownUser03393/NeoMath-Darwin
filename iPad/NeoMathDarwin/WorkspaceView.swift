import SwiftUI

struct WorkspaceView: View {
    @Namespace private var toolSelection
    @Namespace private var themeSelection
    @StateObject private var store = NotebookStore()
    @State private var screen = "documents"
    @State private var writingName: String?
    @State private var layoutTier = 2
    @State private var liveCompletionRequest = 0
    @State private var viewMode = "Live Preview"
    @State private var tool = "Select"
    @State private var selectedCell: UUID?
    @State private var selectedRelation = false
    @State private var editingCell: UUID?
    @State private var mathEditingCell: UUID?
    @State private var inspecting = false
    @State private var expandedInspector = false
    @State private var pinnedCell: UUID?
    @State private var pinnedRelation = false
    @FocusState private var focusedCell: UUID?
    @State private var documentFocusedCell: UUID?
    @State private var history: [Notebook] = []
    @State private var future: [Notebook] = []
    @State private var zoom: CGFloat = 1
    @State private var viewport: CGPoint = .zero
    @State private var fitRequest = 0
    @State private var grid = false
    @State private var importing = false
    @State private var exporting = false
    @State private var exportFile = NotebookFile(data: Data())
    @State private var settings = false
    @State private var documentEditing = false
    @State private var actionsCollapsed = false
    @State private var transformCell: UUID?
    @State private var rename = false
    @State private var newTitle = ""
    @AppStorage("darwin.appearance") private var appearance = "system"
    @AppStorage("darwin.fingerDrawing") private var fingerDrawing = false
    @Environment(\.colorScheme) private var colorScheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        GeometryReader { geometry in
            VStack(spacing: 0) {
                if settings { settingsPage }
                else if screen == "documents" { documentsPage }
                else if screen == "writing" { WritingWorkspace(initialName: writingName) { screen = "documents" } }
                else if let doc = store.current { documentPage(doc, size: geometry.size) }
            }
            .id(settings ? "settings" : screen)
            .transition(reduceMotion ? .identity : .move(edge: screen == "documents" && !settings ? .leading : .trailing))
            .onAppear { updateTier(geometry.size.width) }
            .onChange(of: geometry.size.width) { _, width in updateTier(width) }
            .background(DarwinTheme.canvas)
            .foregroundStyle(DarwinTheme.ink)
            .animation(reduceMotion ? nil : DarwinMotion.panel, value: inspecting)
            .animation(reduceMotion ? nil : DarwinMotion.page, value: viewMode)
            .animation(reduceMotion ? nil : DarwinMotion.panel, value: actionsCollapsed)
            .animation(reduceMotion ? nil : DarwinMotion.panel, value: documentEditing)
            .animation(reduceMotion ? nil : DarwinMotion.panel, value: expandedInspector)
            .animation(reduceMotion ? nil : DarwinMotion.panel, value: tool)
        }
        .animation(reduceMotion ? nil : DarwinMotion.page, value: screen)
        .animation(reduceMotion ? nil : DarwinMotion.page, value: settings)
        .tint(DarwinTheme.accent)
        .preferredColorScheme(appearance == "system" ? nil : appearance == "dark" ? .dark : .light)
        .fileExporter(isPresented: $exporting, document: exportFile, contentType: .data, defaultFilename: store.current?.backendName ?? ((store.current?.id.uuidString ?? "NeoMath") + ".nm")) { result in
            if case .failure(let error) = result { store.error = error.localizedDescription }
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.json, .data]) { result in
            do {
                let url = try result.get(); let scoped = url.startAccessingSecurityScopedResource()
                defer { if scoped { url.stopAccessingSecurityScopedResource() } }
                if ["hw", "xdlt"].contains(url.pathExtension.lowercased()) {
                    let source = try String(contentsOf: url, encoding: .utf8)
                    let name = UUID().uuidString + ".xdlt"
                    Task { do { _ = try await BackendClient().call("saveXdltDocument", ["name": name, "source": source]); writingName = name; screen = "writing" } catch { store.error = error.localizedDescription } }
                } else { add(try DocumentTransfer.read(Data(contentsOf: url))) }
            } catch { store.error = "Import failed: \(error.localizedDescription)" }
        }
        .alert("NeoMath", isPresented: Binding(get: { store.error != nil }, set: { if !$0 { store.error = nil } })) {
            Button("OK") { store.error = nil }
        } message: { Text(store.error ?? "") }
        .alert("Rename document", isPresented: $rename) {
            TextField("Title", text: $newTitle)
            Button("Cancel", role: .cancel) { }
            Button("Rename") { mutate { $0.title = newTitle } }
        }
        .sheet(isPresented: $documentEditing) {
            if let doc = store.current { NavigationStack { documentEditor(doc).navigationTitle("Edit document").navigationBarTitleDisplayMode(.inline) }.presentationDetents([.large]) }
        }
        .sheet(isPresented: Binding(get: { transformCell != nil }, set: { if !$0 { transformCell = nil } })) {
            if let doc = store.current, let id = transformCell {
                TransformPalette(doc: doc, trace: store.result, selected: id) { intent, argument in
                    let previous = store.current
                    let applied = await store.transform(cellID: id, intent: intent, argument: argument)
                    if applied { if let previous { history.append(previous); future = [] }; transformCell = nil }
                    return applied
                }
            }
        }
        .onChange(of: editingCell) { _, id in DispatchQueue.main.async { focusedCell = id } }
        .task {
            #if DEBUG
            if ProcessInfo.processInfo.arguments.contains("--preview-canvas"), let id = store.documents.first?.id {
                open(id); viewMode = "Canvas"
                if ProcessInfo.processInfo.arguments.contains("--preview-expanded") { expandedInspector = true }
                try? await Task.sleep(for: .milliseconds(600))
                firstFault()
            }
            #endif
        }
    }

    private var documentsPage: some View {
        DarwinDocuments(documents: store.documents, onOpen: open, onExample: { add(Notebook.example($0)) }, onNew: {
            add(Notebook(title: "Untitled derivation", cells: [Cell(source: "x = 1")]))
        }, onWriting: { name in writingName = name; screen = "writing" }, onImport: { importing = true }, onSettings: { settings = true }, onRefresh: { Task { await store.refreshRemote() } })
        .task { await store.refreshRemote() }
    }

    private func documentPage(_ doc: Notebook, size: CGSize) -> some View {
        let docked = layoutTier >= 2
        let fullInspector = inspecting && (layoutTier == 0 || (layoutTier == 1 && expandedInspector && (size.height - 100) * 0.55 - (viewMode == "Canvas" ? 124 : 0) < 280))
        return VStack(spacing: 0) {
            header(doc, width: size.width)
            ZStack(alignment: .bottom) {
                if fullInspector {
                    VStack(spacing: 0) {
                        DarwinButton(title: "Back to canvas", icon: "chevron.left") { inspecting = false }.frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 12)
                        DarwinInspector(doc: doc, trace: store.result, selected: pinnedCell ?? selectedCell, relation: pinnedCell == nil ? selectedRelation : pinnedRelation, pinned: pinnedCell != nil,
                            onPin: { if pinnedCell == nil { pinnedCell = selectedCell; pinnedRelation = selectedRelation } else { pinnedCell = nil } }, onClose: { inspecting = false }, onEdit: { inspecting = false; editingCell = pinnedCell ?? selectedCell; if viewMode == "Steps" { documentEditing = true; focusedCell = editingCell } }, onTransform: { id, _ in transformCell = id }, onGoFault: firstFault)
                    }
                } else {
                HStack(spacing: 0) {
                    VStack(spacing: 0) {
                        if viewMode == "Canvas" { spatialDocument(doc, bottomInset: inspecting && !docked ? (expandedInspector ? max(280, min(size.height * 0.45, size.height - 280)) + 84 : 84) : 12) }
                        else if viewMode == "Live Preview" { LiveEditor(doc: doc, trace: store.result, changed: { value, composing in
                            store.composing = composing
                            mutate { $0.cells = LiveSource.apply(value, to: $0.cells) }
                            if !composing && store.autoCheck { store.check() }
                        }, inspect: select, complete: { transformCell = $0 }, activeChanged: { id in if store.current?.cells.contains(where: { $0.id == id }) == true { selectedCell = id; selectedRelation = false } }, completionRequest: liveCompletionRequest, editRequest: editingCell, didFinish: { editingCell = nil }, editEquation: { id in selectedCell = id; selectedRelation = false; mathEditingCell = id }, externallyEditing: mathEditingCell)
                            VStack(spacing: 0) {
                                if mathEditingCell == nil, let id = selectedCell ?? doc.cells.first(where: { $0.kind != "markdown" })?.id {
                                    equationActions(id).padding(.horizontal, 16)
                                }
                                if mathEditingCell == nil { HStack { Spacer(); DarwinButton(title: "Complete · Ctrl+.") { liveCompletionRequest += 1 } }.padding(.horizontal, 16) }
                            }.background(DarwinTheme.panel)
                        }
                        else { linearDocument(doc) }
                    }.frame(maxWidth: .infinity, maxHeight: .infinity)
                    if inspecting && docked {
                        DarwinInspector(doc: doc, trace: store.result, selected: pinnedCell ?? selectedCell, relation: pinnedCell == nil ? selectedRelation : pinnedRelation,
                                        pinned: pinnedCell != nil, onPin: { if pinnedCell == nil { pinnedCell = selectedCell; pinnedRelation = selectedRelation } else { pinnedCell = nil } }, onClose: { inspecting = false },
                                        onEdit: { editingCell = pinnedCell ?? selectedCell; if viewMode == "Steps" { documentEditing = true; focusedCell = editingCell } }, onTransform: { id, _ in transformCell = id },
                                        onGoFault: firstFault)
                            .frame(width: 344).background(DarwinTheme.canvas)
                            .overlay(alignment: .leading) { Rectangle().fill(DarwinTheme.separator).frame(width: 1) }
                            .transition(reduceMotion ? .identity : .move(edge: .trailing))
                    }
                }
                if inspecting && !docked {
                    narrowInspector(doc, available: size)
                }
                }
            }.frame(maxWidth: .infinity, maxHeight: .infinity)
            if let id = mathEditingCell, let index = doc.cells.firstIndex(where: { $0.id == id }) {
                VStack(spacing: 4) {
                    HStack {
                        Text("Step \(index + 1)").font(.subheadline.weight(.semibold)).foregroundStyle(DarwinTheme.accent)
                        Spacer()
                        DarwinButton(title: "Next step", icon: "plus") {
                            let cell = Cell(source: doc.cells[index].source)
                            mutate { $0.cells.insert(cell, at: index + 1) }
                            selectedCell = cell.id; mathEditingCell = cell.id
                        }.disabled(doc.cells[index].source.isEmpty || doc.cells[index].source.contains("□"))
                        DarwinButton(title: "Done") { store.save(); mathEditingCell = nil }
                    }
                    MathInput(source: cellBinding(id), compact: true).id(id)
                }.padding(.horizontal, 16).padding(.bottom, 8)
                    .frame(maxWidth: 800).frame(maxWidth: .infinity)
                    .background(DarwinTheme.panel)
                    .overlay(alignment: .top) { Rectangle().fill(DarwinTheme.accent.opacity(0.4)).frame(height: 1) }
            }
        }
        .sheet(isPresented: Binding(get: { viewMode == "Canvas" && editingCell != nil }, set: { if !$0 { editingCell = nil } })) {
            equationEditor(doc)
        }
    }

    private func header(_ doc: Notebook, width: CGFloat) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 4) {
                documentNavigation(doc)
                Spacer(minLength: 8)
                if !actionsCollapsed { headerActions(doc) }
                collapseActions
            }
            VStack(spacing: 0) {
                HStack { documentNavigation(doc); Spacer(); collapseActions }
                if !actionsCollapsed { HStack { Spacer(); headerActions(doc) } }
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 6)
        .background(DarwinTheme.panel)
        .overlay(alignment: .bottom) { Rectangle().fill(DarwinTheme.separator).frame(height: 1) }
    }
    private var collapseActions: some View {
        DarwinButton(title: "", icon: actionsCollapsed ? "chevron.down" : "chevron.up") { actionsCollapsed.toggle() }
            .accessibilityLabel(actionsCollapsed ? "Expand document actions" : "Collapse document actions")
    }
    private func documentNavigation(_ doc: Notebook) -> some View {
        HStack(spacing: 4) {
            DarwinButton(title: "Documents", icon: "chevron.left") { store.save(); screen = "documents" }
            Menu {
                Button("Rename") { newTitle = doc.title; rename = true }
                Button("Export notebook") { export(doc) }
                Button("Edit document") { documentEditing.toggle() }
                Button("Settings") { settings = true }
            } label: {
                HStack(spacing: 6) { Text(doc.title).font(.system(size: 17, weight: .semibold)).lineLimit(1); Image(systemName: "chevron.down").font(.caption2) }
                    .foregroundStyle(DarwinTheme.ink).frame(minHeight: 44)
            }
        }
    }
    private func headerActions(_ doc: Notebook) -> some View {
        HStack(spacing: 2) {
            Menu {
                ForEach(["Live Preview", "Canvas", "Steps"], id: \.self) { mode in Button(mode) { editingCell = nil; mathEditingCell = nil; viewMode = mode } }
            } label: {
                HStack(spacing: 8) { Text(viewMode); Image(systemName: "chevron.down").font(.caption2) }
                    .font(.system(size: 13, weight: .medium)).padding(.horizontal, 12).frame(height: 44)
                    .foregroundStyle(DarwinTheme.ink).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 10))
            }
            DarwinButton(title: "", icon: "arrow.uturn.backward") { undo() }.disabled(history.isEmpty).accessibilityLabel("Undo").keyboardShortcut("z")
            DarwinButton(title: "", icon: "arrow.uturn.forward") { redo() }.disabled(future.isEmpty).accessibilityLabel("Redo").keyboardShortcut("z", modifiers: [.command, .shift])
            DarwinButton(title: store.checking ? "Checking…" : "Check") { store.check() }.keyboardShortcut(.return, modifiers: .command)
            DarwinButton(title: "Inspect", selected: inspecting) { inspecting.toggle() }.keyboardShortcut("i", modifiers: [.command, .shift])
            Menu {
                Toggle("Auto check", isOn: $store.autoCheck)
                if store.checking { Button("Cancel check") { store.cancelCheck() } }
                Button("Edit document") { documentEditing.toggle() }
                Button("First fault") { firstFault() }.disabled(store.result?.steps?.contains { ["root_fault", "parse_error"].contains($0.status) } != true)
                Button(store.saving) { store.save() }.keyboardShortcut("s")
                Button("Add equation") { addCell() }
                Button("Add text note") { mutate { $0.cells.append(Cell(kind: "markdown", source: "")) } }
                Toggle("Dot grid", isOn: $grid)
            } label: { Text("More").font(.system(size: 15, weight: .medium)).frame(minWidth: 52, minHeight: 44) }
        }
    }

    private func spatialDocument(_ doc: Notebook, bottomInset: CGFloat) -> some View {
        ZStack(alignment: .bottom) {
            SpatialCanvas(world: CGSize(width: 1600, height: max(1200, CGFloat(doc.cells.count) * 112 + 200)), zoom: $zoom, viewport: $viewport,
                          fitRequest: fitRequest, fitBounds: CGSize(width: 600, height: CGFloat(doc.cells.count) * 112 + 120),
                          drawingWithFinger: fingerDrawing && ["Annotate", "Eraser", "Ink select"].contains(tool)) {
                ZStack(alignment: .topLeading) {
                    if grid { dotGrid }
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(Array(doc.cells.enumerated()), id: \.element.id) { _, cell in
                            canvasCell(cell, doc: doc)
                        }
                    }.padding(.leading, 40).padding(.top, 56)
                    InkCanvas(data: Binding(get: { store.current?.ink ?? Data() }, set: { value in mutate { $0.ink = value } }),
                              erasing: tool == "Eraser", fingerDrawing: fingerDrawing, selectingInk: tool == "Ink select")
                        .frame(width: 1600, height: max(1200, CGFloat(doc.cells.count) * 112 + 200))
                        .allowsHitTesting(["Annotate", "Eraser", "Ink select"].contains(tool))
                }.frame(width: 1600, height: max(1200, CGFloat(doc.cells.count) * 112 + 200), alignment: .topLeading)
            }.id(doc.id)
            VStack(spacing: 8) {
                if mathEditingCell == nil, tool == "Select", let id = selectedCell, doc.cells.first(where: { $0.id == id })?.kind != "markdown" {
                    equationActions(id).padding(.horizontal, 12).frame(maxWidth: 660).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
                }
                canvasTools
            }.padding(.bottom, bottomInset)
        }
    }
    private var dotGrid: some View {
        Canvas { context, size in
            for x in stride(from: 12.0, to: size.width, by: 24) {
                for y in stride(from: 12.0, to: size.height, by: 24) {
                    context.fill(Path(ellipseIn: CGRect(x: x, y: y, width: 1.5, height: 1.5)), with: .color(DarwinTheme.dot))
                }
            }
        }.allowsHitTesting(false)
    }
    private func canvasCell(_ cell: Cell, doc: Notebook) -> some View {
        let maths = doc.cells.filter { $0.kind != "markdown" }
        let index = maths.firstIndex { $0.id == cell.id }
        let result = resultAt(index)
        let strong = selectedCell == cell.id
        let weak = selectedRelation && index != nil && maths.indices.contains(index! + 1) && maths[index! + 1].id == selectedCell
        return VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 0) {
                Text(index.map { String($0 + 1) } ?? "").font(.system(size: 12)).foregroundStyle(DarwinTheme.tertiary).frame(width: 40, alignment: .trailing).padding(.trailing, 12)
                Button {
                    selectedCell = cell.id; selectedRelation = false
                    if cell.kind == "markdown" { editingCell = cell.id }
                    else { mathEditingCell = cell.id }
                } label: {
                    Group {
                        if cell.kind == "markdown" { Text(cell.source).font(.system(size: 15)) }
                        else { TypesetMath(source: cell.source.isEmpty ? "\\square" : cell.source) }
                    }
                    .padding(.horizontal, 12).padding(.vertical, 10).frame(minHeight: 56)
                    .background(strong ? DarwinTheme.accent.opacity(0.08) : .clear, in: RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(strong || weak ? DarwinTheme.accent : .clear, lineWidth: 2))
                    .opacity(weak ? 0.7 : 1)
                }.buttonStyle(.plain)
                .contextMenu {
                    Button("Inspect") { select(cell.id, relation: false) }
                    Button("Edit source") { selectedCell = cell.id; if viewMode == "Steps" { editingCell = cell.id; documentEditing = true } else { mathEditingCell = cell.id } }
                    Button("Transform") { transformCell = cell.id }
                    Button("Duplicate") { mutate { doc in if let i = doc.cells.firstIndex(where: { $0.id == cell.id }) { doc.cells.insert(Cell(kind: cell.kind, source: cell.source), at: i + 1) } } }
                    Button("Delete", role: .destructive) { remove(cell.id) }
                }
                if result?.status == "tainted", zoom >= 0.6 {
                    Label("Affected by upstream step", systemImage: "arrow.turn.down.right").font(.system(size: 13, weight: .medium)).foregroundStyle(DarwinTheme.caution).padding(.leading, 12)
                }
            }
            if let index, index + 1 < maths.count, let next = resultAt(index + 1), next.status != "valid" {
                Button { select(maths[index + 1].id, relation: true) } label: {
                    HStack(spacing: 8) {
                        Rectangle().fill(DarwinTheme.tone(next.status)).frame(width: 2, height: 28)
                        Image(systemName: next.status == "tainted" ? "arrow.turn.down.right" : "exclamationmark.circle")
                        if zoom >= 0.6 { Text(statusTitle(next)).font(.system(size: 13, weight: .medium)) }
                    }.foregroundStyle(DarwinTheme.tone(next.status)).frame(minHeight: 44).padding(.leading, 52)
                }.buttonStyle(.plain)
            } else { Spacer().frame(height: 44) }
        }.frame(height: 112, alignment: .topLeading)
    }
    private var canvasTools: some View {
        VStack(spacing: 4) {
            HStack(spacing: 2) {
                ForEach([("Annotate", "pencil.tip"), ("Eraser", "eraser"), ("Select", "cursorarrow"), ("Equation", "function")], id: \.0) { name, icon in
                    Button {
                        if name == "Equation" { tool = "Select"; if let selectedCell { editingCell = selectedCell } else { addCell() } }
                        else { tool = name; if name == "Annotate" { fingerDrawing = true } }
                    } label: {
                        HStack(spacing: 8) { Image(systemName: icon).font(.system(size: 18)); if tool == name { Text(name).font(.system(size: 15, weight: .medium)).transition(.identity) } }
                            .frame(minWidth: 44, minHeight: 44).padding(.horizontal, tool == name ? 12 : 0)
                            .foregroundStyle(tool == name ? DarwinTheme.accent : DarwinTheme.secondary)
                            .background { if tool == name { Capsule().fill(DarwinTheme.accent.opacity(0.1)).matchedGeometryEffect(id: "tool", in: toolSelection) } }
                    }.buttonStyle(DarwinPressStyle()).accessibilityLabel(name)
                }
                Menu {
                    Button("Equation") { addCell() }
                    Button("Text note") { mutate { $0.cells.append(Cell(kind: "markdown", source: "Note")) } }
                    Button("Select ink with lasso") { tool = "Ink select" }
                    Toggle("Draw with finger", isOn: $fingerDrawing)
                } label: { Image(systemName: "plus").frame(width: 44, height: 44) }
            }.padding(4).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 22))
            HStack(spacing: 2) {
                DarwinButton(title: "", icon: "minus") { zoom = max(0.25, zoom - 0.25) }.accessibilityLabel("Zoom out")
                Text("\(Int(zoom * 100))%").font(.system(size: 13).monospacedDigit()).frame(width: 44)
                DarwinButton(title: "", icon: "plus") { zoom = min(4, zoom + 0.25) }.accessibilityLabel("Zoom in")
                DarwinButton(title: "Fit") { fitRequest += 1 }
                DarwinButton(title: "Grid", selected: grid) { grid.toggle() }
            }.padding(4).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 22))
        }.fixedSize(horizontal: true, vertical: false)
    }

    private func linearDocument(_ doc: Notebook) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                ForEach(Array(doc.cells.filter { $0.kind != "markdown" }.enumerated()), id: \.element.id) { index, cell in
                    let result = resultAt(index)
                    Button { select(cell.id, relation: index > 0) } label: {
                        HStack(alignment: .top, spacing: 16) {
                            Text(String(index + 1)).font(.system(size: 12)).foregroundStyle(DarwinTheme.tertiary).frame(width: 20).padding(.top, 8)
                            VStack(alignment: .leading, spacing: 8) {
                                TypesetMath(source: cell.source, size: 26)
                                Text(result.map { index == 0 && $0.status == "valid" ? "Initial state" : statusTitle($0) } ?? "Unverified").font(.system(size: 13)).padding(.horizontal, 8).padding(.vertical, 4)
                                    .foregroundStyle(DarwinTheme.tone(result?.status ?? "unknown"))
                                    .background(DarwinTheme.tone(result?.status ?? "unknown").opacity(colorScheme == .dark ? 0.12 : 0.08), in: RoundedRectangle(cornerRadius: 10))
                                Text(index == 0 ? "Initial state — no relation to a previous step" : "Relation from Step \(index)")
                                    .font(.system(size: 12)).foregroundStyle(DarwinTheme.secondary)
                            }.frame(maxWidth: .infinity, alignment: .leading)
                        }.padding(16).background(DarwinTheme.panel, in: RoundedRectangle(cornerRadius: 14))
                            .overlay(RoundedRectangle(cornerRadius: 14).stroke(selectedCell == cell.id ? DarwinTheme.accent : DarwinTheme.separator, lineWidth: 2))
                    }.buttonStyle(DarwinPressStyle()).accessibilityLabel("Step \(index + 1): \(cell.source). \(result.map { index == 0 && $0.status == "valid" ? "Initial state" : statusTitle($0) } ?? "Unverified")")
                }
            }.padding(24).frame(maxWidth: 672).frame(maxWidth: .infinity)
        }
    }

    private func narrowInspector(_ doc: Notebook, available: CGSize) -> some View {
        VStack(spacing: 0) {
            Button { expandedInspector.toggle() } label: {
                HStack {
                    Capsule().fill(DarwinTheme.tertiary.opacity(0.35)).frame(width: 28, height: 4)
                    Text("Inspect").font(.system(size: 15, weight: .semibold))
                    if let index = doc.cells.filter({ $0.kind != "markdown" }).firstIndex(where: { $0.id == selectedCell }), let result = resultAt(index) {
                        Text("Step \(index + 1) · \(statusTitle(result))").font(.system(size: 13)).foregroundStyle(DarwinTheme.tone(result.status))
                    }
                    Spacer()
                    Image(systemName: expandedInspector ? "chevron.down" : "chevron.up")
                    Button { inspecting = false } label: { Image(systemName: "xmark").frame(width: 44, height: 44) }
                }.padding(.horizontal, 20).frame(height: 72)
            }.buttonStyle(.plain)
            if expandedInspector {
                DarwinInspector(doc: doc, trace: store.result, selected: pinnedCell ?? selectedCell, relation: pinnedCell == nil ? selectedRelation : pinnedRelation, pinned: pinnedCell != nil,
                                onPin: { if pinnedCell == nil { pinnedCell = selectedCell; pinnedRelation = selectedRelation } else { pinnedCell = nil } }, onClose: { inspecting = false },
                                onEdit: { editingCell = pinnedCell ?? selectedCell; if viewMode == "Steps" { documentEditing = true; focusedCell = editingCell } }, onTransform: { id, _ in transformCell = id }, onGoFault: firstFault)
                    .frame(height: max(280, min(available.height * 0.45, available.height - 280)))
            }
        }.background(DarwinTheme.canvas, in: UnevenRoundedRectangle(topLeadingRadius: 18, topTrailingRadius: 18))
            .overlay(alignment: .top) { Rectangle().fill(DarwinTheme.separator).frame(height: 1) }
    }

    private func equationActions(_ id: UUID) -> some View {
        EquationActions(edit: { selectedCell = id; selectedRelation = false; mathEditingCell = id }, more: { transformCell = id }) { operation, argument in
            let previous = store.current
            let applied = await store.transform(cellID: id, intent: operation, argument: argument)
            if applied, let previous {
                history.append(previous); future = []
                if let index = previous.cells.firstIndex(where: { $0.id == id }), let cells = store.current?.cells, cells.indices.contains(index + 1) {
                    selectedCell = cells[index + 1].id; selectedRelation = false
                }
            }
            return applied
        }
    }
    private func equationEditor(_ doc: Notebook) -> some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    if let id = mathEditingCell ?? editingCell, let cell = doc.cells.first(where: { $0.id == id }) {
                        if cell.kind == "markdown" {
                            TextField("Note", text: cellBinding(id), axis: .vertical).padding(16)
                        } else {
                            MathInput(source: cellBinding(id))
                        }
                    }
                }.padding(24)
            }.background(DarwinTheme.canvas).navigationTitle("Edit equation").navigationBarTitleDisplayMode(.inline)
                .toolbar { Button("Done") { store.save(); mathEditingCell = nil; editingCell = nil } }
        }.presentationDetents([.large])
    }
    private func documentEditor(_ doc: Notebook) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Title").font(.system(size: 13))
                    TextField("Title", text: Binding(get: { store.current?.title ?? "" }, set: { title in mutate { $0.title = title } }))
                        .padding(12).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 10))
                    DarwinButton(title: "Done") { documentEditing = false }
                }
                ForEach(Array(doc.cells.enumerated()), id: \.element.id) { index, cell in
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(String(index + 1)).font(.caption).frame(width: 24)
                            WritingSource(text: cell.source, selection: nil, changed: { value, composing in
                                store.composing = composing
                                mutate { doc in if let i = doc.cells.firstIndex(where: { $0.id == cell.id }) { doc.cells[i].source = value } }
                                if !composing && store.autoCheck { store.check() }
                            }, fontSize: 14, minimumHeight: cell.kind == "markdown" ? 72 : 44, focused: { documentFocusedCell = cell.id }, check: { store.check() })
                                .padding(4).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 10))
                                .accessibilityLabel(cell.kind == "markdown" ? "Text \(index + 1)" : "Equation \(index + 1)")
                            Button { remove(cell.id) } label: { Image(systemName: "xmark").frame(width: 44, height: 44).foregroundStyle(DarwinTheme.fault) }.accessibilityLabel("Delete cell \(index + 1)")
                        }
                        if cell.kind != "markdown" { TypesetMath(source: cell.source, size: 22).padding(.leading, 32) }
                    }
                }
                ForEach(Array((store.result?.steps ?? []).enumerated()).filter { ["parse_error", "unverified"].contains($0.element.status) && !$0.element.message.isEmpty }, id: \.offset) { index, result in
                    Text("Step \(index + 1): \(result.message)").font(.system(size: 13)).foregroundStyle(DarwinTheme.tone(result.status))
                }
                HStack {
                    DarwinButton(title: "+ Equation", selected: true) { mutate { $0.cells.append(Cell(source: "x = 1")) } }
                    DarwinButton(title: "+ Text", selected: true) { mutate { $0.cells.append(Cell(kind: "markdown", source: "")) } }
                    if let id = documentFocusedCell { DarwinButton(title: "Transform") { transformCell = id } }
                }
            }.padding(16)
        }.background(DarwinTheme.panel).overlay(alignment: .bottom) { Divider() }
    }
    private var settingsPage: some View {
        VStack(spacing: 0) {
            HStack { DarwinButton(title: "Back", icon: "chevron.left") { settings = false }; Spacer(); Text("NeoMath").font(.system(size: 20, weight: .semibold)) }.padding(12).background(DarwinTheme.panel)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    Text("Settings").font(.system(size: 28, weight: .semibold))
                    Text("Make NeoMath feel at home").foregroundStyle(DarwinTheme.secondary)
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Appearance").font(.headline)
                        Text("Theme · Choose a look, or follow your device.").font(.system(size: 13)).foregroundStyle(DarwinTheme.secondary)
                        HStack { ForEach([("system", "System", "desktopcomputer"), ("light", "Light", "sun.max"), ("dark", "Dark", "moon")], id: \.0) { value, title, icon in
                            Button { withAnimation(reduceMotion ? nil : DarwinMotion.panel) { appearance = value } } label: {
                                    Label(title, systemImage: icon).font(.system(size: 15, weight: .medium)).frame(maxWidth: .infinity, minHeight: 44)
                                }.buttonStyle(DarwinPressStyle())
                                .foregroundStyle(appearance == value ? DarwinTheme.ink : DarwinTheme.secondary)
                                .background { if appearance == value { RoundedRectangle(cornerRadius: 8).fill(DarwinTheme.elevated).matchedGeometryEffect(id: "theme", in: themeSelection) } }
                                .accessibilityValue(appearance == value ? "Selected" : "")
                        } }.padding(4).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 12))
                        Text("System follows your device appearance.").font(.caption).foregroundStyle(DarwinTheme.secondary)
                    }.padding(20).background(DarwinTheme.panel, in: RoundedRectangle(cornerRadius: 18))
                    VStack(alignment: .leading, spacing: 16) { Text("Backend").font(.headline); BackendSettings() }.padding(20).background(DarwinTheme.panel, in: RoundedRectangle(cornerRadius: 18))
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Input").font(.headline)
                        Toggle("Draw with finger", isOn: $fingerDrawing)
                        Text("In Canvas, choose Annotate to add handwritten notes and marks. With finger drawing enabled, one finger draws and two fingers pan; otherwise use Apple Pencil to draw.").font(.caption).foregroundStyle(DarwinTheme.secondary)
                    }.padding(20).background(DarwinTheme.panel, in: RoundedRectangle(cornerRadius: 18))
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Workspace").font(.headline)
                        Toggle("Auto check", isOn: $store.autoCheck)
                        Text("Derivations are saved on this iPad and synchronized with the configured NeoMath workspace. Math requests use Core / SymPy CAS with engine auto.").font(.caption).foregroundStyle(DarwinTheme.secondary)
                    }.padding(20).background(DarwinTheme.panel, in: RoundedRectangle(cornerRadius: 18))
                }.padding(24).frame(maxWidth: 576).frame(maxWidth: .infinity)
            }
        }
    }
    private func updateTier(_ width: CGFloat) {
        let boundaries: [CGFloat] = [600, 900, 1180]
        while layoutTier < 3 && width >= boundaries[layoutTier] + 12 { layoutTier += 1 }
        while layoutTier > 0 && width < boundaries[layoutTier - 1] - 12 { layoutTier -= 1 }
    }
    private func resultAt(_ index: Int?) -> StepResult? {
        guard let index, let steps = store.result?.steps, steps.indices.contains(index) else { return nil }; return steps[index]
    }
    private func statusTitle(_ result: StepResult) -> String {
        if result.lost?.isEmpty == false { return "Lost solution" }
        if result.gained?.isEmpty == false { return "Extraneous solution" }
        switch result.status { case "tainted": return "Affected by upstream step"; case "valid": return "Equivalent"; case "root_fault": return "Domain or solution changed"; case "parse_error": return "Syntax error"; default: return result.title.isEmpty ? "Unverified" : result.title }
    }
    private func cellBinding(_ id: UUID) -> Binding<String> { Binding(get: { store.current?.cells.first { $0.id == id }?.source ?? "" }, set: { value in mutate { doc in if let i = doc.cells.firstIndex(where: { $0.id == id }) { doc.cells[i].source = value } } }) }
    private func select(_ id: UUID, relation: Bool) { selectedCell = id; selectedRelation = relation; inspecting = true }
    private func firstFault() { guard let i = store.result?.steps?.firstIndex(where: { ["root_fault", "parse_error"].contains($0.status) }), let doc = store.current else { return }; let math = doc.cells.filter { $0.kind != "markdown" }; if math.indices.contains(i) { select(math[i].id, relation: true) } }
    private func checkpoint() { if let doc = store.current { history.append(doc); if history.count > 100 { history.removeFirst() }; future = [] } }
    private func mutate(_ change: (inout Notebook) -> Void) { guard var doc = store.current else { return }; change(&doc); guard doc != store.current else { return }; checkpoint(); store.update(doc) }
    private func undo() { guard let doc = history.popLast(), let current = store.current else { return }; future.append(current); store.update(doc); reconcileEditing(doc) }
    private func redo() { guard let doc = future.popLast(), let current = store.current else { return }; history.append(current); store.update(doc); reconcileEditing(doc) }
    private func reconcileEditing(_ doc: Notebook) {
        if let id = mathEditingCell, !doc.cells.contains(where: { $0.id == id }) { mathEditingCell = nil }
        if let id = selectedCell, !doc.cells.contains(where: { $0.id == id }) { selectedCell = doc.cells.last?.id }
    }
    private func remove(_ id: UUID) { mutate { $0.cells.removeAll { $0.id == id } }; if selectedCell == id { selectedCell = nil }; if editingCell == id { editingCell = nil } }
    private func reorder(_ id: UUID, delta: Int) { mutate { doc in if let i = doc.cells.firstIndex(where: { $0.id == id }), doc.cells.indices.contains(i + delta) { doc.cells.swapAt(i, i + delta) } } }
    private func addCell() { let cell = Cell(source: ""); mutate { $0.cells.append(cell) }; selectedCell = cell.id; editingCell = cell.id }
    private func open(_ id: UUID) { store.open(id); if let ink = store.current.flatMap(BrowserInk.migrate) { mutate { $0.ink = ink } }; resetDocument(); screen = "document" }
    private func add(_ doc: Notebook) { var doc = doc; if let ink = BrowserInk.migrate(doc) { doc.ink = ink }; store.add(doc); resetDocument(); screen = "document" }
    private func resetDocument() { mathEditingCell = nil; documentEditing = false; documentFocusedCell = nil; history = []; future = []; selectedCell = nil; selectedRelation = false; editingCell = nil; pinnedCell = nil; inspecting = false; expandedInspector = false; zoom = 1; viewport = .zero; viewMode = "Live Preview"; tool = "Select" }
    private func export(_ doc: Notebook) { do { exportFile = NotebookFile(data: try DocumentTransfer.export(doc)); exporting = true } catch { store.error = error.localizedDescription } }
}
