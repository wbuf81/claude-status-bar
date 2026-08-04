import Cocoa

// Decoding and rendering for the Daisy sprite clips in DaisyFrames.swift.
//
// Two variants are needed, matching the app's two colour modes:
//
//   Orange  -> the full-colour sprite drawn as-is (she is already tri-colour; there is nothing
//              sensible to tint her to).
//   System  -> an adaptive TEMPLATE image. macOS draws templates in one uniform colour (black on a
//              light menu bar, white on a dark one), so only the alpha channel can carry detail.
//
// The template is built by INKING the dark pixels and PUNCHING OUT the light ones, which turns her
// white blaze, chest bib, paws and tail tip into deliberate negative space. That is what makes her
// readable as a specific dog in monochrome rather than an anonymous blob.
//
// This is the opposite of the approach CrabRender.swift uses for Clawd. The crab maps brightness to
// opacity, keeping its bright body solid and dropping its dark eyes out. Run that on a Bernese and
// her entire black body vanishes, leaving a floating white chest patch. Hence a separate renderer;
// do not try to share one.
enum DaisyRender {

    /// Luminance below this becomes ink, above it becomes a transparent hole.
    ///
    /// Tuned against the art, not guessed. The sprite's luminance histogram has a wide empty gap
    /// between the body/rust cluster (~24-49) and the whites (~178-240), so anything from roughly
    /// 55 to 175 gives an identical result. 150 sits safely mid-plateau.
    static let inkCut: Double = 150

    // MARK: - Decoding

    static func decode(_ base64: String) -> NSImage? {
        guard let data = Data(base64Encoded: base64), let img = NSImage(data: data) else { return nil }
        return img
    }

    static func decodeAll(_ base64: [String]) -> [NSImage] {
        base64.compactMap(decode)
    }

    // MARK: - Template rendering

    /// Build the System-mode template for one frame.
    ///
    /// - Parameter particleMask: optional 8-bit mask marking pixels that belong to a particle blob
    ///   (dirt clods, speed puffs, the sleep Z) rather than to Daisy herself. Those are ALWAYS
    ///   inked, never punched out. Pale particles otherwise disappear entirely: a hole needs
    ///   surrounding ink to read as a hole, and an isolated puff has none. This is why the zoomies
    ///   speed puffs vanished before the mask existed.
    static func template(_ src: NSImage, particleMask: NSImage? = nil) -> NSImage {
        guard let srcPixels = bitmap(src) else { return src }
        let w = srcPixels.pixelsWide, h = srcPixels.pixelsHigh
        guard let cg = srcPixels.cgImage else { return src }

        // Flatten the particle mask to a plain byte array once. Reading it per-pixel via
        // NSBitmapImageRep.colorAt would be slow, and raises on greyscale reps because the returned
        // NSColor has no RGB components to interrogate.
        let maskBits: [Bool]? = particleMask.flatMap { maskBytes($0, width: w, height: h) }

        let space = CGColorSpaceCreateDeviceRGB()
        let info = CGImageAlphaInfo.premultipliedLast.rawValue
        guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8,
                                  bytesPerRow: w * 4, space: space, bitmapInfo: info) else { return src }
        ctx.draw(cg, in: CGRect(x: 0, y: 0, width: w, height: h))
        guard let raw = ctx.data else { return src }
        let px = raw.bindMemory(to: UInt8.self, capacity: w * h * 4)

        for i in 0..<(w * h) {
            let off = i * 4
            let alpha = px[off + 3]
            guard alpha > 0 else { continue }               // background stays transparent

            let isParticle = maskBits?[i] ?? false

            let af = Double(alpha) / 255
            let r = Double(px[off])     / (255 * af)
            let g = Double(px[off + 1]) / (255 * af)
            let b = Double(px[off + 2]) / (255 * af)
            let lum = (0.299 * r + 0.587 * g + 0.114 * b) * 255

            px[off] = 0; px[off + 1] = 0; px[off + 2] = 0   // template ink is black

            if isParticle || lum < inkCut {
                px[off + 3] = alpha                          // ink, preserving anti-aliased edges
            } else {
                px[off + 3] = 0                              // light markings punch through as holes
            }
        }

        guard let out = ctx.makeImage() else { return src }
        let img = NSImage(cgImage: out, size: src.size)
        img.isTemplate = true
        return img
    }

    // MARK: - Sizing

    /// Scale a decoded frame to the point size that keeps one logical pixel on one device pixel.
    /// Width floats with the aspect ratio, the same way upstream's crabIcon does.
    static func sized(_ src: NSImage, pointHeight: CGFloat, isTemplate: Bool) -> NSImage {
        let rep = src.representations.first
        let pw = CGFloat(rep?.pixelsWide ?? Int(src.size.width))
        let ph = CGFloat(rep?.pixelsHigh ?? Int(src.size.height))
        let w = ph > 0 ? (pointHeight * (pw / ph)).rounded() : pointHeight
        let img = NSImage(size: NSSize(width: w, height: pointHeight), flipped: false) { rect in
            NSGraphicsContext.current?.imageInterpolation = .none   // never smooth pixel art
            src.draw(in: rect, from: .zero, operation: .sourceOver, fraction: 1.0)
            return true
        }
        img.isTemplate = isTemplate
        return img
    }

    // MARK: - Helpers

    private static func bitmap(_ img: NSImage) -> NSBitmapImageRep? {
        if let rep = img.representations.compactMap({ $0 as? NSBitmapImageRep }).first { return rep }
        guard let tiff = img.tiffRepresentation else { return nil }
        return NSBitmapImageRep(data: tiff)
    }

    /// Rasterise a mask image into one bool per pixel, row-major, matching the frame's dimensions.
    /// Drawn through an explicit greyscale context so the input's own colour space and bit depth
    /// stop mattering.
    private static func maskBytes(_ mask: NSImage, width: Int, height: Int) -> [Bool]? {
        guard width > 0, height > 0,
              let rep = bitmap(mask), let cg = rep.cgImage else { return nil }
        var buf = [UInt8](repeating: 0, count: width * height)
        let space = CGColorSpaceCreateDeviceGray()
        let ok: Bool = buf.withUnsafeMutableBytes { raw -> Bool in
            guard let ctx = CGContext(data: raw.baseAddress, width: width, height: height,
                                     bitsPerComponent: 8, bytesPerRow: width, space: space,
                                     bitmapInfo: CGImageAlphaInfo.none.rawValue) else { return false }
            ctx.interpolationQuality = .none
            ctx.draw(cg, in: CGRect(x: 0, y: 0, width: width, height: height))
            return true
        }
        guard ok else { return nil }
        return buf.map { $0 > 127 }
    }
}

// MARK: - Clip playback

/// Wraps one generated clip with its decoded frames and the sequencing rules the pipeline recorded
/// (a wind-up intro, whether it loops). Frames are decoded lazily and cached: decoding all 36 up
/// front is wasted work when a session may only ever show two or three clips.
final class DaisyAnimation {
    let name: String
    let fps: Double
    let loops: Bool
    let intro: Int

    private let clip: DaisyClip
    private var colourCache: [Int: NSImage] = [:]
    private var templateCache: [Int: NSImage] = [:]

    init?(_ name: String) {
        guard let clip = daisyClips[name] else { return nil }
        self.name = name
        self.clip = clip
        self.fps = clip.fps
        self.loops = clip.loops
        self.intro = clip.intro
    }

    var frameCount: Int { clip.frames.count }

    /// Total frames in one pass; a looping clip repeats only the part after the intro.
    func frameIndex(forTick tick: Int) -> Int {
        let n = frameCount
        guard n > 0 else { return 0 }
        if tick < intro { return tick }
        let cycle = n - intro
        guard cycle > 0 else { return n - 1 }
        if !loops { return min(tick, n - 1) }
        return intro + ((tick - intro) % cycle)
    }

    /// One frame, ready to hand to a status item button.
    func image(frame: Int, colour: NSColor?, pointHeight: CGFloat) -> NSImage? {
        let i = max(0, min(frame, frameCount - 1))
        let wantTemplate = (colour == nil)
        if let hit = (wantTemplate ? templateCache : colourCache)[i] { return hit }

        guard let base = DaisyRender.decode(clip.frames[i]) else { return nil }
        let rendered: NSImage
        if wantTemplate {
            let mask = clip.particleMasks.indices.contains(i)
                ? clip.particleMasks[i].flatMap(DaisyRender.decode)
                : nil
            rendered = DaisyRender.sized(DaisyRender.template(base, particleMask: mask),
                                         pointHeight: pointHeight, isTemplate: true)
            templateCache[i] = rendered
        } else {
            rendered = DaisyRender.sized(base, pointHeight: pointHeight, isTemplate: false)
            colourCache[i] = rendered
        }
        return rendered
    }

    func flushCache() {
        colourCache.removeAll()
        templateCache.removeAll()
    }
}
