import Cocoa

// Standalone debug viewer for the Daisy clips. Build and run with:
//
//     ./tools/preview.sh
//
// It compiles against the REAL Sources/DaisyFrames.swift and Sources/DaisyRender.swift, so what you
// see here is what the menu bar will show. If a clip looks wrong in this window it is wrong in the
// app, not wrong in the preview.
//
// Shows every clip simultaneously, each in three renderings:
//   * ACTUAL   - at daisyPointHeight, on light and dark strips, exactly menu-bar size
//   * ZOOMED   - 6x nearest-neighbour, to inspect individual pixels
//   * TEMPLATE - the System-mode variant, on light and dark, to check the punch-outs read
//
// Controls:  space = pause/resume · left/right = step one frame while paused
//            G = toggle a per-frame grid · S = save a PNG contact sheet to art/preview/

private let ZOOM: CGFloat = 5
private let ROW_PAD: CGFloat = 16
private let LABEL_W: CGFloat = 78
private let HEADER_H: CGFloat = 34

private struct Row {
    let anim: DaisyAnimation
    var tick: Int = 0
}

final class PreviewView: NSView {
    private var rows: [Row]
    private var paused = false
    private var showGrid = false
    private var lastStep: [String: TimeInterval] = [:]
    private var timer: Timer?

    // Clips in the order they matter for the app's state machine, not alphabetically.
    private static let order = ["sleep", "drowsy", "alert", "yawn",
                                "trot", "zoomies", "dig", "sniff",
                                "ask", "wag"]

    override init(frame: NSRect) {
        rows = PreviewView.order.compactMap(DaisyAnimation.init).map { Row(anim: $0) }
        super.init(frame: frame)
        timer = Timer.scheduledTimer(withTimeInterval: 1.0 / 60.0, repeats: true) { [weak self] _ in
            self?.step()
        }
    }

    required init?(coder: NSCoder) { fatalError() }

    override var acceptsFirstResponder: Bool { true }

    /// Frames a finished one-shot is held on before the preview replays it.
    ///
    /// Keep this small. At 6 it made `alert` - two frames at 1.4 fps - dwell on its final frame for
    /// about five seconds against 0.7 s on the first, so the ear-perk looked like a static image.
    private static let replayHold = 2

    private func step() {
        guard !paused else { return }
        let now = Date().timeIntervalSince1970
        var dirty = false
        for i in rows.indices {
            let anim = rows[i].anim
            let interval = 1.0 / anim.fps
            let last = lastStep[anim.name] ?? 0
            if now - last >= interval {
                lastStep[anim.name] = now
                rows[i].tick += 1
                // A one-shot holds its final frame forever, which in a preview just looks like a
                // static image - it's why `alert` and `yawn` appeared to have no movement at all.
                // In the app the driver hands back to an idle clip instead; here, replay it.
                if !anim.loops, rows[i].tick >= anim.frameCount + PreviewView.replayHold {
                    rows[i].tick = 0
                }
                dirty = true
            }
        }
        if dirty { needsDisplay = true }
    }

    var rowHeight: CGFloat { CGFloat(daisyCanvas.h) * ZOOM + ROW_PAD }

    /// Full content size. Taller than any display once every clip is listed, so the caller puts this
    /// inside a scroll view rather than trying to size a window to it.
    var idealSize: NSSize {
        let canvasW = CGFloat(daisyCanvas.w) * ZOOM
        let cell = daisyPointHeight * 2 + 20
        let w = LABEL_W + canvasW + 30 + canvasW + 34 + (cell + 10) * 4 + 24
        return NSSize(width: w, height: rowHeight * CGFloat(rows.count) + HEADER_H + 18)
    }

    override func keyDown(with e: NSEvent) {
        switch e.charactersIgnoringModifiers?.lowercased() {
        case " ":
            paused.toggle()
            needsDisplay = true
        case "g":
            showGrid.toggle()
            needsDisplay = true
        case "s":
            saveContactSheet()
        default:
            if e.keyCode == 124 { nudge(1) }       // right arrow
            else if e.keyCode == 123 { nudge(-1) } // left arrow
            else { super.keyDown(with: e) }
        }
    }

    private func nudge(_ d: Int) {
        paused = true
        for i in rows.indices {
            rows[i].tick = max(0, rows[i].tick + d)
        }
        needsDisplay = true
    }

    // MARK: - Drawing

    override func draw(_ dirtyRect: NSRect) {
        NSColor(white: 0.13, alpha: 1).setFill()
        dirtyRect.fill()
        NSGraphicsContext.current?.imageInterpolation = .none

        drawHeader()

        var y = bounds.height - HEADER_H
        for row in rows {
            y -= rowHeight
            draw(row: row, atY: y)
        }
    }

    private func drawHeader() {
        let mode = paused ? "PAUSED — space resume, arrows step" : "playing — space pause"
        let text = "\(rows.count) clips · canvas \(daisyCanvas.w)x\(daisyCanvas.h) logical px · "
            + "menu bar height \(String(format: "%g", daisyPointHeight)) pt · \(mode) · G grid · S save"
        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedSystemFont(ofSize: 11, weight: .regular),
            .foregroundColor: NSColor(white: 0.62, alpha: 1),
        ]
        NSAttributedString(string: text, attributes: attrs)
            .draw(at: NSPoint(x: 14, y: bounds.height - 22))
    }

    private func draw(row: Row, atY y: CGFloat) {
        let anim = row.anim
        let idx = anim.frameIndex(forTick: row.tick)
        let canvasW = CGFloat(daisyCanvas.w) * ZOOM
        let canvasH = CGFloat(daisyCanvas.h) * ZOOM

        // label
        let meta = "\(anim.name)\n\(anim.frameCount)f @\(String(format: "%g", anim.fps))\n"
            + (anim.loops ? "loop" : "once") + (anim.intro > 0 ? "\nintro \(anim.intro)" : "")
            + "\n#\(idx)"
        NSAttributedString(string: meta, attributes: [
            .font: NSFont.monospacedSystemFont(ofSize: 9, weight: .medium),
            .foregroundColor: NSColor(white: 0.78, alpha: 1),
        ]).draw(in: NSRect(x: 10, y: y, width: LABEL_W - 12, height: canvasH))

        var x = LABEL_W

        // Clip widths differ (each clip is trimmed to its own content), so the rect is derived from
        // the image's own aspect. Forcing every clip into one width would stretch the narrow ones.
        // zoomed colour
        if let img = anim.image(frame: idx, colour: .orange, pointHeight: CGFloat(daisyCanvas.h)) {
            let r = NSRect(x: x, y: y, width: img.size.width * ZOOM, height: canvasH)
            NSColor(white: 0.22, alpha: 1).setFill()
            NSRect(x: x, y: y, width: canvasW, height: canvasH).fill()
            img.draw(in: r, from: .zero, operation: .sourceOver, fraction: 1)
            if showGrid { drawGrid(in: r) }
        }
        x += canvasW + 30

        // zoomed template, rendered onto mid grey so the punch-outs are visible
        if let img = anim.image(frame: idx, colour: nil, pointHeight: CGFloat(daisyCanvas.h)) {
            let r = NSRect(x: x, y: y, width: img.size.width * ZOOM, height: canvasH)
            NSColor(white: 0.55, alpha: 1).setFill()
            NSRect(x: x, y: y, width: canvasW, height: canvasH).fill()
            NSColor.black.set()
            img.draw(in: r, from: .zero, operation: .sourceOver, fraction: 1)
            if showGrid { drawGrid(in: r) }
        }
        x += canvasW + 34

        // actual size, four combinations: colour and template, each on light and dark
        let cell = daisyPointHeight * 2 + 20
        // `isDark` is carried explicitly rather than derived from the colour: NSColor(white:alpha:)
        // lives in a greyscale space, and asking such a colour for .brightnessComponent raises.
        let variants: [(label: String, colour: NSColor?, bg: CGFloat, isDark: Bool)] = [
            ("colour/light", .orange, 0.93, false),
            ("colour/dark", .orange, 0.16, true),
            ("tmpl/light", nil, 0.93, false),
            ("tmpl/dark", nil, 0.16, true),
        ]
        for (label, colour, bg, isDark) in variants {
            let strip = NSRect(x: x, y: y + canvasH / 2 - cell / 2, width: cell, height: cell)
            NSColor(white: bg, alpha: 1).setFill()
            strip.fill()
            if var img = anim.image(frame: idx, colour: colour, pointHeight: daisyPointHeight) {
                // A template NSImage is recoloured by AppKit only inside menu-bar/button cells;
                // drawing one directly just renders its own black pixels, which is invisible on a
                // dark strip. So tint it explicitly to mimic what the real menu bar will do.
                if colour == nil {
                    img = PreviewView.tinted(img, isDark ? .white : .black)
                }
                let p = NSPoint(x: strip.midX - img.size.width / 2, y: strip.midY - img.size.height / 2)
                img.draw(at: p, from: .zero, operation: .sourceOver, fraction: 1)
            }
            NSAttributedString(string: label, attributes: [
                .font: NSFont.monospacedSystemFont(ofSize: 8, weight: .regular),
                .foregroundColor: NSColor(white: 0.5, alpha: 1),
            ]).draw(at: NSPoint(x: strip.minX, y: strip.minY - 11))
            x += cell + 10
        }
    }

    /// Recolour a template image's ink, preserving its alpha (and therefore its punched-out holes).
    static func tinted(_ src: NSImage, _ colour: NSColor) -> NSImage {
        let out = NSImage(size: src.size)
        out.lockFocus()
        NSGraphicsContext.current?.imageInterpolation = .none
        let r = NSRect(origin: .zero, size: src.size)
        src.draw(in: r, from: .zero, operation: .sourceOver, fraction: 1)
        colour.set()
        r.fill(using: .sourceAtop)
        out.unlockFocus()
        return out
    }

    private func drawGrid(in r: NSRect) {
        NSColor(white: 1, alpha: 0.13).setStroke()
        let p = NSBezierPath()
        p.lineWidth = 0.5
        for i in 0...daisyCanvas.w {
            let gx = r.minX + CGFloat(i) * ZOOM
            p.move(to: NSPoint(x: gx, y: r.minY)); p.line(to: NSPoint(x: gx, y: r.maxY))
        }
        for i in 0...daisyCanvas.h {
            let gy = r.minY + CGFloat(i) * ZOOM
            p.move(to: NSPoint(x: r.minX, y: gy)); p.line(to: NSPoint(x: r.maxX, y: gy))
        }
        p.stroke()
    }

    private func saveContactSheet() {
        guard let rep = bitmapImageRepForCachingDisplay(in: bounds) else { return }
        cacheDisplay(in: bounds, to: rep)
        guard let data = rep.representation(using: .png, properties: [:]) else { return }
        let out = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
            .appendingPathComponent("art/preview/viewer-contact-sheet.png")
        try? data.write(to: out)
        NSSound(named: "Tink")?.play()
    }
}

// MARK: - App shell

final class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!

    func applicationDidFinishLaunching(_ n: Notification) {
        let view = PreviewView(frame: .zero)
        let content = view.idealSize
        view.frame = NSRect(origin: .zero, size: content)

        // The content is taller than any display, so scroll it rather than clipping rows away.
        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.hasHorizontalScroller = true
        scroll.drawsBackground = true
        scroll.backgroundColor = NSColor(white: 0.13, alpha: 1)
        scroll.documentView = view

        let visible = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1200, height: 800)
        let w = min(content.width + 16, visible.width * 0.95)
        let h = min(content.height + 2, visible.height * 0.92)

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: w, height: h),
                          styleMask: [.titled, .closable, .resizable, .miniaturizable],
                          backing: .buffered, defer: false)
        window.title = "Daisy animation preview"
        window.contentView = scroll
        window.center()
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(view)
        // scroll to the top: the document view is flipped-less, so top is max Y
        view.scroll(NSPoint(x: 0, y: content.height))
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ a: NSApplication) -> Bool { true }
}

// @main rather than top-level code: Swift only permits top-level statements in a file literally
// named main.swift, and that name is taken by the app itself.
@main
struct DaisyPreviewApp {
    // held statically because NSApplication keeps only a weak reference to its delegate
    static let delegate = AppDelegate()

    static func main() {
        let app = NSApplication.shared
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
}
