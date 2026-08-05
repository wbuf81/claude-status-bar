# DAISY-DISTRIBUTION.md — shipping Daisy as an installable app

Plan of record for making `wbuf81/daisy-claude-status-bar` installable by someone who is not us.
Written 2026-08-05.

**Status: §1 §2 §3 §6 done. §4 (tag a release) and §5 (create the tap) are the remaining steps.**
Verified on 2026-08-05: Daisy and upstream's app run side by side in the same menu bar, with all
16 hooks (8 each) coexisting in one real `~/.claude/settings.json`, neither stripping the other.

Read `DAISY-PLAN.md` for the app architecture and `HOMEBREW.md` for how UPSTREAM's cask works —
that file describes m1ckc3s's cask, not ours, and is a source of confusion until step 6.

## Decisions taken

**Distribution is a Homebrew formula that builds from source, in our own tap.** Not a cask, not a
DMG. The reason is Gatekeeper: `build.sh:59` notarizes against `TEAM_ID="W9JZ4932LA"`, which is
upstream's team, and we hold no certificate for it, so every build falls back to ad-hoc signing.
Verified: `spctl -a` **rejects** the current build. A downloaded ad-hoc app makes the user visit
System Settings → Privacy & Security → Open Anyway, and on macOS 26 the old Control-click → Open
shortcut no longer clears it.

A formula sidesteps this entirely: the app is compiled on the user's own machine, and locally built
binaries are never quarantined, so there is no Gatekeeper prompt to explain. It costs nothing, where
a Developer ID is currently $99/yr. The price is that users need Xcode Command Line Tools and wait
through two `swiftc` invocations instead of a download.

If we ever do buy a Developer ID, `build.sh --dmg` already implements signing, notarization and
stapling — switching to a cask would then be a small change, and this plan does not foreclose it.

**Daisy gets its own identity, so it can coexist with upstream.** Today the fork is bundle-identical
to upstream, which makes it uninstallable alongside it. See the next section.

## 1. The identity rename

Everything in the left column is currently shared with upstream. While it is shared: a cask or
formula would fight upstream's cask over `/Applications/Claude Status Bar.app`, both apps read the
same preferences (already a known gotcha in `CLAUDE.md` — the upstream build cannot parse
`animStyle=daisy` and silently falls back to Claude Spark), and `Sources/main.swift:478` actively
hunts down and deletes "the old copy."

| Thing | Now | Becomes | Where |
|---|---|---|---|
| Bundle folder | `Claude Status Bar.app` | `Daisy Status Bar.app` | `build.sh:10` |
| Bundle ID | `com.local.claudestatusbar` | `com.wbuf81.daisystatusbar` | `build.sh:33`, `hooks/lifecycle.js:9`, `hooks/update.js:115`, `hooks/*.js` agent labels, `Sources/DaisyState.swift:80-81` (doc comments) |
| Executable | `ClaudeStatusBar` | `DaisyStatusBar` | `build.sh:11,34`, `hooks/lifecycle.js:10`, `hooks/update.js:112`, `hooks/uninstall.js:22` |
| `CFBundleName` / display name | `ClaudeStatusBar` / `Claude Status Bar` | `DaisyStatusBar` / `Daisy Status Bar` | `build.sh:31-32` |
| Hook dir | `~/.claude/statusbar` | `~/.claude/daisy-statusbar` | `hooks/install.js:12`, `hooks/update.js:10`, `hooks/uninstall.js:10`, `hooks/lifecycle.js:11` |
| settings.json backup | `.bak-statusbar` | `.bak-daisy-statusbar` | `hooks/install.js:44` |

### Landmine: the hook directory must be PREFIXED, never suffixed

`hooks/install.js:34` decides which hooks in `~/.claude/settings.json` belong to it by plain
substring match against the hook directory path:

```js
const isOurs = (command) => command.includes(MARKER) || command.includes(quotedMarkerPrefix);
```

`~/.claude/daisy-statusbar` is safe: it does not contain the substring `~/.claude/statusbar`.

`~/.claude/statusbar-daisy` would be a **disaster** — it *does* contain `~/.claude/statusbar`, so
upstream's `install.js` would classify Daisy's hooks as its own and strip them on every launch.
Daisy would silently stop animating whenever upstream's app started. Use the `daisy-` prefix.

### Consequence: `main.swift:473-481` self-deletion must go

That block removes `/Applications/ClaudeStatusBar.app` after verifying its bundle ID. It exists for
upstream's 0.4.0 rename and is meaningless for us — worse, it is exactly the behaviour that would
make Daisy eat a neighbouring install. Delete it rather than repoint it.

## 2. Repoint the update check

`Sources/main.swift:548-553` currently asks upstream about upstream:

```swift
let releaseAPIURL = "https://api.github.com/repos/m1ckc3s/claude-status-bar/releases/latest"
let releasePageURL = "https://github.com/m1ckc3s/claude-status-bar/releases/latest"
let brewCaskAPIURL = "https://formulae.brew.sh/api/cask/claude-status-bar.json"
```

Shipped as-is, Daisy would compare its version against upstream's tags and tell every user to go
install m1ckc3s's app. Repoint the two GitHub URLs at `wbuf81/daisy-claude-status-bar`.

The `formulae.brew.sh` check must be **removed**, not repointed: that API only serves official
homebrew-core/cask, and our formula lives in a personal tap, so there is no endpoint to ask. The
"has brew caught up yet" logic it feeds (documented in `HOMEBREW.md`) is moot for a tap, because a
tap has no autobump bot and no propagation lag — the formula is whatever we last pushed.

## 3. Version numbering

The fork inherited `0.4.3` from upstream in `build.sh:35-36`. Restart Daisy at **`0.1.0`** and
version independently from here. Keeping upstream's numbers would make `versionIsNewer` compare our
releases against theirs, and a user could not tell which app a version referred to.

Record in the release notes which upstream version each Daisy release is built on, since we still
merge from `upstream`.

## 4. Tag a release

The formula needs a tagged source tarball and its sha256. GitHub generates the tarball
automatically for any tag, so **there is no artifact to build or upload** — no DMG, nothing to
notarize.

```
git tag -a v0.1.0 -m "Daisy Status Bar 0.1.0"
git push origin v0.1.0
gh release create v0.1.0 --title "Daisy Status Bar 0.1.0" --notes "…"
shasum -a 256 <(curl -sL https://github.com/wbuf81/daisy-claude-status-bar/archive/refs/tags/v0.1.0.tar.gz)
```

## 5. Create the tap

A new repo, `wbuf81/homebrew-daisy` — Homebrew resolves the `homebrew-` prefix, so users type
`wbuf81/daisy`. Personal taps need no review and no notability threshold, which official
homebrew-cask does; it would also reject a second cask for a fork of an app it already ships.

`Formula/daisy-status-bar.rb`:

```ruby
class DaisyStatusBar < Formula
  desc "Bernese Mountain Dog that reacts to what Claude Code is doing, in your macOS menu bar"
  homepage "https://github.com/wbuf81/daisy-claude-status-bar"
  url "https://github.com/wbuf81/daisy-claude-status-bar/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "…"
  license "MIT"

  depends_on :macos
  depends_on xcode: :build   # swiftc; Command Line Tools are enough

  def install
    system "./build.sh"
    prefix.install "build/Daisy Status Bar.app"
  end

  def caveats
    <<~EOS
      Link Daisy into /Applications and launch her once to install the Claude Code hooks:
        ln -sf "#{opt_prefix}/Daisy Status Bar.app" /Applications/
        open "/Applications/Daisy Status Bar.app"
      She self-quits when no Claude Code session is live; that is normal, not a failed install.
    EOS
  end
end
```

Then `brew install wbuf81/daisy/daisy-status-bar`.

Open questions to resolve while writing it:
- `build.sh` runs `xattr -cr` and `codesign --force --sign -`; confirm both work inside Homebrew's
  build sandbox. If ad-hoc signing fails there, the app still runs — verify rather than assume.
- Formulae cannot use the cask `app` stanza, hence the `ln -sf` in caveats. Check whether a
  `postinstall` symlink is acceptable in a personal tap and less clumsy for users.

## 6. Fix the docs — currently actively wrong

Both install paths in `README.md` are broken for this fork:

- **`README.md:37`** — `brew install --cask claude-status-bar` installs **upstream's app**. Anyone
  following our own README today gets m1ckc3s's build with no Daisy in it.
- **`README.md:51`** — links to `../../releases`, and this fork has **zero releases**. Dead end.

The Daisy header block at the top of `README.md` needs its own Install section, above the inherited
upstream README, saying plainly that the brew line further down belongs to upstream.

`HOMEBREW.md` is entirely upstream's cask story. Either retitle it as upstream's (it is still
accurate for them, and we merge from `upstream`) or add a Daisy section. Do not leave it looking
like it describes our install.

## Order of work, and how to verify each step

1. Identity rename (§1) → `./build.sh`, then `./tools/drivertest.sh`, then launch by explicit path
   and confirm the icon appears.
2. Remove self-deletion + repoint update check (§2) → grep for any remaining `m1ckc3s` or
   `claudestatusbar` outside of deliberate upstream references.
3. Version bump (§3), commit, tag, release (§4).
4. Tap + formula (§5) → `brew install --build-from-source wbuf81/daisy/daisy-status-bar` **on a
   machine that is not this one**, or at least verify the Caskroom/Cellar path does not collide.
5. Docs (§6).

### Risk: this machine is not a clean test bed

`/Applications/Claude Status Bar.app` here is a **dev build copied in place**, and the Homebrew
Caskroom entry is a symlink pointing at it:

```
/opt/homebrew/Caskroom/claude-status-bar/0.4.3/Claude Status Bar.app -> /Applications/Claude Status Bar.app
```

So `codesign`/`spctl` checks against that path describe our dev build, not upstream's shipped one,
and brew believes it manages a bundle we replaced by hand. Do not draw conclusions about upstream's
signing from this machine, and expect a genuine end-to-end install test to need a clean Mac or a
fresh user account.

Also: `~/.claude/settings.json` on this machine currently has upstream's hooks wired in. The rename
adds a second, independent set. Both apps will animate at once — two icons in the menu bar — which
is correct behaviour for coexistence but will look alarming the first time.
