import Cocoa

/// Chooses which Daisy clip to play from the app's state, and sequences the one-shot beats
/// (celebration, idle fidgets) that make the resting icon feel alive rather than frozen.
///
/// Unlike the other animation styles, Daisy animates in EVERY state - including idle and awaiting
/// permission, which the Claude styles render as a static logo and a static yellow dot. That is the
/// point of her: the menu bar always has a dog doing something appropriate in it.
///
/// The driver owns a tick counter rather than reading wall-clock time, so playback speed is entirely
/// determined by the timer the caller runs at `fps`.
final class DaisyDriver {

    // MARK: - Tuning

    /// Idle longer than this and she stops dozing and properly goes to sleep.
    private let deepSleepAfter: TimeInterval = 120

    /// An idle fidget fires somewhere in this window, measured from the last one.
    private let fidgetEvery: ClosedRange<TimeInterval> = 35...100

    /// How long the turn-complete celebration runs before she settles. The wag loops, so this is
    /// three full cycles at 11 fps - a bit over a second.
    private let wagTicks = 12

    /// Extra ticks held after a fidget's last frame. A non-looping clip holds its final frame, so
    /// this keeps the pose on screen long enough to notice: `alert` is only two frames, and its
    /// first is the same resting sphinx as `drowsy`, so without padding the ear-perk flashes past.
    private let fidgetHoldTicks = 3

    /// Odds an idle fidget is the small ear-perk rather than the big stretch-and-yawn.
    private let alertVsYawn = 0.65

    // MARK: - State

    private var cache: [String: DaisyAnimation] = [:]
    private(set) var clip: String = "sleep"
    private var tick = 0

    /// Set while a one-shot beat plays: the tick at which it ends, and what to return to.
    private var oneShotEndsAt: Int?
    private var resumeClip: String = "sleep"

    private var restingSince: Date
    private var nextFidgetAt: Date
    private var lastEff = ""

    /// Injectable clock. Deep sleep and the idle fidgets are wall-clock thresholds, so without this
    /// they can only be exercised by waiting minutes in real time - which makes them effectively
    /// untestable, and "why does she never fall asleep?" impossible to answer offline.
    private let now: () -> Date

    init(now: @escaping () -> Date = Date.init) {
        self.now = now
        self.restingSince = now()
        self.nextFidgetAt = now()
        scheduleFidget()
    }

    // MARK: - Clip lookup

    /// Clips are decoded on first use and kept; a session may only ever touch two or three of them.
    private func animation(_ name: String) -> DaisyAnimation? {
        if let hit = cache[name] { return hit }
        guard let made = DaisyAnimation(name) else { return nil }
        cache[name] = made
        return made
    }

    var current: DaisyAnimation? { animation(clip) }
    var fps: Double { current?.fps ?? 6 }
    var frameCount: Int { current?.frameCount ?? 1 }
    var frameIndex: Int { current?.frameIndex(forTick: tick) ?? 0 }

    func image(colour: NSColor?) -> NSImage? {
        current?.image(frame: frameIndex, colour: colour, pointHeight: daisyPointHeight)
    }

    // MARK: - Tool mapping

    /// Raw Claude Code tool names, straight from the hook payload - deliberately not the prettified
    /// label, which the "thinking words" setting rewrites.
    private static func clip(forTool tool: String) -> String {
        switch tool {
        case "Edit", "Write", "MultiEdit", "NotebookEdit":
            return "dig"                    // digging: making a mess, productively
        case "Read", "Grep", "Glob", "WebFetch", "WebSearch":
            return "sniff"                  // nose down, following a trail
        case "Bash":
            return "zoomies"                // something is actually executing
        default:
            return "trot"                   // Task, TodoWrite, anything unrecognised
        }
    }

    // MARK: - Driving

    /// Feed the current app state in once per poll. Returns true when the clip changed, so the
    /// caller can restart its animation timer at the new clip's fps.
    @discardableResult
    func update(eff: String, tool: String) -> Bool {
        let active = (eff == "thinking" || eff == "tool" || eff == "permission")

        // A real state always wins: cancel any fidget or celebration immediately.
        if active {
            oneShotEndsAt = nil
            let want: String
            switch eff {
            case "permission": want = "ask"
            case "tool":       want = DaisyDriver.clip(forTool: tool)
            default:           want = "trot"
            }
            restingSince = now()
            lastEff = eff
            return switchTo(want)
        }

        // Just finished a turn - celebrate once, then settle.
        let wasActive = (lastEff == "thinking" || lastEff == "tool")
        lastEff = eff
        if wasActive {
            restingSince = now()
            scheduleFidget()
            return startOneShot("wag", ticks: wagTicks, resume: idleClip())
        }

        // Mid-beat: let it finish.
        if oneShotEndsAt != nil { return false }

        // Otherwise doze, with the occasional fidget.
        if now() >= nextFidgetAt {
            scheduleFidget()
            let fidget = Double.random(in: 0..<1) < alertVsYawn ? "alert" : "yawn"
            if let anim = animation(fidget) {
                return startOneShot(fidget, ticks: anim.frameCount + fidgetHoldTicks,
                                    resume: idleClip())
            }
        }
        return switchTo(idleClip())
    }

    /// Advance one animation frame. Returns true when a finished one-shot handed back to another
    /// clip, since that changes fps.
    @discardableResult
    func advance() -> Bool {
        tick += 1
        if let end = oneShotEndsAt, tick >= end {
            oneShotEndsAt = nil
            return switchTo(resumeClip)
        }
        return false
    }

    // MARK: - Helpers

    private func idleClip() -> String {
        now().timeIntervalSince(restingSince) >= deepSleepAfter ? "sleep" : "drowsy"
    }

    private func scheduleFidget() {
        nextFidgetAt = now().addingTimeInterval(Double.random(in: fidgetEvery))
    }

    private func switchTo(_ name: String) -> Bool {
        guard name != clip else { return false }
        guard animation(name) != nil else { return false }   // never leave her on a missing clip
        clip = name
        tick = 0
        return true
    }

    private func startOneShot(_ name: String, ticks: Int, resume: String) -> Bool {
        guard animation(name) != nil else { return switchTo(resume) }
        resumeClip = resume
        let changed = switchTo(name)
        oneShotEndsAt = tick + max(1, ticks)     // switchTo reset tick to 0 when the clip changed
        return changed
    }

    /// Called when the colour mode flips; cached renders are mode-specific.
    func flushCaches() {
        cache.values.forEach { $0.flushCache() }
    }
}
