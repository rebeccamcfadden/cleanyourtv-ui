# Reading Continue watching

A launcher can show the rows other apps publish to the system's Continue watching (Watch Next)
and preview channels. They live in the TV provider, behind `TvContract.WatchNextPrograms` and
`TvContract.PreviewPrograms`.

- **Permission:** `android.permission.READ_TV_LISTINGS`, a runtime permission. Request it with
  the normal dialog, or grant it from a shell: `pm grant <package> android.permission.READ_TV_LISTINGS`.
- **Not needed:** `com.android.providers.tv.permission.ACCESS_ALL_EPG_DATA` is
  `signature|privileged`, so a sideloaded app cannot hold it. With only `READ_TV_LISTINGS` a query returns
  the caller's own rows plus every row marked `searchable`.
- **Query without a selection:** a caller without `ACCESS_ALL_EPG_DATA` gets a `SecurityException`
  when it passes one. Read the whole table and filter in code.
- **Some apps publish nothing.** Rows exist only if the app writes them and marks them
  searchable, and some apps do neither, so query on the target TV before relying on an app.
  Query from an app that holds `READ_TV_LISTINGS`, not from the shell: the shell lacks it, so
  `content query --uri content://android.media.tv/watch_next_program` (or `channel`,
  `preview_program`) prints `No result found.` and cannot tell whether any app publishes rows.
- **Seen on a Chromecast with Google TV 4K** (Google TV 14, `UTTC.250917.004`): a test build
  holding `READ_TV_LISTINGS` and querying without a selection saw 6 channels and 51 preview
  programs, all from YouTube and Spotify, and no Watch Next rows. Poster URIs were `https://` (one
  Spotify poster aside, `android.resource://`), so a reader needs network access to show most of
  them; `intent_uri` held `intent:` URIs. Plex (`com.plexapp.android` 2026.20.0, which requests
  `WRITE_EPG_DATA`) had no channel, preview or Watch Next rows visible. Without
  `ACCESS_ALL_EPG_DATA` a reader sees only its own rows plus rows marked `searchable`, so Plex rows
  that are not searchable would be invisible too: the probe cannot tell "publishes nothing" from
  "publishes only non-searchable rows".

Source: `createSqlParams()` in `packages/providers/TvProvider/src/com/android/providers/tv/TvProvider.java`
(AOSP) holds the `READ_TV_LISTINGS` and `searchable` logic; both permissions are defined in that
module's `AndroidManifest.xml`.

## Temporary CleanYourTV UI diagnostic (Phase 1 only)

The UI launcher (`io.cleanyourtv.ui`, Android 9 / API 28 minimum, target 33) now has an explicit,
read-only diagnostic. It does not add a Home row, change the layout, resume anything, fetch artwork,
call TMDB, or run automatically. The diagnostic is independent of the opt-in production Home integration below.

`TvProviderDiagnosticActivity` dispatches the work to a background thread and finishes when it is
done. It requires the **caller's** `android.permission.DUMP`, normally held by the ADB shell but not
ordinary apps. The launcher does not request that permission itself. There is no menu or intent
filter for the diagnostic. If a manufacturer refuses the shell entry point, report that failure;
do not remove the protection or root the TV.

### Build, install and run

Build from this repository using [the UI build instructions](../README.md). The resulting APK is
`launcher-ui/CleanYourTV-UI.apk`; keep the existing local signing key for an update. The following
commands assume native `adb` is installed, the TV has already authorized this computer, and the
updated APK is installed. Replace `<tv ip>` with the TV's address.

```powershell
$env:TV_HOST='<tv ip>'
adb connect "$($env:TV_HOST):5555"
adb install -r launcher-ui\CleanYourTV-UI.apk
adb shell pm grant io.cleanyourtv.ui android.permission.READ_TV_LISTINGS
```

In one terminal, start capturing **before** launching the diagnostic (leave other log buffers alone):

```sh
adb logcat -v threadtime -s CYTV-TvProvider:I "*:S"
```

In another terminal:

```sh
adb shell am start -n io.cleanyourtv.ui/.TvProviderDiagnosticActivity
```

That first run shows titles, packages, metadata and progress, but redacts URI/intent/internal-provider
columns and other recognizable sensitive columns. It is **not guaranteed safe to publish**: arbitrary
vendor columns, titles and error messages can still be personal or sensitive.

For the requested **full raw inspection**, explicitly opt in:

```sh
adb shell am start -n io.cleanyourtv.ui/.TvProviderDiagnosticActivity --ez raw_values true
```

**Keep raw logs local.** They contain viewing history; URLs, intent extras and opaque provider data
may include account identifiers or access tokens. Do not upload the output or commit it. Redact it
before sharing even a short excerpt. The diagnostic does not write its own files or transmit data.
Logcat retains entries until they roll out of its buffers; revoking the permission does not erase logs.

Without native `adb`, the existing Python tools can transfer the APK and run the same device-side
commands from the repository root. Use this alternative instead of the native installation above:

```powershell
$env:TV_HOST='<tv ip>'
& tools\venv\Scripts\python.exe -I tools\b64push.py launcher-ui\CleanYourTV-UI.apk /data/local/tmp/cleanyourtv-ui.apk
& tools\venv\Scripts\python.exe -I tools\tv.py 'pm install -r /data/local/tmp/cleanyourtv-ui.apk'
```

Continue only if the transfer verifies and the installation reports `Success`. An update must use
the existing signing key; stop on an install failure rather than uninstalling the working launcher.
Then grant, trigger and read the retained logs:

```powershell
$env:TV_HOST='<tv ip>'
& tools\venv\Scripts\python.exe -I tools\tv.py 'pm grant io.cleanyourtv.ui android.permission.READ_TV_LISTINGS'
& tools\venv\Scripts\python.exe -I tools\tv.py 'am start -n io.cleanyourtv.ui/.TvProviderDiagnosticActivity --ez raw_values true'
& tools\venv\Scripts\python.exe -I tools\tv.py 'logcat -d -v threadtime -s CYTV-TvProvider:I "*:S"'
```

The last command dumps retained log entries instead of keeping a streaming connection open. Run it
again if the matching `END` has not appeared yet. Use the `run=` identifier to distinguish runs.
No TV install occurs just by building, and this update does not change the default Home selection
or debloat settings.

### What the output means

Every run lists visible enabled Leanback app packages (not a guarantee that they publish anything),
the runtime/privileged permission states, and independent results for:

- `WATCH_NEXT`: the system's Watch Next records.
- `PREVIEW_PROGRAM`: preview-channel records, which can be recommendations rather than resume items.
- `CHANNEL`: publisher/channel metadata; use `_id` to interpret preview `channel_id`.

Each query uses a null projection, selection and sort order. Every accessible row and every returned
column is logged, including unknown/vendor fields, with its cursor type and original value. No package
filter, deduplication, inferred metadata, fabricated progress, or row limit is applied. Column types are
`0=null`, `1=integer`, `2=float`, `3=string`, `4=blob`. Missing columns appear only by their absence from
the schema; nulls stay null and zero stays zero. Binary values are base64 only in raw mode.

Look for `_id`, `package_name`, `title`, `short_description`, `long_description`, `type`,
`watch_next_type`, `season_display_number`, `episode_display_number`, `episode_title`,
`last_playback_position_millis`, `duration_millis`, `last_engagement_time_utc_millis`,
`poster_art_uri`, `thumbnail_uri`, `preview_video_uri`, `intent_uri`, `searchable`, `browsable`,
`content_id`, `internal_provider_id` and any provider-specific identifiers. Availability varies;
the diagnostic does not request a fixed column list that would fail on an older schema.

For example (illustrative, not results from your TV):

```text
run=123 READ_TV_LISTINGS=GRANTED ACCESS_ALL_EPG_DATA=DENIED
run=123 WATCH_NEXT row=1 column="_id" type=1 value= 42
run=123 WATCH_NEXT row=1 column="package_name" type=3 value= "com.example.player"
run=123 WATCH_NEXT row=1 column="title" type=3 value= "Example show"
run=123 WATCH_NEXT row=1 column="last_playback_position_millis" type=1 value= 1200000
run=123 WATCH_NEXT row=1 column="duration_millis" type=1 value= 2400000
run=123 WATCH_NEXT PUBLISHER rows=1 package= "com.example.player"
run=123 WATCH_NEXT END status=OK rows_visited=1 field_errors=0 complete=true
run=123 PREVIEW_PROGRAM END status=OK rows_visited=0 field_errors=0 complete=true
run=123 CHANNEL END status=OK rows_visited=0 field_errors=0 complete=true
run=123 END status=COMPLETE complete_sources=3/3 inventory_ok=true
```

Long values are split into numbered character ranges, preserving surrogate pairs and repeating the
source/row/column prefix, rather than silently truncating a URI at logcat's per-entry byte limit.
Strings use JSON quoting so embedded line breaks cannot impersonate other diagnostic records.
Writes are briefly paced because older TVs can drop rapid log bursts even during live capture.
Large channel tables can take a minute or longer; wait for the final run-level `END`. Keep a live
capture running before triggering the probe, since a large dump can exceed logcat's retained buffer.

- `OK` with zero rows means **no rows accessible to this launcher**, not proof that nothing is published.
- `SECURITY_EXCEPTION` identifies a denied table. Verify the runtime grant first. A granted permission
  does not guarantee that a manufacturer's provider exposes other apps' records.
- `UNSUPPORTED` / `UNAVAILABLE_OR_INVALID_QUERY` identifies an unsupported table or rejected query.
- `NULL_CURSOR` is a failed/inconclusive query, never represented as an empty success.
- `QUERY_OR_CURSOR_ERROR` or `FIELD_ERRORS` means incomplete data; earlier rows may still be useful.
- Each failure includes its exception type, message and stack trace. Other tables are still attempted.
- A completed run with any failure says `COMPLETED_WITH_ERRORS`. A missing final `END` is incomplete:
  inspect logcat for process/provider crashes or a stalled query; do not interpret it as zero records.
- `ACCESS_ALL_EPG_DATA=DENIED` is expected for this sideloaded launcher. Do not try to grant privileged
  permissions, add write permissions, or use shell `content query` as a substitute for this app probe.

To deliberately verify denial reporting, revoke the read permission and then launch the diagnostic
again (revoking may restart the launcher process):

```sh
adb shell pm revoke io.cleanyourtv.ui android.permission.READ_TV_LISTINGS
adb shell am start -n io.cleanyourtv.ui/.TvProviderDiagnosticActivity
```

Restore the grant before collecting real coverage results. After testing, it can be revoked again.
To remove the temporary facility, delete `TvProviderDiagnostic.java`, `TvProviderDiagnosticActivity.java`,
its manifest activity entry, this diagnostic documentation section and its diagnostic tests.
**Keep `READ_TV_LISTINGS`: the production source below also needs it.** No Home code or persisted
launcher preferences need reverting.

## Production data boundary (Phase 2)

Phase 2 adds data and playback primitives, **not a Home row**. The current `Tmdb.Title` and `Recs.Pick`
models require TMDB identifiers and artwork assumptions that do not fit native provider rows, so they
remain unchanged. No standalone add-on, Activity, layout, dependency, network request, permission
screen or provider-specific integration is added. Minimum/target SDK remain 28/33.

```text
TvContract.WatchNextPrograms -> TvProviderWatchNextSource
                            -> ContinueWatchingItem
                            -> ContinueWatchingRepository.current().items

ContinueWatchingItem.originalPlaybackIntent -> ContinueWatchingPlayback (explicit action only)
```

### Model and source

`ContinueWatchingItem` is immutable and has no Android Cursor/Intent objects or TMDB ID. It retains:

- Namespaced identity `tvprovider:watch_next:<package>:<rowId>` and original provider row ID.
- Title, description, package, original serialized playback intent, poster and thumbnail URI.
- Raw nullable position, duration and engagement time, native integer content type, continuation kind.
- Season/episode **display strings**, episode title, and nullable browsable/live/searchable flags.
- Playback capability at load time (`VALID_PLAYBACK` or `INVALID`); launch always validates again.

Artwork strings remain unchanged, including `https://`, `content://` and `android.resource://`.
Phase 2 does not load artwork or change the existing HTTP image loader; native-URI loading belongs
with a later UI integration. Provider labels and localized presentation strings are not stored.

`progress()` returns a nullable fraction in `0..1`; callers may multiply by 100 for display.
Null, negative position, missing duration or duration <= 0 means unknown. Zero is a known 0%;
position >= duration yields 100% without changing either raw value. The observed TV case
`808000 / 1429000` yields about **56.5%**. No fallback progress is fabricated.

`TvProviderWatchNextSource.load()` is blocking and explicitly rejects calls from the main thread.
It checks the existing runtime read permission and queries **only Watch Next**, with null projection,
selection and sort. Missing columns are optional; malformed numeric values become unknown and are
logged by column name only. Invalid identities/titles/packages or malformed boolean flags are skipped.
Negative/over-duration numeric playback values are retained for the model to interpret.

The source preserves `NEXT` separately from `CONTINUE`; both kinds are eligible for the Home row.
NEW, WATCHLIST, missing and unknown kinds map to `NONE` and remain excluded. Its result may contain
non-resumable or hidden/live records, but the repository never
promises those as Continue Watching. **Preview Programs and Channels are not queried or mixed in**;
their Phase 1 diagnostic collections remain independent.

### Qualification, ordering and failures

`ContinueWatchingRepository` includes only items with a positive row ID, nonblank title/valid owning
package, browsable absent/true, live absent/false, kind `CONTINUE` or `NEXT`, and a valid resolvable original
playback intent belonging to that package. It does not require progress, artwork, episode metadata,
internal/content IDs, engagement time, searchable=true, or any TMDB match.

Positive engagement times sort newest first; unknown/nonpositive times sort last. Stable identity
breaks ties deterministically. Only identical namespaced row identities are deduplicated, keeping
the newest engagement record if repeated. Same title, other episode/row or other app stays distinct.

Two independent, off-by-default repository filters can be enabled in Home Settings or pushed in
`config.json`: `continue_watching_recent_only` and `continue_watching_hide_finished`.
The first excludes positive engagement timestamps strictly older than a rolling 30-day window;
exactly 30 days remains eligible. Missing, zero or negative timestamps stay visible.
The second excludes known derived progress strictly greater than 95%; exactly 95%, known zero and
unknown progress stay visible. These rules apply to both CONTINUE and NEXT without altering raw data.
Changing filters invalidates older background responses; the clock and options are captured per refresh.
No polling is added: age is reevaluated on foreground and provider-change refreshes.

Results expose an immutable `items` list and explicit status: `NOT_LOADED`, `OK`,
`PERMISSION_DENIED`, `UNAVAILABLE` or `ERROR`. Revoked permissions, null cursors, unsupported tables,
provider/cursor failures and failed cursor close produce an **empty result with a failure status**,
not a partial list or a launcher crash. Exceptions are logged through `AppLog` using their class,
never their message, URI, title or extras. A later refresh can recover normally.

On the tested TV, revoking `READ_TV_LISTINGS` made provider queries silently return no rows rather
than throw. The production source's explicit permission check distinguishes that from an authorized
empty result. Privileged EPG access is not requested.

### Lifecycle API

Create one repository on the owning UI thread. Add/remove listeners and read `current()` there.
Call `onForeground()` when the screen resumes, `onBackground()` when it pauses, and `close()` when
it is destroyed. `refresh()` allows an explicit refresh while foregrounded. These methods were
initially unconnected in Phase 2; Phase 3 below now wires them into the existing opt-in Home layout.
The default Home remains unchanged and there are no queries without deliberate feature opt-in and permission.

The repository uses a single-thread IO executor and main-thread Handler, following this project's
existing service pattern. Backgrounding, refreshing or closing invalidates the previous request;
generation checks prevent even an already-posted old response from overwriting newer state.
The Android-backed repository registers one `ContentObserver` on Watch Next (including row descendants)
while foregrounded, before its initial refresh. Notifications invalidate older responses immediately and
coalesce into a single queued background reload per main-loop burst. They use the same source, filters,
sorting and immutable results as the foreground load; Home does not observe or query providers itself.
Pause and close unregister the observer and invalidate queued callbacks. Registration failure is logged
without provider data; ordinary foreground refresh remains available and registration is retried on resume.
Closing cancels work, clears listeners/data and shuts down the executor. There are no timers, background
services, polling or disk cache of viewing history.

Observation only notices changes an app publishes to TvProvider. It cannot force Disney+, Max or another
service to sync its history, and does not start those apps or introduce provider-specific network calls.

The Phase 1 permission was revoked after testing. Phase 3 obtains a deliberate runtime grant through
Home Settings; neither the build nor the installer grants it.

### Explicit playback API

`ContinueWatchingPlayback.launch(context, item)` reparses a copy of the **original** serialized
provider intent, validates and resolves it again, then launches only within the originating package:

- Rejects foreign explicit components/packages, selectors, relative data URIs and `file:`,
  `javascript:` or `data:` schemes.
- Removes ClipData, browser-fallback extras and all provider activity/URI-grant flags.
- Pins the package and adds only `FLAG_ACTIVITY_NEW_TASK`, required for application Context.
- Checks resolution, owning package and enabled/exported activity; catches launch races/denials.

The original stored string is never modified, and playback extras needed for native resume are
preserved. Results distinguish `STARTED` (activity dispatch, not proof playback actually resumed),
`INVALID_INTENT`, `UNAVAILABLE` and `FAILED`. There is deliberately **no automatic browser or app-home
fallback**; a future UX can offer an explicit separate app-open action if desired. Loading metadata
never launches playback. Existing TMDB/Wikidata deep-link handling is unaffected.

### Checks

```powershell
& tools\venv\Scripts\python.exe -m unittest discover -s tests -p "test_ui_*watching.py" -v
& tools\venv\Scripts\python.exe -m unittest discover -s tests -p test_ui_tv_provider_diagnostic.py -v
```

The tests compile the real Java boundary with fake cursors, package resolution and deterministic
IO/main queues. They cover the actual TV's numeric fixture, missing/malformed fields, native artwork,
permission/provider failures, qualification, recency, namespaced deduplication, intent sanitization,
launch outcomes and stale responses. The fixture Intent parser is not Android's implementation;
building against the Android SDK checks platform API compatibility, while actual device resolution
and resume behavior still need a later deliberately authorized TV test.

## Home integration (Phase 3)

This connects the **existing** `home_preview` Home section, not a second carousel. Its mountain background,
greeting/clock, header, four-card geometry, focus springs, below-fold apps, utilities and widgets remain.
The embedded sample titles/providers, fixed percentages, synthetic programme artwork and demo action are gone.
The layout flag retains its existing name for config compatibility.

### Ownership and presentation

`HomeView` owns one `ContinueWatchingRepository` only for this layout. On resume it registers its listener
and calls `onForeground()` **only** when the feature preference and `READ_TV_LISTINGS` are granted.
On pause it calls `onBackground()`, unregisters, invalidates artwork callbacks and releases visible bitmaps;
destroy calls `close()`. Returning from playback refreshes via that same lifecycle, not a separate timer.
While foregrounded, provider notifications also refresh through that repository; when backgrounded,
the observer is removed and Home waits for its next normal resume.
Home does not query Android providers or duplicate qualification/sorting/security rules.

Repository `current().items` goes directly into `HomeContinueWatching`, a tiny presentation/selection
helper holding those original immutable items, not another media model. It preserves selection by `stableId`
on reorder and clamps to the nearest remaining index if that identity disappears. An empty row has no cards,
heading, accessibility entries or selectable row. When a focused row disappears, focus moves to apps (or the
header without apps). With no records at entry, the header is focused and Down skips directly to apps.
More than four records use the same four-card viewport, moving the window when horizontal focus crosses it.

Title is the provider title, fitted with an ellipsis at the original card typography. Secondary text contains only
available season/episode display strings and episode title (`S2 E4 / Episode title`), or stays blank.
No provider name, episode, duration or artwork identity is guessed. The existing progress bar uses `progress()`;
unknown hides it, known zero remains visible zero and completion clamps to 100%. The percentage label truncates
to an integer: `808000 / 1429000` is about **56.5%**, displayed as **56%**. Raw model values stay unchanged.

Card OK calls the Phase 2 `ContinueWatchingPlayback` with the selected original item. Non-STARTED outcomes
show a localized launcher toast without moving focus or opening a fallback destination.
Returning from a dispatched native playback intent preserves the selected identity; pressing Home while
already at Home retains the existing reset-to-first behavior. The repository may then reorder, update or remove it.

### Permission UX

Continue Watching defaults **off**, independently of the layout flag. In the new layout:

1. Open the header's Settings gear.
2. Choose **Home Settings**, then **Continue Watching**.
3. Press OK to enable it and accept Android's TV listings permission dialog.
4. Return to Home. The settings change recreates Home through its existing preference-version mechanism.

There are no startup permission dialogs. Denial/cancellation leaves the preference off and shows feedback;
only another explicit enable action can request again. If the permission was revoked, Home clears the row and
does not query. Other Home features remain available. Turn the same setting off to stop loading without
revoking a permission another explicit debug action may need.

The setting is shown only with `home_preview` enabled, since the other Home layouts have no such row.
Neither `ACCESS_ALL_EPG_DATA` nor `WRITE_EPG_DATA` is added. The manifest is unchanged in this phase.

The following two Home Settings rows independently toggle **Continue Watching: last 30 days** and
**Continue Watching: hide over 95%**. Both default off; unknown date/progress metadata is kept.
These filters do not identify the viewer. Watch Next has no standard streaming-service profile field;
Android user isolation does not separate profiles inside Disney+, Max or another app. An engagement
timestamp is provider-supplied recency, not proof that the current viewer watched the item (especially NEXT).
An ADB grant alone does **not** turn on the feature preference: still enable the setting explicitly.

### Artwork

`Images.loadArtwork` uses the existing image executor, HTTP downloader/disk cache and memory cache.
It tries poster, then thumbnail, then a neutral card surface; failure never removes an item.
`https://` uses the existing HTTP loader; `content://` and `android.resource://` use native
`ContentResolver.openInputStream`, with sampled decoding off the main thread. Native URIs never go to HTTP.
Visible bitmaps are bounded to approximately 1024 x 576, and generations prevent obsolete callbacks painting
over a refreshed item, shifted viewport, backgrounded or destroyed Home. No I/O runs in drawing code.
Artwork failures log only classifications, never full URIs or exception messages. Downloaded artwork follows
the existing image disk-cache policy; the repository itself still stores no viewing-history files.

### Automated checks

From the repository root, with JDK 17 and the Android SDK configured:

```powershell
& tools\venv\Scripts\python.exe -m unittest discover -s tests -p 'test_ui_*.py' -v
```

The Home tests compile the real renderer, presentation helper and item model with recording graphics fakes.
They cover empty/one/multiple cards, the four-card viewport, unknown/zero/56.5%/complete progress,
partial episode metadata, identity restoration/reordering/removal, failed-result row omission and
selection dispatch/failure stability. Artwork tests run the real `Images` boundary with fake HTTP/native streams,
including native sampling, cache reuse, poster-to-thumbnail fallback and failure/privacy behavior.
Static wiring checks cover Home's lifecycle/permission/vertical-navigation connections; they are **not**
an Android lifecycle or physical remote simulation. Existing Phase 2 provider/security tests remain unchanged.
No test uses the real network or launches a streaming app.

### Physical-TV acceptance test

Build with the [UI build instructions](../README.md), preserving the existing signing key. The commands below
use native `adb` from PowerShell; the Python installation alternative earlier in this document also applies.
Back up the currently installed APK/config before replacing it. Do not uninstall or change debloat/Home settings.

```powershell
$env:TV_HOST='<tv ip>'
adb connect "$($env:TV_HOST):5555"
adb install -r launcher-ui\CleanYourTV-UI.apk
```

Proceed only after `Success`. Your existing `home_preview: true` config remains enabled.
If testing on another install, enable that layout using `launcher-ui/config.sh` first.

1. Launch Home **before opting in**. No mock titles or progress should remain; no Continue Watching row
   should appear. Up/Down must still reach header, apps and utilities. Deny the explicit settings permission
   request once: Home must stay usable and must not prompt again on later starts.
2. Return to **Settings > Home Settings > Continue Watching**, enable and grant. For a deliberate development
   grant instead, use the following command, then enable the same setting (no runtime dialog is needed):

   ```powershell
   adb shell pm grant io.cleanyourtv.ui android.permission.READ_TV_LISTINGS
   ```

3. Capture privacy-safe integration status separately if needed:

   ```powershell
   adb logcat -v threadtime -s CleanYourTV-UI:I AndroidRuntime:E "*:S"
   ```

4. Press the **real remote's Home button**. Wait for the query. Expect `Continue Watching: Home OK items=1`
   if the known YouTube record still exists. It may legitimately have changed since the diagnostic.
5. Confirm the YouTube item, actual title/artwork (if still accessible), no fabricated episode line,
   and approximately 56.5% progress (**56%** label for the known 808000/1429000 fixture).
   Missing or failed artwork must leave a selectable neutral card.
6. Check Left/Right at both edges (one record must not wrap), Up to header, Down to apps and utilities,
   then Up back to the card. With multiple records, navigate beyond the fourth and back.
7. Select the card. Expect `Continue Watching: playback STARTED` only if Android accepted the original
   provider intent. **Manually verify in YouTube** whether the expected content actually resumed;
   Activity dispatch is not proof that YouTube honored the saved position.
8. Watch a little, return with the real Home button, and verify a new `Home OK` result plus refreshed
   progress/order/removal. A surviving `stableId` must retain focus; a completed/disappearing item must
   leave focus on another card or apps/header, never an invisible card.
9. If playback becomes unavailable, expect `INVALID_INTENT`, `UNAVAILABLE` or `FAILED` and a launcher
   toast. Home must remain stable; no browser, provider-home or TMDB fallback may open.
10. Turn Continue Watching off and return Home: the row must disappear. For permission revocation testing
    (which can restart Android's launcher process):

    ```powershell
    adb shell pm revoke io.cleanyourtv.ui android.permission.READ_TV_LISTINGS
    adb shell input keyevent KEYCODE_HOME
    ```

    Home must remain usable without querying/displaying provider data or automatically requesting permission.
    Re-enable/grant explicitly afterwards only if desired.

Do not publish viewing-history screenshots/logs without redacting private information. No additional providers,
Preview Programs, TMDB enrichment/matching or Search Everywhere changes are included. TvProvider remains a
partial source: Phase 4 should retain this repository boundary rather than filling empty coverage with
recommendations or title-based deduplication.
