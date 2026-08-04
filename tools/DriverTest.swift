import Cocoa

// Headless exercise of DaisyDriver, so the state machine can be checked without installing hooks or
// taking over the menu bar. Run with:  ./tools/drivertest.sh
//
// Prints the clip chosen for each simulated state transition, then fast-forwards through idle to
// show the doze -> deep-sleep progression and the random fidgets firing.

@main
struct DriverTest {
    static func main() {
        let d = DaisyDriver()
        var failures = 0

        func expect(_ got: String, _ want: String, _ what: String) {
            let ok = got == want
            if !ok { failures += 1 }
            print("  \(ok ? "ok  " : "FAIL") \(what.padding(toLength: 34, withPad: " ", startingAt: 0)) -> \(got)\(ok ? "" : "   (wanted \(want))")")
        }

        print("clips available: \(daisyClips.keys.sorted().joined(separator: ", "))")
        print("canvas \(daisyCanvas.w)x\(daisyCanvas.h), drawn at \(daisyPointHeight) pt\n")

        print("state -> clip mapping")
        d.update(eff: "thinking", tool: "")
        expect(d.clip, "trot", "thinking")
        d.update(eff: "tool", tool: "Bash")
        expect(d.clip, "zoomies", "tool/Bash")
        d.update(eff: "tool", tool: "Edit")
        expect(d.clip, "dig", "tool/Edit")
        d.update(eff: "tool", tool: "Write")
        expect(d.clip, "dig", "tool/Write")
        d.update(eff: "tool", tool: "Read")
        expect(d.clip, "sniff", "tool/Read")
        d.update(eff: "tool", tool: "Grep")
        expect(d.clip, "sniff", "tool/Grep")
        d.update(eff: "tool", tool: "WebSearch")
        expect(d.clip, "sniff", "tool/WebSearch")
        d.update(eff: "tool", tool: "TodoWrite")
        expect(d.clip, "trot", "tool/TodoWrite (fallback)")
        d.update(eff: "tool", tool: "SomethingNew")
        expect(d.clip, "trot", "tool/unknown (fallback)")
        d.update(eff: "permission", tool: "")
        expect(d.clip, "ask", "permission")

        print("\nturn completion should celebrate, then settle")
        d.update(eff: "thinking", tool: "")
        expect(d.clip, "trot", "back to thinking")
        d.update(eff: "idle", tool: "")
        expect(d.clip, "wag", "thinking -> idle fires wag")
        var guard1 = 0
        while d.clip == "wag" && guard1 < 200 { d.advance(); guard1 += 1 }
        expect(d.clip, "drowsy", "wag hands back after \(guard1) ticks")

        print("\nidle should stay put, not thrash")
        let before = d.clip
        for _ in 0..<40 { d.update(eff: "idle", tool: "") }
        expect(d.clip, before, "40 idle polls keep the clip")

        print("\nan active state must interrupt a one-shot immediately")
        d.update(eff: "thinking", tool: "")
        d.update(eff: "idle", tool: "")
        expect(d.clip, "wag", "wag started")
        d.update(eff: "tool", tool: "Bash")
        expect(d.clip, "zoomies", "Bash interrupts the wag")

        print("\nfidgets and deep sleep, on a virtual clock (10 simulated minutes)")
        // A fresh driver on an injectable clock, so the wall-clock thresholds (120 s deep sleep,
        // 35-100 s fidget interval) can actually be reached without waiting.
        var virtualNow = Date(timeIntervalSince1970: 1_000_000)
        let sim = DaisyDriver(now: { virtualNow })

        var seen: [String: Int] = [:]
        var transitions: [String] = []
        var last = sim.clip
        var firstSleepAt: TimeInterval?
        let start = virtualNow

        // 0.4 s poll interval, matching StatusController's pollTimer
        for _ in 0..<1500 {
            virtualNow = virtualNow.addingTimeInterval(0.4)
            sim.update(eff: "idle", tool: "")
            for _ in 0..<3 { sim.advance() }
            if sim.clip != last {
                transitions.append(sim.clip)
                last = sim.clip
                if sim.clip == "sleep", firstSleepAt == nil {
                    firstSleepAt = virtualNow.timeIntervalSince(start)
                }
            }
            seen[sim.clip, default: 0] += 1
        }
        print("  clips seen: \(seen.sorted { $0.value > $1.value }.map { "\($0.key)x\($0.value)" }.joined(separator: ", "))")
        print("  transitions: \(transitions.prefix(14).joined(separator: " -> "))\(transitions.count > 14 ? " …" : "")")
        if let t = firstSleepAt {
            expect(t >= 120 && t < 160 ? "yes" : "at \(Int(t))s", "yes", "deep sleep after ~120 s")
        } else {
            expect("never", "yes", "deep sleep after ~120 s")
        }
        let fidgets = (seen["alert"] ?? 0) + (seen["yawn"] ?? 0)
        expect(fidgets > 0 ? "yes" : "never", "yes", "idle fidgets fire")
        expect(transitions.contains("alert") || transitions.contains("yawn") ? "yes" : "no",
               "yes", "fidget appears in transitions")

        print("\nevery clip must decode and produce an image")
        for name in daisyClips.keys.sorted() {
            guard let anim = DaisyAnimation(name) else {
                print("  FAIL \(name): DaisyAnimation init returned nil"); failures += 1; continue
            }
            var okColour = 0, okTemplate = 0
            for i in 0..<anim.frameCount {
                if anim.image(frame: i, colour: .orange, pointHeight: daisyPointHeight) != nil { okColour += 1 }
                if anim.image(frame: i, colour: nil, pointHeight: daisyPointHeight) != nil { okTemplate += 1 }
            }
            let good = okColour == anim.frameCount && okTemplate == anim.frameCount
            if !good { failures += 1 }
            print("  \(good ? "ok  " : "FAIL") \(name.padding(toLength: 10, withPad: " ", startingAt: 0)) "
                  + "\(anim.frameCount)f  colour \(okColour)/\(anim.frameCount)  template \(okTemplate)/\(anim.frameCount)  "
                  + "fps \(anim.fps)  \(anim.loops ? "loop" : "once")\(anim.intro > 0 ? "  intro \(anim.intro)" : "")")
        }

        print("\nframe index sequencing (intro must play once, then loop)")
        if let dig = DaisyAnimation("dig") {
            let seq = (0..<10).map { String(dig.frameIndex(forTick: $0)) }.joined(separator: ",")
            expect(seq, "0,1,2,3,1,2,3,1,2,3", "dig intro=1 over 10 ticks")
        }
        if let yawn = DaisyAnimation("yawn") {
            let seq = (0..<7).map { String(yawn.frameIndex(forTick: $0)) }.joined(separator: ",")
            expect(seq, "0,1,2,3,3,3,3", "yawn one-shot holds last frame")
        }

        print(failures == 0 ? "\nALL CHECKS PASSED" : "\n\(failures) CHECK(S) FAILED")
        exit(failures == 0 ? 0 : 1)
    }
}
